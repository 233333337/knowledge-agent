"""冒烟测试：保证核心模块基本可用，防止改动破坏现有行为。

分两类：
- 快测（默认跑，秒级，不加载模型）：切片、BM25、索引、配置、工具层
- 慢测（pytest -m slow，需加载本地模型）：真实检索链路

用法：
    pytest                    # 只跑快测
    pytest -m slow            # 跑慢测（含快测）
    pytest tests/test_smoke.py::test_bm25_returns_relevant_doc   # 跑单个
"""
import pytest

import bm25
import chunker
import store
import tools
from config import settings

# 判分逻辑（与 eval.py 口径一致：答案级）
from eval import _rank_of


# ---------------- 快测：不加载模型 ----------------

def test_split_text_produces_chunks():
    """长文本应被切成多个片段，且片段非空。"""
    text = ("第一段。" * 60) + "\n\n" + ("第二段。" * 60) + "\n\n" + ("第三段。" * 60)
    chunks = chunker.split_text(text, chunk_size=100, overlap=20)
    assert len(chunks) >= 2, "长文本应切成多个片段"
    assert all(isinstance(c, str) and c.strip() for c in chunks)


def test_split_text_short_input():
    """短文本不应被切碎。"""
    chunks = chunker.split_text("很短的一句话。", chunk_size=400, overlap=50)
    assert len(chunks) == 1


def test_bm25_finds_relevant_doc():
    """BM25 应把含关键词的文档排第一。"""
    corpus = [
        "Redis 缓存穿透 布隆过滤器 缓存空值",
        "TCP 三次握手 SYN ACK 连接建立",
        "Docker 镜像 容器 Dockerfile 构建",
    ]
    b = bm25.BM25(corpus)
    hits = b.search("缓存穿透", top_k=1)
    assert hits, "BM25 应有命中结果"
    assert hits[0][0] == 0, "含关键词的文档应排第一"
    assert hits[0][1] > 0


def test_bm25_returns_empty_for_unknown_terms():
    """完全无关的查询（分词后无匹配）不应返回低质结果。"""
    b = bm25.BM25(["Redis 缓存穿透", "TCP 三次握手"])
    hits = b.search("量子纠缠的实验装置", top_k=3)
    # 允许返回空，或返回但分数为 0 的结果已被过滤
    for _, score in hits:
        assert score > 0


def test_store_loads_index():
    """索引应能加载，且片段数与向量数一致。"""
    chunks, vectors = store.load()
    if not chunks:
        pytest.skip("尚未建立索引，请先运行 ingest.py")
    assert len(chunks) > 0
    assert vectors is not None
    assert len(vectors) == len(chunks), "片段数与向量数必须一致"


def test_chunk_has_required_fields():
    """每个片段必须含 text / source / title 三个字段（生成与判分都依赖）。"""
    chunks, _ = store.load()
    if not chunks:
        pytest.skip("尚未建立索引，请先运行 ingest.py")
    for c in chunks[:10]:
        assert "text" in c and c["text"].strip()
        assert "title" in c and c["title"]
        assert "source" in c


def test_settings_sane_defaults():
    """关键配置应在合理范围。"""
    assert settings.top_k >= 1
    assert settings.candidate_k >= 1
    assert settings.chunk_size > settings.chunk_overlap, "切片大小必须大于重叠大小"
    assert isinstance(settings.enable_rerank, bool)


def test_top_k_not_exceed_candidate_k():
    """top_k 不能超过 candidate_k：候选池只有 N 个时，rerank 最多只能排出 N 个。"""
    assert settings.top_k <= settings.candidate_k, (
        f"top_k({settings.top_k}) 不能大于 candidate_k({settings.candidate_k})，"
        "否则多余的位置永远取不到内容"
    )


def test_tools_definitions_exist():
    """Agent 的工具定义必须存在且结构正确（Function Calling 依赖）。"""
    assert len(tools.TOOLS) >= 2
    for t in tools.TOOLS:
        assert t["type"] == "function"
        fn = t["function"]
        assert "name" in fn and "description" in fn
        assert "query" in fn["parameters"]["properties"]
    names = {t["function"]["name"] for t in tools.TOOLS}
    assert {"search_knowledge_base", "search_web"} <= names


def test_answer_level_ranking_logic():
    """答案级判分：title 命中但答案短语不在片段中，不算命中。"""
    q = {"question": "测试", "doc": "Redis缓存", "answer": "布隆过滤器"}
    hit = [{"chunk": {"title": "Redis缓存", "text": "用布隆过滤器拦截"}}]
    miss = [{"chunk": {"title": "Redis缓存", "text": "讲别的内容"}}]
    assert _rank_of(hit, q) == 1, "含答案短语应判为命中"
    assert _rank_of(miss, q) is None, "同文档但不含答案短语，不应判为命中"


# ---------------- 慢测：需加载本地模型 ----------------

@pytest.mark.slow
def test_hybrid_search_returns_top_k():
    import retriever
    chunks, vectors = store.load()
    if not chunks:
        pytest.skip("尚未建立索引，请先运行 ingest.py")
    results = retriever.hybrid_search("缓存穿透怎么解决", chunks, vectors, top_k=3)
    assert len(results) == 3
    assert all(r["chunk"]["title"] for r in results)


@pytest.mark.slow
def test_hybrid_rerank_search_returns_top_k():
    import retriever
    chunks, vectors = store.load()
    if not chunks:
        pytest.skip("尚未建立索引，请先运行 ingest.py")
    results = retriever.hybrid_rerank_search(
        "缓存穿透怎么解决", chunks, vectors, top_k=3, candidate_k=5
    )
    assert len(results) == 3
    # rerank 分数应降序
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.slow
def test_search_entry_respects_rerank_switch(monkeypatch):
    """ENABLE_RERANK=false 时应降级为纯混合检索，不加载 rerank 模型。"""
    import retriever
    chunks, vectors = store.load()
    if not chunks:
        pytest.skip("尚未建立索引，请先运行 ingest.py")
    monkeypatch.setattr(settings, "enable_rerank", False)
    results = retriever.search("缓存穿透怎么解决", chunks, vectors, top_k=3)
    assert len(results) == 3

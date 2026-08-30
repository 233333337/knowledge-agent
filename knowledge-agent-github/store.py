"""片段与向量的持久化：Chroma 向量库（支持增量更新）。

## 版本演进

- **v1（旧）**：文本存 JSON、向量存 npy。**每加一篇文档都要全量重建**
  ——文档少时无所谓，文档多了不可接受。
- **v2（当前）**：Chroma 持久化存储。按「来源文件」增量更新与删除，
  只对新加/改动过的文档做向量化；并支持 Chroma 原生向量检索（HNSW 近似检索）。

## 对外接口（保持兼容）

- `load()` → `(chunks, vectors)`：全量取出，兼容 retriever / eval 等模块
- `save(chunks, vectors)`：全量重建（清空后写入）
- `upsert_file(source, chunks, vectors, file_hash)`：按来源文件增量更新
- `delete_source(source)`：删除某个文件的全部片段
- `get_indexed_sources()` → `{source: file_hash}`：已索引文件及其哈希
- `query_by_vector(q_emb, top_k)` → `[(chunk_index, similarity)]`：Chroma 原生检索

说明：向量已做 L2 归一化，Chroma 使用 cosine 空间时相似度 = 点积；
Chroma 返回的是 cosine distance，故 similarity = 1 - distance。
"""
import hashlib
from pathlib import Path

import numpy as np

from config import settings

_client = None
_collection = None
COLLECTION_NAME = "knowledge_base"


def _get_collection():
    """获取（或创建）Chroma 集合。延迟导入以免拖慢其它模块。"""
    global _client, _collection
    if _collection is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # 向量已 L2 归一化，cosine 空间下相似度 = 点积
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def file_hash(path) -> str:
    """计算文件内容哈希，用于判断文件是否改动（增量更新依据）。"""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def count() -> int:
    """已索引的片段总数。"""
    return _get_collection().count()


def _id_to_index() -> dict:
    """id → 全局索引 的映射（与 load() 的顺序保持一致：按 id 排序）。"""
    data = _get_collection().get(include=[])
    return {cid: i for i, cid in enumerate(sorted(data["ids"]))}


def load():
    """返回 (chunks, vectors)；无索引时返回 ([], None)。

    chunks 顺序按 id 排序，保证多次调用结果稳定。
    """
    coll = _get_collection()
    if coll.count() == 0:
        return [], None

    data = coll.get(include=["documents", "embeddings", "metadatas"])
    items = sorted(
        zip(data["ids"], data["documents"], data["embeddings"], data["metadatas"])
    )
    chunks = [
        {
            "text": doc,
            "source": (meta or {}).get("source", ""),
            "title": (meta or {}).get("title", ""),
        }
        for _, doc, _, meta in items
    ]
    vectors = np.asarray([emb for _, _, emb, _ in items], dtype="float32")
    return chunks, vectors


def load_chunks():
    """只取片段文本与元数据（BM25 建索引用），**不加载向量矩阵**，省内存。"""
    coll = _get_collection()
    if coll.count() == 0:
        return []
    data = coll.get(include=["documents", "metadatas"])
    items = sorted(zip(data["ids"], data["documents"], data["metadatas"]))
    return [
        {
            "text": doc,
            "source": (meta or {}).get("source", ""),
            "title": (meta or {}).get("title", ""),
        }
        for _, doc, meta in items
    ]


def query_by_vector(q_emb, top_k: int):
    """用 Chroma 原生检索（HNSW 近似检索），返回 [(chunk_index, similarity)] 按相似度降序。

    与 load() 的索引体系一致（chunk_index 可直接用于 chunks[i]）。
    """
    coll = _get_collection()
    total = coll.count()
    if total == 0:
        return []

    res = coll.query(
        query_embeddings=[np.asarray(q_emb, dtype="float32").tolist()],
        n_results=min(top_k, total),
        include=["distances"],
    )
    index_of = _id_to_index()
    out = []
    for cid, dist in zip(res["ids"][0], res["distances"][0]):
        idx = index_of.get(cid)
        if idx is not None:
            # Chroma 返回 cosine distance，转成相似度
            out.append((idx, float(1.0 - dist)))
    return out


def upsert_file(source, chunks: list[dict], vectors, file_hash_value: str) -> int:
    """替换某个来源文件的全部片段（增量更新的核心）。

    先删除该 source 的旧片段，再写入新片段。返回写入的片段数。
    """
    coll = _get_collection()
    try:
        coll.delete(where={"source": source})
    except Exception:
        # 该 source 原本不存在时可能报错，忽略即可
        pass

    if not chunks:
        return 0

    ids = [f"{source}::{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "source": source,
            "title": c.get("title", ""),
            "file_hash": file_hash_value,
        }
        for c in chunks
    ]
    coll.add(
        ids=ids,
        documents=[c["text"] for c in chunks],
        embeddings=[np.asarray(v, dtype="float32").tolist() for v in vectors],
        metadatas=metadatas,
    )
    return len(chunks)


def delete_source(source) -> None:
    """删除某个来源文件的全部片段（文件被删掉时用）。"""
    _get_collection().delete(where={"source": source})


def get_indexed_sources() -> dict:
    """返回 {source: file_hash}，用于增量更新时判断哪些文件变了。"""
    data = _get_collection().get(include=["metadatas"])
    out = {}
    for meta in data["metadatas"]:
        if meta and "source" in meta:
            out[meta["source"]] = meta.get("file_hash", "")
    return out


def save(chunks: list[dict], vectors):
    """全量重建：清空现有索引后写入（兼容旧接口）。"""
    coll = _get_collection()
    try:
        coll.delete(where={"source": {"$ne": "__never_match__"}})
    except Exception:
        # 兜底：直接删集合重建
        global _collection
        _client.delete_collection(COLLECTION_NAME)
        _collection = None

    if not len(chunks):
        return

    # 按 source 分组写入，保留 file_hash（没有则用空串，下次 ingest 会重算）
    sources = {}
    for c, v in zip(chunks, np.asarray(vectors, dtype="float32")):
        sources.setdefault(c.get("source", "unknown"), []).append((c, v))

    for source, items in sources.items():
        upsert_file(
            source,
            [c for c, _ in items],
            [v for _, v in items],
            items[0][0].get("file_hash", ""),
        )


def migrate_from_json() -> int:
    """把 v1 的 index.json + vectors.npy 迁移进 Chroma（一次性）。返回迁移的片段数。"""
    if not (settings.index_file.exists() and settings.vector_file.exists()):
        return 0
    import json

    chunks = json.loads(settings.index_file.read_text(encoding="utf-8"))
    vectors = np.load(settings.vector_file)
    save(chunks, vectors)
    return len(chunks)

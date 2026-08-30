"""检索模块：向量检索 + BM25 关键词检索 + RRF 混合检索。

三种检索方式：
- vector_search : 纯向量（语义相似度）
- bm25_search   : 纯关键词（BM25）
- hybrid_search : 向量排名 + BM25 排名，用 RRF 融合（默认入口）
"""
from collections import defaultdict

import numpy as np

import reranker
import store
from bm25 import BM25
from config import settings
from embedder import embed_query

# BM25 索引缓存：片段数量变化时重建
_bm25: BM25 | None = None
_bm25_count: int = -1


def _get_bm25(chunks: list[dict]) -> BM25:
    global _bm25, _bm25_count
    if _bm25 is None or len(chunks) != _bm25_count:
        _bm25 = BM25([c["text"] for c in chunks])
        _bm25_count = len(chunks)
    return _bm25


def _rrf_fuse(rankings: list[list[int]], k: int = 60) -> list[tuple]:
    """RRF（倒数排名融合）：合并多个排序，返回 [(doc_index, 融合分)] 按分降序。"""
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def vector_search(query: str, chunks=None, vectors=None, top_k=None) -> list[dict]:
    """纯向量检索，返回 [{chunk, score}]。

    默认走 Chroma 原生检索（HNSW 近似检索，数据量大时无需把向量全量载入内存）；
    .env 里设 USE_VECTOR_DB=false 则退回内存点积，便于与旧行为做对照实验。
    """
    if chunks is None:
        chunks = store.load_chunks()
    if not chunks:
        return []
    top_k = top_k or settings.top_k

    q = embed_query(query)

    if settings.use_vector_db:
        hits = store.query_by_vector(q, top_k)
        return [{"chunk": chunks[i], "score": s} for i, s in hits]

    if vectors is None:
        _, vectors = store.load()
    if vectors is None or len(vectors) == 0:
        return []
    scores = vectors @ q  # 已归一化，点积即余弦
    idxs = np.argsort(-scores)[:top_k]
    return [{"chunk": chunks[i], "score": float(scores[i])} for i in idxs]


def bm25_search(query: str, chunks=None, top_k=None) -> list[dict]:
    """BM25 关键词检索，返回 [{chunk, score}]。"""
    if chunks is None:
        chunks = store.load_chunks()
    if not chunks:
        return []
    top_k = top_k or settings.top_k

    bm25 = _get_bm25(chunks)
    hits = bm25.search(query, top_k)
    return [{"chunk": chunks[i], "score": round(s, 4)} for i, s in hits]


def hybrid_search(query: str, chunks=None, vectors=None, top_k=None) -> list[dict]:
    """混合检索：BM25 + 向量，RRF 融合。返回 [{chunk, score}]。"""
    if chunks is None:
        chunks = store.load_chunks()
    if not chunks:
        return []
    top_k = top_k or settings.top_k
    pool = max(top_k * 4, 10)  # 先各取更大候选池，融合后再取 top_k

    q = embed_query(query)

    # 向量排名：优先走 Chroma 原生检索，退回内存点积
    if settings.use_vector_db:
        v_rank = [i for i, _ in store.query_by_vector(q, pool)]
    else:
        if vectors is None:
            _, vectors = store.load()
        if vectors is None or len(vectors) == 0:
            return []
        v_rank = np.argsort(-(vectors @ q))[:pool].tolist()

    # BM25 排名
    b_rank = [i for i, _ in _get_bm25(chunks).search(query, pool)]

    fused = _rrf_fuse([v_rank, b_rank])[:top_k]
    return [{"chunk": chunks[idx], "score": round(s, 4)} for idx, s in fused]


def hybrid_rerank_search(query, chunks=None, vectors=None, top_k=None, candidate_k=None):
    """混合检索 + rerank：先混合召回 candidate_k 个候选，再用 rerank 精排取 top_k。

    candidate_k 默认取配置 CANDIDATE_K（实测 5 最优），可临时传参覆盖。
    """
    if chunks is None:
        chunks = store.load_chunks()
    if not chunks:
        return []
    top_k = top_k or settings.top_k
    candidate_k = candidate_k or settings.candidate_k

    candidates = hybrid_search(query, chunks, vectors, top_k=candidate_k)
    if not candidates:
        return []
    return reranker.rerank(query, candidates, top_k=top_k)


def search(query: str, chunks=None, vectors=None, top_k=None) -> list[dict]:
    """默认入口：混合检索 + rerank 重排。

    若 .env 里设 ENABLE_RERANK=false（内存不足时的降级方案），则退化为纯混合检索。
    """
    if not settings.enable_rerank:
        return hybrid_search(query, chunks, vectors, top_k)
    return hybrid_rerank_search(query, chunks, vectors, top_k)

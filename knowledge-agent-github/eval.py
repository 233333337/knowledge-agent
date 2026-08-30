"""离线评测：对比 BM25 / 向量 / 混合 / 混合+rerank 的召回效果。"""
import json
from pathlib import Path

import retriever
import store

BASE_DIR = Path(__file__).resolve().parent

METHODS = [
    ("bm25", "BM25"),
    ("vector", "向量"),
    ("hybrid", "混合"),
    ("hybrid_rerank", "混合+rerank"),
]


def load_queries() -> list[dict]:
    with open(BASE_DIR / "eval_queries.json", encoding="utf-8") as f:
        return json.load(f)


def run_method(method: str, question: str, chunks, vectors, top_k: int):
    if method == "bm25":
        return retriever.bm25_search(question, chunks, top_k=top_k)
    if method == "vector":
        return retriever.vector_search(question, chunks, vectors, top_k=top_k)
    if method == "hybrid":
        return retriever.hybrid_search(question, chunks, vectors, top_k=top_k)
    return retriever.hybrid_rerank_search(question, chunks, vectors, top_k=top_k)


def _rank_of(results: list[dict], q: dict):
    """答案级判分：命中 = 文档 title 匹配 且 片段文本包含答案特征短语。

    若 q 无 answer 字段（旧数据），退化为文档级判分。
    """
    target_doc = q["doc"]
    answer = q.get("answer", "")
    for i, r in enumerate(results):
        chunk = r["chunk"]
        if chunk["title"] == target_doc and (not answer or answer in chunk["text"]):
            return i + 1
    return None


def evaluate(method: str, queries, chunks, vectors, top_k: int):
    hits = 0
    rr_sum = 0.0
    for q in queries:
        results = run_method(method, q["question"], chunks, vectors, top_k)
        rank = _rank_of(results, q)
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(queries)
    return hits / n, rr_sum / n, hits, n


def main():
    chunks, vectors = store.load()
    queries = load_queries()
    print(f"评测数据集：{len(queries)} 个问题，知识库 {len(chunks)} 个片段\n")

    print(f"{'方法':<14}{'Recall@1':<12}{'Recall@3':<12}{'MRR':<10}")
    print("-" * 48)
    for method, label in METHODS:
        r1, _, _, _ = evaluate(method, queries, chunks, vectors, top_k=1)
        r3, mrr, hits, n = evaluate(method, queries, chunks, vectors, top_k=3)
        print(f"{label:<14}{r1:<12.2%}{r3:<12.2%}{mrr:<10.3f}")

    print("\n=== 逐题对比（top-3，数字=命中排名，x=未命中）===")
    for q in queries:
        row = f"[{q['doc']}] {q['question']}"
        parts = []
        for method, label in METHODS:
            res = run_method(method, q["question"], chunks, vectors, 3)
            rank = _rank_of(res, q)
            parts.append(f"{label}={rank if rank else 'x'}")
        print(f"{row}\n    " + "  ".join(parts))


if __name__ == "__main__":
    main()

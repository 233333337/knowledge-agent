"""混合检索参数调优实验（独立脚本，不改动现有代码）。

Step 1：加权 RRF 融合（纯混合，无 rerank）→ 找最优的 BM25/向量 权重
Step 2：固定最优权重 → rerank 候选池大小调优（candidate_k）

输出每种参数组合在 60 题评测集上的 Recall@1 / Recall@3 / MRR。
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import reranker
import store
from bm25 import BM25
from embedder import embed

BASE_DIR = Path(__file__).resolve().parent

# 待测参数空间：(w_bm25, w_vec) 权重组合
WEIGHTS = [
    (0.3, 0.7), (0.4, 0.6), (0.5, 0.5),
    (0.6, 0.4), (0.7, 0.3), (0.8, 0.2), (0.9, 0.1),
]
# 待测 rerank 候选池大小
CANDIDATE_KS = [5, 8, 10, 15, 20]

RRF_K = 60


def load_queries():
    return json.loads((BASE_DIR / "eval_queries.json").read_text(encoding="utf-8"))


def weighted_rrf(rankings: list[list[int]], weights: list[float], k: int = RRF_K):
    """加权倒数排名融合，返回 [(idx, score)] 按分降序。"""
    scores = defaultdict(float)
    for ranking, w in zip(rankings, weights):
        for rank, idx in enumerate(ranking):
            scores[idx] += w / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def hybrid(query_text: str, q_emb, bm25: BM25, chunks, vectors,
           w_bm25: float, w_vec: float, candidate_k: int, use_rerank: bool):
    """加权混合检索（可选 rerank），返回前 3 个 chunk。"""
    v_rank = np.argsort(-(vectors @ q_emb))[:candidate_k * 2].tolist()
    b_rank = [i for i, _ in bm25.search(query_text, candidate_k * 2)]
    fused = weighted_rrf([b_rank, v_rank], [w_bm25, w_vec])[:candidate_k]
    cands = [chunks[i] for i, _ in fused]
    if not use_rerank or not cands:
        return cands[:3]
    ranked = reranker.rerank(query_text, [{"chunk": c} for c in cands], top_k=3)
    return [r["chunk"] for r in ranked]


def rank_of(chunks: list[dict], q: dict):
    """答案级判分（与 eval.py 口径一致）：title 匹配 且 片段含答案短语。"""
    target_doc = q["doc"]
    answer = q.get("answer", "")
    for i, c in enumerate(chunks):
        if c["title"] == target_doc and (not answer or answer in c["text"]):
            return i + 1
    return None


def evaluate(queries, q_embs, bm25, chunks, vectors,
             w_bm25, w_vec, candidate_k, use_rerank):
    hits1 = hits3 = 0
    rr = 0.0
    for q, emb in zip(queries, q_embs):
        res = hybrid(q["question"], emb, bm25, chunks, vectors,
                     w_bm25, w_vec, candidate_k, use_rerank)
        r = rank_of(res, q)
        if r is not None:
            if r == 1:
                hits1 += 1
            if r <= 3:
                hits3 += 1
            rr += 1.0 / r
    n = len(queries)
    return hits1 / n, hits3 / n, rr / n


def main():
    chunks, vectors = store.load()
    queries = load_queries()
    n = len(queries)

    print(f"评测集：{n} 题，知识库 {len(chunks)} 片段\n")

    # 预计算所有问题的 query embedding（只算一次，实验循环复用）
    print(f"预计算 {n} 题 query embedding ...")
    q_embs = embed([q["question"] for q in queries])
    bm25 = BM25([c["text"] for c in chunks])
    print("完成\n")

    # ---- Step 1：加权 RRF（纯混合，无 rerank）----
    print("=" * 60)
    print("Step 1：加权 RRF 融合（纯混合，无 rerank）")
    print("=" * 60)
    print(f"{'BM25权':<8}{'向量权':<8}{'R@1':<10}{'R@3':<10}{'MRR':<8}")
    print("-" * 44)
    best_w = None
    best_r1 = 0
    for w_bm25, w_vec in WEIGHTS:
        r1, r3, mrr = evaluate(queries, q_embs, bm25, chunks, vectors,
                               w_bm25, w_vec, candidate_k=10, use_rerank=False)
        flag = ""
        if r1 > best_r1:
            best_r1, best_w, flag = r1, (w_bm25, w_vec), "  <== 最优"
        print(f"{w_bm25:<8.1f}{w_vec:<8.1f}{r1:<10.2%}{r3:<10.2%}{mrr:<8.3f}{flag}")
    print(f"\n最优权重：BM25={best_w[0]}, 向量={best_w[1]}（R@1={best_r1:.2%}）\n")

    # ---- Step 2：候选池大小（固定最优权重 + rerank）----
    print("=" * 60)
    print(f"Step 2：rerank 候选池大小（权重 BM25={best_w[0]}, 向量={best_w[1]}）")
    print("=" * 60)
    print(f"{'候选池':<8}{'R@1':<10}{'R@3':<10}{'MRR':<8}")
    print("-" * 36)
    best_k = None
    best_r1 = 0
    for ck in CANDIDATE_KS:
        r1, r3, mrr = evaluate(queries, q_embs, bm25, chunks, vectors,
                               best_w[0], best_w[1], candidate_k=ck, use_rerank=True)
        flag = ""
        if r1 > best_r1:
            best_r1, best_k, flag = r1, ck, "  <== 最优"
        print(f"{ck:<8}{r1:<10.2%}{r3:<10.2%}{mrr:<8.3f}{flag}")

    print(f"\n最终推荐：权重 BM25={best_w[0]}/向量={best_w[1]}，候选池={best_k}，R@1={best_r1:.2%}")


if __name__ == "__main__":
    main()

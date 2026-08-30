"""top_k / candidate_k 参数实验：测 Recall@k 曲线，看增大返回片段数的收益。

## 背景
端到端评测用 top_k=4 给 LLM 资料，而检索评测只测到 top_k=3（R@3=86.51%）。
已知召回随 top_k 增长明显（R@1 64.29% → R@3 86.51%），
本实验测更大的 top_k 能带来多少召回提升，为端到端挑选最优配置。

## 关键约束
top_k 受 candidate_k 限制：候选池只有 N 个，rerank 最多只能排出 N 个。
所以想增大 top_k，必须同时增大 candidate_k。本实验同时测两者。

## 判分口径
与 eval.py 一致（答案级：title 匹配 且 片段含 answer 短语）。

用法：
    python tune_topk.py
"""
import json
from pathlib import Path

import retriever
import store
from eval import _rank_of

BASE_DIR = Path(__file__).resolve().parent

# (candidate_k, top_k) 组合
# 第一组：当前候选池 5，逐步增大 top_k（上限被 5 卡住）
# 第二组：候选池放大到 10，看能否继续提升
COMBOS = [
    (5, 1), (5, 2), (5, 3), (5, 4), (5, 5),
    (10, 5), (10, 6), (10, 8), (10, 10),
]


def evaluate(queries, chunks, vectors, candidate_k, top_k):
    """返回 (Recall@k, MRR)。"""
    hits = 0
    rr_sum = 0.0
    for q in queries:
        results = retriever.hybrid_rerank_search(
            q["question"], chunks, vectors, top_k=top_k, candidate_k=candidate_k
        )
        rank = _rank_of(results, q)
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank
    n = len(queries)
    return hits / n, rr_sum / n


def main():
    queries = json.loads((BASE_DIR / "eval_queries.json").read_text(encoding="utf-8"))
    chunks, vectors = store.load()

    print(f"top_k 实验：{len(queries)} 题，知识库 {len(chunks)} 片段\n")
    print(f"{'候选池':<8}{'top_k':<8}{'Recall@k':<12}{'MRR':<10}")
    print("-" * 38)

    results = {}
    for candidate_k, top_k in COMBOS:
        r, mrr = evaluate(queries, chunks, vectors, candidate_k, top_k)
        results[(candidate_k, top_k)] = (r, mrr)
        note = "  <- 当前线上配置" if (candidate_k, top_k) == (5, 3) else ""
        print(f"{candidate_k:<8}{top_k:<8}{r:<12.2%}{mrr:<10.3f}{note}", flush=True)

    print("\n" + "=" * 38)
    base = results[(5, 3)]  # 检索评测口径（top_k=3）
    print(f"基线（候选池5 / top_k=3，对应检索评测 R@3）：Recall={base[0]:.2%} MRR={base[1]:.3f}")
    best_key = max(results, key=lambda k: results[k][0])
    best = results[best_key]
    print(f"最优配置：候选池={best_key[0]} / top_k={best_key[1]}，"
          f"Recall={best[0]:.2%}（对比基线 {(best[0] - base[0]) * 100:+.2f}pt），MRR={best[1]:.3f}")


if __name__ == "__main__":
    main()

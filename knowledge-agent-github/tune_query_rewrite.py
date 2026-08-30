"""查询改写优化实验：对比 baseline / 查询扩展 / 多查询融合 的检索效果。

## 背景
126 题评测暴露「答案细节级」短板：用户问得口语化，答案藏在专业术语/代码符号片段里，
产生词汇鸿沟。本实验验证「检索前先改写查询」能否提升召回。

## 三种模式
- baseline ：不改，直接拿原问题检索（= 现有线上行为）
- expand   ：LLM 把问题扩展成含术语/符号的查询串，再检索
- multi    ：原问题 + 3 个改写查询分别召回，候选池去重后统一 rerank 精排

## 判分口径
与 eval.py 完全一致（答案级：title 匹配 且 片段含 answer 短语），
R@1 用 top_k=1 检索、R@3/MRR 用 top_k=3 检索，结果可与 eval.py 基线直接对比。

## 用法
    python tune_query_rewrite.py --limit 30   # 快速验证（推荐先跑这个）
    python tune_query_rewrite.py              # 全量 126 题

注：本脚本不改动任何现有代码，仅做离线实验。
"""
import argparse
import json
from pathlib import Path

import query_rewriter
import reranker
import retriever
import store
from eval import _rank_of

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR / "test" / "query_rewrite_cache.json"
CANDIDATE_K = 5


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get_rewrites(question: str, cache: dict) -> tuple[str, list[str]]:
    """取改写结果，优先走缓存（避免重复调用 API）。"""
    if question in cache:
        item = cache[question]
        return item["expand"], item["multi"]
    expand = query_rewriter.rewrite_expand(question)
    multi = query_rewriter.rewrite_multi(question, n=3)
    cache[question] = {"expand": expand, "multi": multi}
    return expand, multi


def search_baseline(question, chunks, vectors, top_k):
    """现有线上行为：混合检索 + rerank。"""
    return retriever.hybrid_rerank_search(
        question, chunks, vectors, top_k=top_k, candidate_k=CANDIDATE_K
    )


def search_expand(query_rewritten, chunks, vectors, top_k):
    """用改写后的查询走同样的混合检索 + rerank。"""
    return retriever.hybrid_rerank_search(
        query_rewritten, chunks, vectors, top_k=top_k, candidate_k=CANDIDATE_K
    )


def search_multi(question, rewrite_qs, chunks, vectors, top_k):
    """多查询：原问题 + 各改写查询分别召回，候选池去重后统一精排。"""
    all_qs = [question] + list(rewrite_qs)
    pool, seen = [], set()
    for q in all_qs:
        hits = retriever.hybrid_search(q, chunks, vectors, top_k=CANDIDATE_K)
        for h in hits:
            key = h["chunk"]["text"]
            if key not in seen:
                seen.add(key)
                pool.append(h)
    if not pool:
        return []
    # 用原问题精排：原问题才代表用户真实意图
    return reranker.rerank(question, pool, top_k=top_k)


def evaluate(queries, chunks, vectors, cache, mode):
    """返回 (R@1, R@3, MRR)。"""
    hits1 = hits3 = 0
    rr_sum = 0.0
    for q in queries:
        question = q["question"]
        expand, multi = get_rewrites(question, cache)

        if mode == "baseline":
            r1_res = search_baseline(question, chunks, vectors, top_k=1)
            r3_res = search_baseline(question, chunks, vectors, top_k=3)
        elif mode == "expand":
            r1_res = search_expand(expand, chunks, vectors, top_k=1)
            r3_res = search_expand(expand, chunks, vectors, top_k=3)
        else:  # multi
            r1_res = search_multi(question, multi, chunks, vectors, top_k=1)
            r3_res = search_multi(question, multi, chunks, vectors, top_k=3)

        rank1 = _rank_of(r1_res, q)
        rank3 = _rank_of(r3_res, q)
        if rank1 == 1:
            hits1 += 1
        if rank3 is not None and rank3 <= 3:
            hits3 += 1
        if rank3:
            rr_sum += 1.0 / rank3

    n = len(queries)
    return hits1 / n, hits3 / n, rr_sum / n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（快速验证用）")
    args = parser.parse_args()

    queries = json.loads((BASE_DIR / "eval_queries.json").read_text(encoding="utf-8"))
    if args.limit:
        queries = queries[: args.limit]

    chunks, vectors = store.load()
    cache = load_cache()

    print(f"查询改写实验：{len(queries)} 题，知识库 {len(chunks)} 片段，候选池={CANDIDATE_K}")
    print("预生成改写结果（带缓存，重复运行不重复消耗 API）...", flush=True)

    # 先统一生成/读取改写，避免三种模式各自触发 API
    for q in queries:
        get_rewrites(q["question"], cache)
    save_cache(cache)
    print(f"改写缓存已保存：{CACHE_FILE}\n")

    results = {}
    for mode in ("baseline", "expand", "multi"):
        r1, r3, mrr = evaluate(queries, chunks, vectors, cache, mode)
        results[mode] = (r1, r3, mrr)
        print(f"  {mode} 完成：R@1={r1:.2%} R@3={r3:.2%} MRR={mrr:.3f}", flush=True)

    base_r1, base_r3, base_mrr = results["baseline"]
    print()
    print(f"{'方法':<16}{'Recall@1':<12}{'Recall@3':<12}{'MRR':<10}{'对比基线(R@1)':<14}")
    print("-" * 64)
    labels = {"baseline": "baseline(不改)", "expand": "+查询扩展", "multi": "+多查询融合"}
    for mode in ("baseline", "expand", "multi"):
        r1, r3, mrr = results[mode]
        delta = "" if mode == "baseline" else f"{(r1 - base_r1) * 100:+.2f}pt"
        print(f"{labels[mode]:<16}{r1:<12.2%}{r3:<12.2%}{mrr:<10.3f}{delta:<14}")
    print("-" * 64)

    print("\n各指标最优（注意：R@1 与 R@3 结论可能不一致，需结合端到端评测判断）：")
    for idx, name, is_pct in ((0, "Recall@1", True), (1, "Recall@3", True), (2, "MRR", False)):
        best = max(("baseline", "expand", "multi"), key=lambda m: results[m][idx])
        val = results[best][idx]
        base_val = results["baseline"][idx]
        if best == "baseline":
            tag = "（= 基线，改写未带来提升）"
        elif is_pct:
            tag = f"（对比基线 {(val - base_val) * 100:+.2f}pt）"
        else:
            tag = f"（对比基线 {val - base_val:+.3f}）"
        print(f"  {name:<10}最优 = {labels[best]:<14}{val:.2%} {tag}")


if __name__ == "__main__":
    main()

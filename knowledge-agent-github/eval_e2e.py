"""端到端评测：检索 → 生成 → LLM 判分，测「回答正确率 / 引用率 / 幻觉率」。

与 eval.py 的区别：
- eval.py      ：只测「检索」环节（有没有找到正确答案片段），不调大模型生成
- eval_e2e.py  ：测「提问 → 最终回答」整条链路，包含检索 + 生成 + 质量判分

判分方式：LLM-as-judge（让 DeepSeek 当阅卷老师），判分时**不带知识库上下文**，
只给它「问题 + 标准答案要点 + 系统回答」，避免它自己脑补答案。

用法：
    python eval_e2e.py            # 跑全部 30 题
    python eval_e2e.py --limit 1  # 冒烟测试，只跑第 1 题
"""
import argparse
import json
import re
import sys
from pathlib import Path

import llm
import retriever
import store
from config import settings

BASE_DIR = Path(__file__).resolve().parent
QUERIES_FILE = BASE_DIR / "eval_e2e_queries.json"
RESULTS_FILE = BASE_DIR / "test" / "eval_e2e_results.json"

JUDGE_SYSTEM = (
    "你是评测阅卷老师。请严格依据「标准答案要点」评判「系统回答」。"
    "只输出 JSON，不要输出任何其他内容。"
)

JUDGE_TEMPLATE = """【问题】
{question}

【标准答案要点】
{points}

【系统回答】
{answer}

【评分规则】
- covered（整数）：系统回答覆盖了多少个要点（0 ~ {total}）
- correctness（0-3 整数）：
    3 = 覆盖全部要点且无事实错误
    2 = 覆盖过半要点（≥50%）且无严重错误
    1 = 只覆盖少量要点
    0 = 基本错误、答非所问，或直接回答“未找到相关信息”
- citation（0 或 1）：回答中是否标注了来源/引用（如“来源 1”“来自《xxx》”等）
- hallucination（0 或 1）：是否编造了标准答案要点之外的、明显无依据的内容
    （合理的补充说明不算幻觉，只有明显瞎编才算）

请输出：
{{"covered": <整数>, "total": {total}, "correctness": <0-3>, "citation": <0或1>, "hallucination": <0或1>, "reason": "<一句话说明>"}}"""


def parse_json(text: str) -> dict | None:
    """从模型输出里提取 JSON 对象（容错：允许被 ```json 包裹或前后有多余文字）。"""
    text = text.strip()
    # 去掉可能的 ```json ... ``` 包裹
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def judge(question: str, points: list[str], answer: str, client) -> dict:
    """让 DeepSeek 当阅卷老师，返回判分 dict。"""
    points_text = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(points))
    prompt = JUDGE_TEMPLATE.format(
        question=question, points=points_text, answer=answer, total=len(points)
    )
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    content = resp.choices[0].message.content or ""
    parsed = parse_json(content)
    if parsed is None:
        return {"error": "判分解析失败", "raw": content}
    return parsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（冒烟测试用）")
    parser.add_argument("--top-k", type=int, default=4, help="检索返回的片段数")
    parser.add_argument("--rewrite", action="store_true",
                        help="检索前先用 LLM 改写查询（验证查询改写对回答质量的影响）")
    parser.add_argument("--candidate-k", type=int, default=5,
                        help="rerank 候选池大小（top_k 不能超过它）")
    parser.add_argument("--tag", default="",
                        help="结果文件后缀，用于区分不同配置（如 topk5），避免覆盖基线结果")
    args = parser.parse_args()

    # 不同配置的结果单独存文件，避免互相覆盖
    if args.tag:
        results_file = BASE_DIR / "test" / f"eval_e2e_results_{args.tag}.json"
    elif args.rewrite:
        results_file = BASE_DIR / "test" / "eval_e2e_results_rewrite.json"
    else:
        results_file = RESULTS_FILE

    queries = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    if args.limit:
        queries = queries[: args.limit]

    chunks, vectors = store.load()
    print(f"端到端评测：{len(queries)} 题，知识库 {len(chunks)} 片段")
    print(f"配置：top_k={args.top_k}  候选池={args.candidate_k}  查询改写={args.rewrite}")
    print(f"生成模型：{settings.deepseek_model}\n")

    client = llm.get_client()
    records = []

    for i, q in enumerate(queries, 1):
        question = q["question"]
        print(f"[{i}/{len(queries)}] {question}", flush=True)

        # 1) 检索（混合 + rerank）；--rewrite 时先用 LLM 把问题改写成更适合检索的查询
        search_q = question
        if args.rewrite:
            import query_rewriter
            search_q = query_rewriter.rewrite_expand(question)
        hits = retriever.hybrid_rerank_search(
            search_q, chunks, vectors, top_k=args.top_k, candidate_k=args.candidate_k
        )
        retrieved = [
            {"title": h["chunk"]["title"], "score": h["score"]} for h in hits
        ]

        # 2) 生成最终回答
        answer = llm.generate(hits, question)

        # 3) 判分
        j = judge(question, q["answer_points"], answer, client)

        records.append({
            "question": question,
            "rewritten_query": search_q,
            "doc": q["doc"],
            "answer_points": q["answer_points"],
            "retrieved": retrieved,
            "answer": answer,
            "judge": j,
        })

        flag = ""
        if "error" in j:
            flag = f"  ⚠ {j['error']}"
        else:
            flag = (f"  正确={j.get('correctness')} "
                    f"引用={j.get('citation')} "
                    f"幻觉={j.get('hallucination')}")
        print(f"    {flag}", flush=True)

    # 4) 统计
    valid = [r for r in records if "error" not in r["judge"]]
    n = len(valid)
    if n == 0:
        print("没有有效判分结果")
        return

    correct_hits = sum(1 for r in valid if r["judge"].get("correctness", 0) >= 2)
    full_hits = sum(1 for r in valid if r["judge"].get("correctness", 0) == 3)
    citation_hits = sum(1 for r in valid if r["judge"].get("citation") == 1)
    halluc_hits = sum(1 for r in valid if r["judge"].get("hallucination") == 1)
    avg_correct = sum(r["judge"].get("correctness", 0) for r in valid) / n / 3

    print("\n" + "=" * 56)
    print("端到端评测结果")
    print("=" * 56)
    print(f"有效题数        {n} / {len(records)}")
    print(f"回答正确率(≥2分) {correct_hits / n:.2%}   ({correct_hits}/{n})")
    print(f"完全正确率(3分)  {full_hits / n:.2%}   ({full_hits}/{n})")
    print(f"平均正确分      {avg_correct:.2%}   (0-3 归一化)")
    print(f"引用率          {citation_hits / n:.2%}   ({citation_hits}/{n})")
    print(f"幻觉率          {halluc_hits / n:.2%}   ({halluc_hits}/{n})")
    print("=" * 56)

    # 5) 保存详细结果
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n详细结果已保存：{results_file}")


if __name__ == "__main__":
    main()

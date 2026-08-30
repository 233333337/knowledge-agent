"""查询改写模块：把用户口语化的问题，改写成更适合检索的查询。

## 为什么需要它

126 题评测暴露了「答案细节级」短板：用户问得口语化、笼统（"装饰器怎么用啊"），
而答案藏在含专业术语/代码符号的片段里（"functools.wraps"）。
这种**词汇鸿沟**导致检索命中率低。

查询改写的思路：检索之前，先让 LLM 把问题"翻译"成更接近资料表述的查询。

## 两种策略

- `rewrite_expand`：单次查询扩展——补充同义词、专业术语、代码符号，输出一个查询串
- `rewrite_multi` ：多查询——生成 3 个不同表述的查询，多角度召回后融合

本模块为**实验模块**，合入正式检索流程前需先由 tune_query_rewrite.py 验证收益。
"""
from config import settings
from llm import get_client

EXPAND_SYSTEM = (
    "你是检索查询优化助手。用户会给出一个口语化的问题，"
    "请把它改写成更适合在中文技术笔记中做「关键词 + 语义」混合检索的查询串。\n\n"
    "要求：\n"
    "1. 补充问题中可能涉及的专业术语、英文术语、代码符号、常见写法\n"
    "2. 保留原问题的核心语义，不要答非所问\n"
    "3. 只输出一个用空格分隔的检索查询串，不要输出解释、标点或句子\n\n"
    "示例：\n"
    "问题：装饰器怎么用啊\n"
    "输出：装饰器 原理 用法 functools.wraps 高阶函数\n\n"
    "问题：怎么把不存在的请求挡在数据库外面\n"
    "输出：缓存穿透 布隆过滤器 缓存空值 Redis\n"
)

MULTI_SYSTEM = (
    "你是检索查询优化助手。用户会给出一个口语化的问题，"
    "请生成 3 个不同表述的检索查询，用于多角度检索后融合结果。\n\n"
    "三个查询分别侧重：\n"
    "1. 关键词直白版：直接用问题里的核心词\n"
    "2. 同义改写版：换一种说法表达同一个意思\n"
    "3. 术语符号版：补充相关专业术语、英文术语、代码符号\n\n"
    "要求：每行一个查询，共 3 行，不要编号、不要解释、不要多余文字。\n\n"
    "示例：\n"
    "问题：装饰器怎么用啊\n"
    "输出：\n"
    "装饰器 用法\n"
    "如何给函数增加额外功能\n"
    "装饰器 原理 functools.wraps 高阶函数\n"
)


def _call(system: str, user: str, temperature: float = 0.2) -> str:
    """调用 DeepSeek 做改写。"""
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def rewrite_expand(query: str) -> str:
    """查询扩展：返回一个改写后的查询串（失败时返回原问题，保证不中断流程）。"""
    out = _call(EXPAND_SYSTEM, f"问题：{query}\n输出：")
    # 清洗：去掉可能的引号、换行，压缩空白
    out = out.replace('"', "").replace("'", "").replace("\n", " ").strip()
    return out or query


def rewrite_multi(query: str, n: int = 3) -> list[str]:
    """多查询：返回 n 个不同表述的查询（失败时返回 [原问题]，保证不中断流程）。"""
    out = _call(MULTI_SYSTEM, f"问题：{query}\n输出：")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    # 去掉可能残留的编号前缀（1. / - 等）
    cleaned = []
    for ln in lines:
        ln = ln.lstrip("0123456789.-、) ").strip()
        if ln:
            cleaned.append(ln)
    result = (cleaned or [query])[:n]
    return result

"""Agent 工具：本地知识库检索 + 联网搜索（Tavily）。

把工具做成可插拔：以后换成 Semantic Scholar，只需改 search_web 这一个函数。
"""
import requests

import retriever
import store
from config import settings


def search_knowledge_base(query: str) -> str:
    """检索本地知识库，返回相关片段。"""
    chunks, vectors = store.load()
    if not chunks:
        return "知识库为空"
    results = retriever.search(query, chunks, vectors, top_k=4)
    if not results:
        return "知识库中没有找到相关内容"
    return "\n\n".join(
        f"[{i + 1}] 《{r['chunk']['title']}》\n{r['chunk']['text']}"
        for i, r in enumerate(results)
    )


def search_web(query: str) -> str:
    """联网搜索（Tavily），返回结果摘要。以后可替换为 Semantic Scholar。"""
    if not settings.tavily_api_key:
        return "未配置 TAVILY_API_KEY，无法联网搜索"
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": 5,
                "search_depth": "basic",
            },
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        return f"联网搜索失败：{e}"

    results = resp.json().get("results", [])
    if not results:
        return "未搜索到结果"
    return "\n\n".join(
        f"[{i + 1}] {r.get('title', '')}\n{r.get('content', '')[:300]}\n{r.get('url', '')}"
        for i, r in enumerate(results)
    )


# Function Calling 工具定义（传给 DeepSeek 的 tools 参数）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "检索本地个人知识库，返回相关文档片段。当问题涉及用户自己的笔记、文档、项目资料时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或问题"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索最新信息。当本地知识库没有答案、或问题涉及实时/公开/通用知识时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """执行指定工具并返回结果字符串。"""
    query = args.get("query", "")
    if name == "search_knowledge_base":
        return search_knowledge_base(query)
    if name == "search_web":
        return search_web(query)
    return f"未知工具: {name}"

"""Agent 循环：让 LLM 自主决定调用工具，直到给出最终回答。"""
import json

from config import settings
from llm import get_client
import tools

SYSTEM = (
    "你是个人知识库助手，会自主判断该用哪个工具回答问题：\n"
    "1. 问题涉及用户自己的笔记、文档、项目资料 → 调用 search_knowledge_base 检索本地知识库；\n"
    "2. 本地知识库没有答案，或问题涉及实时/公开/通用知识 → 调用 search_web 联网搜索；\n"
    "3. 简单寒暄、或无需外部信息就能回答的问题 → 直接回答，不调用工具。\n"
    "回答要准确、简洁，使用中文。如果引用了资料，请说明信息来源。"
)


def run_agent(question: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
    """执行 Agent 循环，返回 (最终回答, 工具调用步骤列表)。"""
    client = get_client()

    messages = [{"role": "system", "content": SYSTEM}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})

    steps: list[dict] = []

    for _ in range(6):  # 最多 6 轮工具调用，防止死循环
        resp = client.chat.completions.create(
            model=settings.deepseek_model,
            messages=messages,
            tools=tools.TOOLS,
            temperature=0.3,
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            # 记录本轮 assistant 消息（含 tool_calls）
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            # 逐个执行工具
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = tools.execute_tool(tc.function.name, args)
                steps.append({
                    "tool": tc.function.name,
                    "query": args.get("query", ""),
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            return msg.content or "", steps

    return "抱歉，处理超时，请稍后重试。", steps

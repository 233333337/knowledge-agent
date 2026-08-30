"""DeepSeek 对话封装（OpenAI 兼容协议），用于基于检索结果生成回答。"""
from openai import OpenAI

from config import settings

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.deepseek_api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写")
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


def generate(context_chunks: list[dict], question: str, history: list[dict] | None = None) -> str:
    """把检索到的片段拼成上下文，让 DeepSeek 基于资料回答。

    history: 多轮对话历史 [{role, content}]，注入以支持追问和上下文连贯。
    """
    client = get_client()

    context = "\n\n".join(
        f"[来源 {i + 1}：《{c['chunk']['title']}》]\n{c['chunk']['text']}"
        for i, c in enumerate(context_chunks)
    )

    system = (
        "你是我的个人知识库助手，只能基于提供的资料回答，不要编造。"
        "如果资料中没有答案，请直接说明「资料中未找到相关信息」。"
        "回答要准确、简洁，末尾用「引用：来源 1、来源 2」标注引用了哪些资料。"
    )

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])  # 只带最近 6 条历史，控制长度
    messages.append(
        {"role": "user", "content": f"参考资料：\n{context}\n\n用户问题：{question}"}
    )

    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""

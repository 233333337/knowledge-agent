"""Streamlit 问答界面：Agent 自主决策（检索/联网）+ 多轮对话。"""
import streamlit as st

import agent
import store
from config import settings

st.set_page_config(page_title="个人知识库 Agent", page_icon="📚", layout="wide")

chunks, vectors = store.load()

with st.sidebar:
    st.header("索引状态")
    st.metric("已索引片段", len(chunks))
    st.write(f"文档目录：`{settings.docs_dir}`")
    st.write(f"Embedding：`{settings.embed_model}`")
    st.write(f"Rerank：`{settings.rerank_model}`")
    if not chunks:
        st.warning("还没有索引，请先放文档并运行 ingest.py")
    if not settings.deepseek_api_key:
        st.warning("未配置 DEEPSEEK_API_KEY")
    if not settings.tavily_api_key:
        st.warning("未配置 TAVILY_API_KEY，联网搜索不可用")
    if st.button("清空对话"):
        st.session_state.history = []
        st.rerun()

st.title("📚 个人知识库 Agent")
st.caption("自主决策 · 检索本地库 / 联网搜索 · 多轮对话")

# 初始化对话历史（存内存，刷新会清空）
if "history" not in st.session_state:
    st.session_state.history = []

# 渲染历史对话
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("输入你的问题…")

if question:
    if not chunks:
        st.warning("知识库为空，请先放文档并运行 ingest.py")
    else:
        with st.chat_message("user"):
            st.write(question)

        with st.spinner("思考中…"):
            try:
                reply, steps = agent.run_agent(question, st.session_state.history)
            except Exception as e:
                reply, steps = f"生成失败：{e}", []

        with st.chat_message("assistant"):
            st.write(reply)
            if steps:
                with st.expander(f"Agent 调用了 {len(steps)} 次工具"):
                    for s in steps:
                        label = "检索知识库" if s["tool"] == "search_knowledge_base" else "联网搜索"
                        st.markdown(f"- {label}：`{s['query']}`")

        st.session_state.history.append({"role": "user", "content": question})
        st.session_state.history.append({"role": "assistant", "content": reply})

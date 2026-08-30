"""rerank 重排：用 CrossEncoder 对候选片段精排。

CrossEncoder 把「问题 + 片段」成对输入，直接输出相关性分数，
比向量余弦更精细，适合在混合检索召回后做精排。
"""
import os

import torch  # 必须早于 config/dotenv 加载：Windows CRT 环境块冲突会导致 torch 初始化 segfault

os.environ.setdefault("HF_HOME", "D:/AI-models/huggingface")

import numpy as np

from config import settings

# config 加载后 .env 已生效，用配置值覆盖默认缓存目录。
# 注意：只能在 config 之后覆盖，不能提前 import config（torch 必须先加载，否则 segfault）
os.environ["HF_HOME"] = settings.hf_home

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        print(f"[reranker] 正在加载本地模型 {settings.rerank_model} ...")
        _model = CrossEncoder(settings.rerank_model)
        print("[reranker] 模型加载完成")
    return _model


def rerank(query: str, candidates: list[dict], top_k=None) -> list[dict]:
    """对候选片段精排，返回按相关性降序的 [{chunk, score}]。"""
    if not candidates:
        return []
    model = get_model()

    pairs = [[query, c["chunk"]["text"] if isinstance(c, dict) and "chunk" in c else c["text"]]
             for c in candidates]
    scores = model.predict(pairs)

    order = np.argsort(-np.asarray(scores))
    top_k = top_k or len(candidates)

    result = []
    for i in order[:top_k]:
        item = candidates[i]
        if isinstance(item, dict) and "chunk" in item:
            result.append({"chunk": item["chunk"], "score": float(scores[i])})
        else:
            result.append({"chunk": item, "score": float(scores[i])})
    return result

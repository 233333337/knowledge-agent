"""本地 embedding 封装：把文字转成语义向量（bge-small-zh）。

使用 sentence-transformers 加载北京智源的 bge-small-zh-v1.5 模型，
首次运行会自动下载模型文件到本地缓存。
"""
import os

import torch  # 必须早于 config/dotenv 加载：Windows CRT 环境块冲突会导致 torch 初始化 segfault

# 国内下载 HuggingFace 模型走镜像，避免连接超时（不影响已缓存的情况）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
# 模型缓存放 D 盘（默认在 C 盘用户目录，占空间且本机约定不落 C 盘）
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
        from sentence_transformers import SentenceTransformer

        print(f"[embedder] 正在加载本地模型 {settings.embed_model}（首次会下载）...")
        _model = SentenceTransformer(settings.embed_model)
        print("[embedder] 模型加载完成")
    return _model


def embed(texts, normalize=True) -> np.ndarray:
    """把一批文字转成向量矩阵，默认做 L2 归一化（这样点积即余弦相似度）。"""
    model = get_model()
    vecs = model.encode(
        texts,
        normalize_embeddings=normalize,
        show_progress_bar=len(texts) > 10,
    )
    return np.asarray(vecs, dtype="float32")


def embed_query(text: str) -> np.ndarray:
    """把单个查询文字转成向量。"""
    return embed([text])[0]

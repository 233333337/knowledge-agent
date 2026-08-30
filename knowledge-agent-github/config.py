import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """集中配置：读 .env，未配置时用合理默认值。"""

    # DeepSeek（生成回答）
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 本地 embedding 模型（北京智源 BAAI 开源，中文专用）
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")

    # 本地 rerank 模型（重排，精排候选片段）
    # 默认用模型名（首次运行自动下载）；若已有本地模型目录，在 .env 里用 RERANK_MODEL 指定
    rerank_model: str = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")

    # 模型缓存目录（HuggingFace）；默认放项目下的 models/，避免占用系统盘
    hf_home: str = os.getenv("HF_HOME", str(BASE_DIR / "models"))

    # 联网搜索 API（Agent 工具用）
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    semantic_scholar_api_key: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

    # 路径
    data_dir: Path = BASE_DIR / "data"
    docs_dir: Path = BASE_DIR / "data" / "docs"
    index_file: Path = BASE_DIR / "data" / "index.json"   # 片段文本 + 元数据（v1 旧格式，仅迁移用）
    vector_file: Path = BASE_DIR / "data" / "vectors.npy"  # 向量矩阵（v1 旧格式，仅迁移用）
    chroma_dir: Path = BASE_DIR / "data" / "chroma"       # v2：Chroma 向量库持久化目录

    # 切片参数
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "400"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "50"))

    # 检索参数（默认值均为实测最优，见 codebuddy笔记.md 的调优实验）
    top_k: int = int(os.getenv("TOP_K", "4"))              # 最终交给 LLM 的片段数
    candidate_k: int = int(os.getenv("CANDIDATE_K", "5"))  # 喂给 rerank 精排的候选数

    # 是否启用 rerank 精排。内存不足导致双模型同进程加载崩溃时，
    # 可在 .env 里设 ENABLE_RERANK=false 降级为纯混合检索（速度更快、内存更省）
    enable_rerank: bool = os.getenv("ENABLE_RERANK", "true").lower() in ("1", "true", "yes")

    # 向量检索是否走 Chroma 向量库（HNSW 近似检索，数据量大时也不用全量载入内存）。
    # 设 false 则退回内存点积，用于与旧行为做对照实验
    use_vector_db: bool = os.getenv("USE_VECTOR_DB", "true").lower() in ("1", "true", "yes")


settings = Settings()

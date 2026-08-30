# 个人知识库 RAG Agent

一个**检索增强生成（RAG）**系统：把个人笔记、文档喂进去，用自然语言提问，回答**带引用出处、不凭空编造**。

> 与直接问 ChatGPT 的区别：ChatGPT 靠常识回答（可能编），它**只基于你喂的资料回答**，每句话都能追溯到来源。

## ✨ 特性

- **三级检索链路**：BM25 关键词 → + 向量语义（RRF 融合）→ CrossEncoder rerank 精排
- **Agent 自主决策**：由大模型判断"查本地知识库还是联网搜索"，而非写死规则
- **端到端评测**：不只测检索，还测最终回答的正确率、引用率与幻觉率
- **增量索引**：基于 Chroma，只向量化新增/改动的文档，无需每次全量重建
- **多格式入库**：md / txt / docx / pdf
- **本地模型**：embedding 与 rerank 本地部署，生成端可接任意 OpenAI 兼容 API

## 📊 效果数据

数据均来自本项目实测，评测脚本可复现。

### 检索评测（126 题，答案级判分）

判分要求命中「**含答案的那个具体片段**」，而非仅命中文档。

| 方法 | Recall@1 | Recall@3 | MRR |
|---|---|---|---|
| BM25 | 60.32% | 86.51% | 0.720 |
| 纯向量 | 59.52% | 81.75% | 0.697 |
| 混合（RRF） | 61.11% | 84.13% | 0.718 |
| **混合 + rerank** | **64.29%** | **86.51%** | **0.743** |

### 端到端评测（30 题，LLM-as-judge）

| 指标 | 结果 |
|---|---|
| **回答正确率**（≥2 分） | **93.33%** |
| 完全正确率（3 分） | 80.00% |
| **引用率** | **100%** |
| **幻觉率** | **0%** |

> 💡 一个反直觉的发现：检索 Recall@1 只有 64%，但回答正确率高达 93%。
> 因为一次返回 4 个片段，只要有 1 个命中，大模型就能组织出正确答案——
> **决定体验的是「召回全不全」(Recall@3)，不是「首条命中」(Recall@1)**。

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置：复制 .env.example 为 .env，填入你的 API Key
cp .env.example .env

# 3. 放文档到 data/docs/，然后导入（支持 --force 全量重建）
python ingest.py

# 4. 启动界面
python -m streamlit run app.py
```

> Windows 建议使用虚拟环境：`.venv\Scripts\python.exe`；若控制台中文乱码，运行时加 `-X utf8`。

## 🏗 系统架构

```
用户提问
   ↓
app.py（Streamlit 界面）
   ↓
agent.py —— 大模型决策：查本地库 / 联网搜索 / 直接回答
   ↓
tools.py
   ├─ search_knowledge_base → retriever.py（混合检索 + rerank）→ Chroma
   └─ search_web            → Tavily 联网搜索
   ↓
llm.py —— 基于检索片段生成回答（带引用）
```

| 模块 | 职责 |
|---|---|
| `agent.py` | Function Calling 工具循环（最多 6 轮） |
| `retriever.py` | 四种检索：BM25 / 向量 / 混合(RRF) / 混合+rerank |
| `bm25.py` | 手写 BM25 + jieba 分词 |
| `embedder.py` / `reranker.py` | 本地 bge-small-zh / bge-reranker-base |
| `store.py` | Chroma 持久化与增量更新 |
| `ingest.py` / `chunker.py` | 文档导入、多格式解析与切片 |

## 🔍 检索链路

| 阶段 | 做法 | 解决什么 |
|---|---|---|
| ① BM25 | 关键词精确匹配 | 专业术语、代码符号查得准 |
| ② 向量 | 语义相似度 | 换个说法也能找到 |
| ③ 混合（RRF） | 两种排名融合 | 兼顾精确与语义 |
| ④ + rerank | CrossEncoder 精排 | 排序更准，把正确答案顶到第 1 |

参数由实验确定：rerank 候选池扫描 5/8/10/15/20，实测 **5 最优**（候选过多反而引入干扰）。

## 📈 评测与优化

| 脚本 | 作用 |
|---|---|
| `eval.py` | 检索评测（126 题，答案级判分） |
| `eval_e2e.py` | 端到端评测（30 题，LLM-as-judge） |
| `tune.py` | 参数调优（融合权重、候选池） |
| `pytest` | 13 个自动化测试（快测 / 慢测分离） |

### 被数据否决的两个优化（负结果）

| 方案 | 检索层 | 端到端 | 决策 |
|---|---|---|---|
| 查询改写 | Recall@3 +7.14pt | 正确率持平（93.33%） | ❌ 不落地 |
| 增大 top_k | 召回 +4.76pt | 正确率持平，完全正确率反降 | ❌ 不落地 |

> 记录负结果是有意为之：**没有提升的优化就不该进系统**。

## ⚙️ 主要配置

复制 `.env.example` 为 `.env` 后按需修改：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | 必填，生成回答 |
| `TAVILY_API_KEY` | — | 联网搜索工具（可选） |
| `TOP_K` | 4 | 交给大模型的片段数（实测最优） |
| `CANDIDATE_K` | 5 | 喂给 rerank 的候选数（实测最优） |
| `ENABLE_RERANK` | true | 内存不足可设 false 降级 |
| `EMBED_MODEL` / `RERANK_MODEL` | bge 系列 | 模型名或本地目录 |

## 📁 项目结构

```
├── app.py / agent.py / tools.py / llm.py   界面与 Agent
├── retriever.py / bm25.py                  检索
├── embedder.py / reranker.py               本地模型
├── chunker.py / ingest.py / store.py       文档处理与存储
├── eval.py / eval_e2e.py / tune.py         评测与调优
├── tests/                                  自动化测试
└── data/                                   文档与索引（已 gitignore）
```



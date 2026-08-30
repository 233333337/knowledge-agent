"""BM25 关键词检索（手写实现 + jieba 分词）。

BM25 是 TF-IDF 的改进版，是关键词检索的经典基线。
这里手写实现（不依赖第三方 BM25 库），便于理解原理、也便于面试讲清楚。
"""
import math
from collections import defaultdict

import jieba


class BM25:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        # 预分词，建立倒排统计
        self.docs = [self._tokenize(d) for d in corpus]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.n, 1)

        self.df = defaultdict(int)
        for doc in self.docs:
            for term in set(doc):
                self.df[term] += 1

        # IDF：词越稀有，权重越高
        self.idf = {
            term: math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)
            for term, df in self.df.items()
        }

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [w for w in jieba.lcut(text) if w.strip()]

    def score(self, query: str) -> list[float]:
        """返回 query 对每个文档的 BM25 得分。"""
        q_terms = self._tokenize(query)
        scores = []
        for doc in self.docs:
            tf = defaultdict(int)
            for t in doc:
                tf[t] += 1
            dl = len(doc)
            s = 0.0
            for term in q_terms:
                idf = self.idf.get(term)
                if idf is None:
                    continue
                f = tf.get(term, 0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                s += idf * (f * (self.k1 + 1)) / denom
            scores.append(s)
        return scores

    def search(self, query: str, top_k: int = 3) -> list[tuple]:
        """返回 [(doc_index, score)]，按得分降序，仅保留得分 > 0 的。"""
        scores = self.score(query)
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [(i, scores[i]) for i in order if scores[i] > 0][:top_k]

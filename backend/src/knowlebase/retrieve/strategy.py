"""
检索域 — 合并策略与重排序策略

策略模式实现，通过配置切换。
"""

import math
import logging
from typing import Protocol

from knowlebase.core.config import settings
from knowlebase.retrieve.schema import SearchResultItem

logger = logging.getLogger(__name__)

# RRF 平滑常数
RRF_K = 60


# ==================== 合并策略 ====================

class MergeStrategy(Protocol):
    """合并策略接口"""

    def merge(
        self,
        path_results: list[list[tuple[str, float]]],
        weights: list[float],
    ) -> list[tuple[str, float]]:
        """接收三路 [(chunk_id, score), ...] 及归一化权重，返回合并排序后的 [(chunk_id, merged_score), ...]"""
        ...


class RRFMergeStrategy:
    """RRF（倒数秩融合）合并策略"""

    def merge(
        self,
        path_results: list[list[tuple[str, float]]],
        weights: list[float],
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for path_idx, path in enumerate(path_results):
            w = weights[path_idx]
            if w == 0:
                continue
            for rank, (chunk_id, _score) in enumerate(path):
                scores[chunk_id] = scores.get(chunk_id, 0) + w / (RRF_K + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class WeightedNormalizationMergeStrategy:
    """分数归一化加权合并策略"""

    def merge(
        self,
        path_results: list[list[tuple[str, float]]],
        weights: list[float],
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for path_idx, path in enumerate(path_results):
            w = weights[path_idx]
            if w == 0 or not path:
                continue
            raw_scores = [s for _cid, s in path]
            s_min = min(raw_scores)
            s_max = max(raw_scores)
            denom = s_max - s_min or 1.0
            for chunk_id, raw_score in path:
                norm = (raw_score - s_min) / denom
                scores[chunk_id] = scores.get(chunk_id, 0) + w * norm
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def get_merge_strategy() -> MergeStrategy:
    """根据配置创建合并策略实例"""
    strategy = settings.search_merge_strategy
    if strategy == "rrf":
        return RRFMergeStrategy()
    if strategy == "weighted_normalization":
        return WeightedNormalizationMergeStrategy()
    raise ValueError(f"无效的合并策略配置: {strategy}")


# ==================== 重排序策略 ====================

class RerankStrategy(Protocol):
    """重排序策略接口"""

    def rerank(
        self, items: list[SearchResultItem], query: str, top_k: int
    ) -> list[SearchResultItem]:
        """重排序后返回 top_k 条"""
        ...


class NoopRerankStrategy:
    """空实现 — 跳过重排序"""

    def rerank(
        self, items: list[SearchResultItem], query: str, top_k: int
    ) -> list[SearchResultItem]:
        return items[:top_k]


class CrossEncoderRerankStrategy:
    """Cross Encoder 重排序

    使用 sentence-transformers CrossEncoder 模型对 (query, chunk_text) 对精排。
    """

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return self._model

    def rerank(
        self, items: list[SearchResultItem], query: str, top_k: int
    ) -> list[SearchResultItem]:
        if not items:
            return []
        pairs = [(query, item.chunk_text) for item in items]
        scores = self.model.predict(pairs)
        scored = list(zip(items, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = []
        for item, score in scored[:top_k]:
            item.score = float(score)
            result.append(item)
        return result


class LLMRerankStrategy:
    """LLM 重排序

    通过 Higress 场景 rerank 调用 LLM 对候选列表精排。
    """

    def rerank(
        self, items: list[SearchResultItem], query: str, top_k: int
    ) -> list[SearchResultItem]:
        logger.warning("LLM 重排序暂未实现，回退为跳过重排序")
        return items[:top_k]


def get_rerank_strategy() -> RerankStrategy:
    """根据配置创建重排序策略实例"""
    strategy = settings.search_rerank_strategy
    if strategy == "none":
        return NoopRerankStrategy()
    if strategy == "cross_encoder":
        return CrossEncoderRerankStrategy()
    if strategy == "llm":
        return LLMRerankStrategy()
    raise ValueError(f"无效的重排序策略配置: {strategy}")

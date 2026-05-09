"""
EmbeddingService — 向量嵌入服务

基于 sentence-transformers + BAAI/bge-small-zh-v1.5 的离线嵌入。
单例模式，首次调用时加载模型。
"""

import logging
from typing import List

from sentence_transformers import SentenceTransformer

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量嵌入服务，包装 sentence-transformers 模型"""

    def __init__(self):
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(
                f"加载嵌入模型: {settings.embedding_model}, "
                f"device={settings.embedding_device}"
            )
            self._model = SentenceTransformer(
                settings.embedding_model,
                device=settings.embedding_device,
            )
            logger.info("嵌入模型加载完成")
        return self._model

    @property
    def dimension(self) -> int:
        return settings.embedding_dimension

    def encode(self, texts: List[str]) -> List[List[float]]:
        """对文本列表进行批量嵌入，返回向量列表"""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def encode_single(self, text: str) -> List[float]:
        """对单条文本进行嵌入"""
        return self.encode([text])[0]

    def count_tokens(self, text: str) -> int:
        """使用模型 tokenizer 计算文本的 token 数量"""
        tokens = self.model.tokenizer.encode(text)
        return len(tokens)


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

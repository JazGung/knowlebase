"""
ElasticsearchService — ES 全文检索索引服务

负责 document_chunk 索引的创建、文档写入和按文档清理。
"""

import logging
from typing import List, Dict

from elasticsearch import AsyncElasticsearch

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)

ES_INDEX_NAME = "document_chunk"

ES_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "keyword": {"type": "text", "analyzer": "standard"},
        }
    },
}


class ElasticsearchService:
    """ES 索引服务 — 管理 document_chunk 索引的 CRUD"""

    def __init__(self):
        self._client: AsyncElasticsearch | None = None

    @property
    def client(self) -> AsyncElasticsearch:
        if self._client is None:
            url = settings.elasticsearch_url
            kwargs = {"hosts": [url]}
            if settings.elasticsearch_username and settings.elasticsearch_password:
                kwargs["basic_auth"] = (
                    settings.elasticsearch_username,
                    settings.elasticsearch_password,
                )
            self._client = AsyncElasticsearch(**kwargs)
            logger.info(f"ES 客户端已创建: {url}")
        return self._client

    async def ensure_index(self) -> None:
        """确保索引存在，不存在则创建"""
        exists = await self.client.indices.exists(index=ES_INDEX_NAME)
        if not exists:
            await self.client.indices.create(index=ES_INDEX_NAME, body=ES_INDEX_MAPPING)
            logger.info(f"ES 索引已创建: {ES_INDEX_NAME}")

    async def index_chunks(self, chunks: List[Dict]) -> None:
        """批量写入分块到 ES（bulk）

        Args:
            chunks: [{"chunk_id": str, "document_id": str, "processed_text": str}, ...]
        """
        if not chunks:
            return
        await self.ensure_index()
        body = []
        for c in chunks:
            body.append({"index": {"_index": ES_INDEX_NAME, "_id": c["chunk_id"]}})
            body.append({"chunk_id": c["chunk_id"], "document_id": c["document_id"], "keyword": c["processed_text"]})
        resp = await self.client.bulk(body=body, refresh=True)
        if resp.get("errors"):
            error_items = [item for item in resp.get("items", []) if "error" in item.get("index", {})]
            logger.error(f"ES bulk 写入有错误: {error_items[:3]}")
            raise RuntimeError(f"ES bulk 写入失败: {error_items[:3]}")
        logger.debug(f"ES bulk 写入成功: {len(chunks)} 条")

    async def delete_by_document_id(self, document_id: str) -> None:
        """按文档ID删除所有相关记录"""
        try:
            await self.client.delete_by_query(
                index=ES_INDEX_NAME,
                body={"query": {"term": {"document_id": document_id}}},
                refresh=True,
            )
        except Exception as e:
            logger.warning(f"ES 按文档删除时出错（可能索引不存在）: {e}")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


_es_service: ElasticsearchService | None = None


def get_es_service() -> ElasticsearchService:
    global _es_service
    if _es_service is None:
        _es_service = ElasticsearchService()
    return _es_service

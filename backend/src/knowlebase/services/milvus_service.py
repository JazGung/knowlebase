"""
MilvusService — 向量数据库服务

负责 collection 的创建、向量写入和按文档清理。
"""

import logging
from typing import List, Dict

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "document_chunk"

# Milvus schema fields
FIELDS = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=settings.embedding_dimension),
]

SCHEMA = CollectionSchema(fields=FIELDS, description="文档分块向量库")

INDEX_PARAMS = {
    "metric_type": "IP",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128},
}


class MilvusService:
    """Milvus 向量服务 — 管理 document_chunk collection 的 CRUD"""

    def __init__(self):
        self._connected = False

    def _connect(self) -> None:
        if not self._connected:
            connections.connect(
                alias="default",
                host=settings.milvus_host,
                port=str(settings.milvus_port),
            )
            self._connected = True
            logger.info(f"Milvus 已连接: {settings.milvus_host}:{settings.milvus_port}")

    def ensure_collection(self) -> Collection:
        """确保 collection 存在并加载到内存"""
        self._connect()
        if not utility.has_collection(COLLECTION_NAME):
            collection = Collection(name=COLLECTION_NAME, schema=SCHEMA)
            collection.create_index(field_name="vector", index_params=INDEX_PARAMS)
            logger.info(f"Milvus collection 已创建: {COLLECTION_NAME}")
        else:
            collection = Collection(name=COLLECTION_NAME)
        collection.load()
        return collection

    def insert_vectors(self, entries: List[Dict]) -> None:
        """批量插入向量

        Args:
            entries: [{"chunk_id": str, "document_id": str, "vector": List[float]}, ...]
        """
        if not entries:
            return
        collection = self.ensure_collection()
        data = [
            [e["chunk_id"] for e in entries],
            [e["document_id"] for e in entries],
            [e["vector"] for e in entries],
        ]
        collection.insert(data)
        collection.flush()
        logger.debug(f"Milvus 写入成功: {len(entries)} 条")

    def delete_by_document_id(self, document_id: str) -> None:
        """按文档ID删除向量"""
        self._connect()
        if not utility.has_collection(COLLECTION_NAME):
            return
        collection = Collection(name=COLLECTION_NAME)
        collection.load()
        expr = f'document_id == "{document_id}"'
        collection.delete(expr)
        collection.flush()
        logger.debug(f"Milvus 删除完成: document_id={document_id}")

    def close(self) -> None:
        if self._connected:
            connections.disconnect("default")
            self._connected = False


_milvus_service: MilvusService | None = None


def get_milvus_service() -> MilvusService:
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService()
    return _milvus_service

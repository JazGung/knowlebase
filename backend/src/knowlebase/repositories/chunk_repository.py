"""
DocumentChunkRepository — 文档分块持久化操作

一对一管理 DocumentChunk 领域对象的查询、插入、删除。
"""

import logging
from typing import List

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.chunk import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentChunkRepository:
    """文档分块 Repository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_insert(self, chunks: List[DocumentChunk]) -> None:
        """批量插入分块记录"""
        self.db.add_all(chunks)
        await self.db.flush()

    async def delete_by_document_id(self, document_id: int) -> None:
        """按文档ID删除所有分块"""
        await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

    async def update_enabled_by_document_id(self, document_id: int, enabled: bool) -> None:
        """按文档ID批量更新分块的 enabled 字段"""
        await self.db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .values(enabled=enabled)
        )

    async def list_by_document_id(self, document_id: int) -> List[DocumentChunk]:
        """查询文档的所有分块，按 chunk_index 排序"""
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

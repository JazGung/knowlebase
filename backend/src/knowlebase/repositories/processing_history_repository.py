"""
ProcessingHistoryRepository — 处理历史持久化操作

一对一管理 DocumentProcessingHistory 领域对象的查询、插入、更新。
"""

import logging
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.document import DocumentProcessingHistory

logger = logging.getLogger(__name__)


class ProcessingHistoryRepository:
    """处理历史 Repository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_processing_id(self, processing_id: str) -> Optional[DocumentProcessingHistory]:
        """通过 processing_id 查询"""
        result = await self.db.execute(
            select(DocumentProcessingHistory).where(
                DocumentProcessingHistory.processing_id == processing_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_document_id(
        self, document_id: int, order_desc: bool = True
    ) -> List[DocumentProcessingHistory]:
        """通过 document_id 查询所有处理历史"""
        query = select(DocumentProcessingHistory).where(
            DocumentProcessingHistory.document_id == document_id
        )
        order_col = DocumentProcessingHistory.attempt_no
        if order_desc:
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_by_document_id(
        self, document_id: int
    ) -> Optional[DocumentProcessingHistory]:
        """查询最新的处理历史记录"""
        result = await self.db.execute(
            select(DocumentProcessingHistory)
            .where(DocumentProcessingHistory.document_id == document_id)
            .order_by(DocumentProcessingHistory.attempt_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_active_processing(self, document_id: int) -> bool:
        """检查是否有正在进行的处理"""
        result = await self.db.execute(
            select(DocumentProcessingHistory).where(
                DocumentProcessingHistory.document_id == document_id,
                DocumentProcessingHistory.status == "processing",
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_max_attempt_no(self, document_id: int) -> int:
        """获取最大处理次数"""
        result = await self.db.execute(
            select(
                func.coalesce(func.max(DocumentProcessingHistory.attempt_no), 0)
            ).where(DocumentProcessingHistory.document_id == document_id)
        )
        return result.scalar_one()

    async def add(self, history: DocumentProcessingHistory) -> DocumentProcessingHistory:
        """新增处理历史记录"""
        self.db.add(history)
        await self.db.flush()
        return history

    async def update(self, history: DocumentProcessingHistory) -> None:
        """更新处理历史记录"""
        self.db.add(history)
        await self.db.flush()

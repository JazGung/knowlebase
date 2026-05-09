"""
DocumentRepository — 文档持久化操作

一对一管理 Document 领域对象的查询、插入、更新。
"""

import logging
from typing import Optional, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.document import Document

logger = logging.getLogger(__name__)


class DocumentRepository:
    """文档 Repository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: int) -> Optional[Document]:
        """通过主键查询"""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Optional[Document]:
        """通过文件哈希查询"""
        result = await self.db.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def find_duplicates(self, hashes: List[str]) -> List[Document]:
        """查询给定哈希列表中已存在的文档"""
        if not hashes:
            return []
        result = await self.db.execute(
            select(Document).where(Document.file_hash.in_(hashes))
        )
        return list(result.scalars().all())

    async def list_with_filters(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ):
        """分页查询文档列表"""
        query = select(Document)

        if status:
            query = query.where(Document.status == status)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Document.original_filename.ilike(search_pattern),
                    Document.title.ilike(search_pattern),
                )
            )

        # 总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # 排序
        sort_columns = {
            "created_at": Document.created_at,
            "updated_at": Document.updated_at,
            "file_size": Document.file_size,
            "title": Document.title,
        }
        order_col = sort_columns.get(sort_by, Document.created_at)
        if order == "asc":
            query = query.order_by(order_col.asc())
        else:
            query = query.order_by(order_col.desc())

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def add(self, doc: Document) -> Document:
        """新增文档记录"""
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def update(self, doc: Document) -> None:
        """更新文档记录（由调用方负责 commit）"""
        self.db.add(doc)
        await self.db.flush()

    async def get_all_hashes(self) -> set:
        """获取所有文档的文件哈希集合"""
        result = await self.db.execute(select(Document.file_hash))
        return {row[0] for row in result.all()}

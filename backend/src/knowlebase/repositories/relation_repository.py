"""RelationRepository — 文档-版本关联持久化操作"""

import logging
from typing import List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.models.document_version_relation import DocumentVersionRelation
from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion

logger = logging.getLogger(__name__)


class RelationRepository:
    """文档-版本关联 Repository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_base_query(self) -> Select:
        return (
            select(
                DocumentVersionRelation.id,
                DocumentVersionRelation.document_id,
                Document.original_filename.label("document_name"),
                DocumentVersionRelation.version_id,
                KnowledgeBaseVersion.version_name.label("version_name"),
                DocumentVersionRelation.relation_type,
                DocumentVersionRelation.status,
                DocumentVersionRelation.created_at,
                func.count(DocumentProcessingHistory.id).label("attempt_count"),
            )
            .outerjoin(Document, Document.id == DocumentVersionRelation.document_id)
            .outerjoin(
                KnowledgeBaseVersion,
                KnowledgeBaseVersion.id == DocumentVersionRelation.version_id,
            )
            .outerjoin(
                DocumentProcessingHistory,
                DocumentProcessingHistory.relation_id == DocumentVersionRelation.id,
            )
            .group_by(
                DocumentVersionRelation.id,
                Document.original_filename,
                KnowledgeBaseVersion.version_name,
            )
        )

    async def list_with_filters(
        self,
        page: int = 1,
        page_size: int = 20,
        document_id: int | None = None,
        version_id: int | None = None,
    ) -> Tuple[List[dict], int]:
        query = self._build_base_query()

        if document_id is not None:
            query = query.where(DocumentVersionRelation.document_id == document_id)
        if version_id is not None:
            query = query.where(DocumentVersionRelation.version_id == version_id)

        # Count total
        count_query = select(func.count()).select_from(DocumentVersionRelation)
        if document_id is not None:
            count_query = count_query.where(DocumentVersionRelation.document_id == document_id)
        if version_id is not None:
            count_query = count_query.where(DocumentVersionRelation.version_id == version_id)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Paginated data
        query = query.order_by(DocumentVersionRelation.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        rows = result.all()

        data = [
            {
                "id": row.id,
                "document_id": row.document_id,
                "document_name": row.document_name,
                "version_id": row.version_id,
                "version_name": row.version_name,
                "relation_type": row.relation_type,
                "status": row.status,
                "attempt_count": row.attempt_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

        return data, total

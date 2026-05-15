"""
文档-版本关联查询服务
"""

import logging
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.repositories.relation_repository import RelationRepository

logger = logging.getLogger(__name__)


class RelationService:
    """关联查询服务"""

    async def query_relations(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        document_id: Optional[int] = None,
        version_id: Optional[int] = None,
    ) -> Dict:
        """文档-版本关联查询"""
        repo = RelationRepository(db)
        data, total = await repo.list_with_filters(page, page_size, document_id, version_id)
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }


_relation_service_instance: Optional[RelationService] = None


def get_relation_service() -> RelationService:
    global _relation_service_instance
    if _relation_service_instance is None:
        _relation_service_instance = RelationService()
    return _relation_service_instance

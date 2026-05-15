"""
文档-版本关联查询 API 端点
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.resource.relation.service import get_relation_service, RelationService
from knowlebase.schemas.document import BaseResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/list",
    response_model=BaseResponse,
    summary="文档-版本关联查询",
    tags=["业务资源域-关联查询"],
)
async def query_relations(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    document_id: Optional[int] = Query(default=None, description="按文档ID过滤"),
    version_id: Optional[int] = Query(default=None, description="按版本ID过滤"),
    db: AsyncSession = Depends(get_db),
    relation_svc: RelationService = Depends(get_relation_service),
):
    """分页查询文档-版本关联记录"""
    try:
        result = await relation_svc.query_relations(db, page, page_size, document_id, version_id)
        return BaseResponse(description="查询成功", content=result)
    except Exception as e:
        logger.error(f"关联查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "关联查询失败", "content": None}
        )

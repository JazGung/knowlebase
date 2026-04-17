"""文档处理 API 端点

包含文档解析、分块、处理状态查询等 API 端点
"""

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse as FastAPIJSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.models.document import DocumentProcessingHistory
from knowlebase.admin.processing.service import get_processing_service, ProcessingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/trigger",
    summary="手动触发文档处理",
    description="手动触发指定文档的解析、分块处理流程",
    tags=["文档处理"]
)
async def trigger_processing(
    document_id: int = Query(..., description="文档 ID"),
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    try:
        import asyncio
        import uuid

        processing_id = f"proc_{uuid.uuid4().hex[:12]}"

        asyncio.create_task(
            processing_svc.process_document(db, document_id, processing_id)
        )

        return FastAPIJSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "文档处理已触发",
                "data": {
                    "document_id": str(document_id),
                    "processing_id": processing_id,
                },
            },
        )

    except Exception as e:
        logger.error(f"触发文档处理失败: {e}", exc_info=True)
        return FastAPIJSONResponse(
            status_code=200,
            content={"code": 500, "message": "触发文档处理失败", "detail": str(e)},
        )


@router.get(
    "/status",
    summary="查询处理状态",
    description="根据 processing_id 查询文档处理状态和进度",
    tags=["文档处理"]
)
async def get_processing_status(
    processing_id: str = Query(..., description="处理任务 ID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(DocumentProcessingHistory).where(
            DocumentProcessingHistory.processing_id == processing_id
        )
        result = await db.execute(query)
        proc = result.scalar_one_or_none()

        if not proc:
            return FastAPIJSONResponse(
                status_code=200,
                content={"code": 404, "message": "处理记录不存在"},
            )

        return FastAPIJSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": "查询成功",
                "data": {
                    "processing_id": proc.processing_id,
                    "document_id": str(proc.document_id),
                    "status": proc.status,
                    "current_stage": proc.current_stage,
                    "progress": proc.progress,
                    "started_at": proc.started_at.isoformat() if proc.started_at else None,
                    "completed_at": proc.completed_at.isoformat() if proc.completed_at else None,
                    "error_message": proc.error_message,
                    "result": proc.result,
                },
            },
        )

    except Exception as e:
        logger.error(f"查询处理状态失败: {e}", exc_info=True)
        return FastAPIJSONResponse(
            status_code=200,
            content={"code": 500, "message": "查询处理状态失败", "detail": str(e)},
        )

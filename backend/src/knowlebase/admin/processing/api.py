"""
文档处理 API 端点

包含处理状态查询、阶段结果详情、处理过程视图、SSE 进度流等 API 端点
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.admin.processing.service import get_processing_service, ProcessingService
from knowlebase.events import get_event_bus
from knowlebase.schemas.document import BaseResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/status/{processing_id}",
    response_model=BaseResponse,
    summary="处理状态查询",
    tags=["文档处理"]
)
async def status(
    processing_id: str,
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    """查询文档处理状态，包含各阶段元信息"""
    try:
        result = await processing_svc.get_processing_status(db, processing_id)

        if not result:
            return JSONResponse(
                status_code=200,
                content={"code": "404001", "description": "处理记录不存在", "content": None}
            )

        return BaseResponse(
            description="处理状态查询成功",
            content=result
        )

    except Exception as e:
        logger.error(f"处理状态查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "处理状态查询失败", "content": None}
        )


@router.get(
    "/stage/{processing_id}/{stage_name}",
    response_model=BaseResponse,
    summary="阶段结果详情",
    tags=["文档处理"]
)
async def stage_result(
    processing_id: str,
    stage_name: str,
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    """查询指定处理阶段的中间结果详情，从 MinIO 读取 JSON"""
    try:
        result = await processing_svc.get_stage_result(db, processing_id, stage_name)

        if not result:
            return JSONResponse(
                status_code=200,
                content={"code": "404001", "description": "阶段结果不存在", "content": None}
            )

        return BaseResponse(
            description="阶段结果查询成功",
            content=result
        )

    except Exception as e:
        logger.error(f"阶段结果查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "阶段结果查询失败", "content": None}
        )


@router.get(
    "/view",
    response_model=BaseResponse,
    summary="处理过程视图",
    tags=["文档处理"]
)
async def view(
    relation_ids: str = Query(..., description="逗号分隔的关联记录ID列表"),
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    """查询多个文档的处理过程，返回多 tab 视图数据"""
    try:
        rel_id_list = [int(rid.strip()) for rid in relation_ids.split(",") if rid.strip()]
        if not rel_id_list:
            return JSONResponse(
                status_code=200,
                content={"code": "400004", "description": "relation_ids 不能为空", "content": None}
            )

        result = await processing_svc.get_processing_view(db, rel_id_list)

        return BaseResponse(
            description="处理过程视图查询成功",
            content=result
        )

    except Exception as e:
        logger.error(f"处理过程视图查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "处理过程视图查询失败", "content": None}
        )


@router.get(
    "/stream/{processing_id}",
    summary="处理进度 SSE 流",
    tags=["文档处理"]
)
async def stream(
    processing_id: str,
    request: Request,
):
    """SSE 实时推送处理进度，每个阶段完成时推送事件"""
    event_bus = get_event_bus()

    async def event_generator():
        try:
            async for event in event_bus.subscribe(processing_id=processing_id):
                if await request.is_disconnected():
                    break
                yield f"data: {event.to_json()}\n\n"
                # 终态检查：失败或最后一阶段完成时关闭流
                if event.status == "failed" or event.stage_name == "stored":
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get(
    "/relation/list",
    response_model=BaseResponse,
    summary="文档-版本关联查询",
    tags=["文档处理"]
)
async def query_relations(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    document_id: int = Query(default=None, description="按文档ID过滤"),
    version_id: int = Query(default=None, description="按版本ID过滤"),
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    """分页查询文档-版本关联记录（DEG 4.4）"""
    try:
        result = await processing_svc.query_relations(db, page, page_size, document_id, version_id)
        return BaseResponse(description="查询成功", content=result)
    except Exception as e:
        logger.error(f"关联查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "关联查询失败", "content": None}
        )


@router.get(
    "/history/list",
    response_model=BaseResponse,
    summary="处理记录查询",
    tags=["文档处理"]
)
async def query_history(
    relation_id: int = Query(..., ge=1, description="关联记录ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    processing_svc: ProcessingService = Depends(get_processing_service),
):
    """分页查询指定关联记录的处理历史（DEG 4.6）"""
    try:
        result = await processing_svc.query_history(db, relation_id, page, page_size)
        return BaseResponse(description="查询成功", content=result)
    except Exception as e:
        logger.error(f"处理记录查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": "500000", "description": "处理记录查询失败", "content": None}
        )

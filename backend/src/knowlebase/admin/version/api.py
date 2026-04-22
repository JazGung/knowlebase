"""知识库版本管理API端点

包含版本列表、创建、启用、停用等API端点
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.schemas.version import (
    VersionListQuery,
    VersionCreateRequest,
    VersionEnableRequest,
    VersionDisableRequest,
    VersionDeleteRequest,
    VersionListSuccessResponse,
    VersionDetailSuccessResponse,
    VersionCreateSuccessResponse,
    VersionActionSuccessResponse,
    SuccessResponse,
)
from knowlebase.admin.version.service import (
    VersionService,
    get_version_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/list",
    response_model=VersionListSuccessResponse,
    summary="版本列表查询",
    description="查询知识库版本列表，支持分页和状态过滤",
    tags=["知识库版本管理"]
)
async def list_versions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: Optional[str] = Query(None, alias="status", description="状态过滤"),
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        from knowlebase.schemas.version import VersionStatus

        status_enum = None
        if status_filter:
            try:
                status_enum = VersionStatus(status_filter)
            except ValueError:
                return JSONResponse(
                    status_code=200,
                    content={"code": 400, "message": f"无效的状态值: {status_filter}"}
                )

        versions, total = await version_service.list_versions(
            db, page=page, page_size=page_size, status_filter=status_enum
        )

        return VersionListSuccessResponse(
            code=0,
            message="版本列表查询成功",
            data={
                "versions": [v.to_dict() for v in versions],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    except Exception as e:
        logger.error(f"版本列表查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本列表查询失败", "detail": str(e)}
        )


@router.get(
    "/detail",
    response_model=VersionDetailSuccessResponse,
    summary="版本详情查询",
    description="查询知识库版本详情",
    tags=["知识库版本管理"]
)
async def get_version_detail(
    version_id: str = Query(..., description="版本ID（如 v20260422_103000）"),
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        version = await version_service.get_version_detail(db, version_id)
        if not version:
            return JSONResponse(
                status_code=200,
                content={"code": 404, "message": "版本不存在", "detail": f"version_id: {version_id}"}
            )

        return VersionDetailSuccessResponse(
            code=0,
            message="版本详情查询成功",
            data={"version": version.to_dict()}
        )

    except Exception as e:
        logger.error(f"版本详情查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本详情查询失败", "detail": str(e)}
        )


@router.post(
    "/create",
    response_model=VersionCreateSuccessResponse,
    summary="创建重建版本",
    description="创建新的知识库重建版本",
    tags=["知识库版本管理"]
)
async def create_version(
    request: VersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        version = await version_service.create_version(
            db, created_by=request.created_by
        )

        return VersionCreateSuccessResponse(
            code=0,
            message="版本创建成功",
            data={
                "version_id": version.version_id,
                "status": version.status,
            }
        )

    except ValueError as e:
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": str(e)}
        )
    except Exception as e:
        logger.error(f"版本创建失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本创建失败", "detail": str(e)}
        )


@router.put(
    "/enable",
    response_model=VersionActionSuccessResponse,
    summary="启用版本",
    description="启用知识库版本，使其成为当前检索可见的版本",
    tags=["知识库版本管理"]
)
async def enable_version(
    request: VersionEnableRequest,
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        old_version, new_version = await version_service.enable_version(
            db, version_id=request.version_id
        )

        result_data = {
            "version_id": new_version.version_id,
            "status": new_version.status,
        }
        if old_version:
            result_data["previous_version"] = old_version.version_id

        return VersionActionSuccessResponse(
            code=0,
            message="版本启用成功",
            data=result_data
        )

    except ValueError as e:
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": str(e)}
        )
    except Exception as e:
        logger.error(f"版本启用失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本启用失败", "detail": str(e)}
        )


@router.put(
    "/disable",
    response_model=VersionActionSuccessResponse,
    summary="停用版本",
    description="停用知识库版本",
    tags=["知识库版本管理"]
)
async def disable_version(
    request: VersionDisableRequest,
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        version = await version_service.disable_version(
            db, version_id=request.version_id
        )

        return VersionActionSuccessResponse(
            code=0,
            message="版本停用成功",
            data={
                "version_id": version.version_id,
                "status": version.status,
            }
        )

    except ValueError as e:
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": str(e)}
        )
    except Exception as e:
        logger.error(f"版本停用失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本停用失败", "detail": str(e)}
        )

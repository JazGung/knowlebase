"""知识库版本管理API端点

包含版本列表、新建、构建、启用等API端点
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
    VersionBuildRequest,
    VersionEnableRequest,
    VersionListSuccessResponse,
    VersionCreateSuccessResponse,
    VersionActionSuccessResponse,
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


@router.post(
    "/create",
    response_model=VersionCreateSuccessResponse,
    summary="版本新建",
    description="创建新版本记录，状态初始化为 初始化",
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
                "version_name": version.version_name,
                "status": version.status,
            }
        )

    except Exception as e:
        logger.error(f"版本创建失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本创建失败", "detail": str(e)}
        )


@router.post(
    "/build",
    response_model=VersionActionSuccessResponse,
    summary="版本构建",
    description="触发知识库构建，遍历所有已启用文档执行处理流水线",
    tags=["知识库版本管理"]
)
async def build_version(
    request: VersionBuildRequest,
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        version = await version_service.build_version(
            db, version_name=request.version_name
        )

        return VersionActionSuccessResponse(
            code=0,
            message="版本构建已触发",
            data={
                "version_name": version.version_name,
                "status": version.status,
            }
        )

    except ValueError as e:
        return JSONResponse(
            status_code=200,
            content={"code": 400, "message": str(e)}
        )
    except Exception as e:
        logger.error(f"版本构建失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "版本构建失败", "detail": str(e)}
        )


@router.put(
    "/enable",
    response_model=VersionActionSuccessResponse,
    summary="版本启用",
    description="启用指定版本，自动将当前启用版本改为已禁用",
    tags=["知识库版本管理"]
)
async def enable_version(
    request: VersionEnableRequest,
    db: AsyncSession = Depends(get_db),
    version_service: VersionService = Depends(get_version_service),
):
    try:
        old_version, new_version = await version_service.enable_version(
            db, version_name=request.version_name
        )

        result_data = {
            "version_name": new_version.version_name,
            "status": new_version.status,
        }
        if old_version:
            result_data["previous_version"] = old_version.version_name

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

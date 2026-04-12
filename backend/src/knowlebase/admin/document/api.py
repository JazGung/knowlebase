"""
文档管理API端点

包含文档上传、管理、查询等API端点
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.schemas.document import (
    FileCheckRequest,
    FileCheckSuccessResponse,
    DocumentUploadSuccessResponse,
    DocumentUploadRequestMetadata,
    IntegrityValidationErrorResponse,
    DocumentListQuery,
    DocumentDetailSuccessResponse,
    EnableDisableDocumentRequest,
    ReprocessDocumentRequest,
    ReprocessDocumentSuccessResponse,
    SuccessResponse,
    ErrorResponse,
)
from knowlebase.admin.document.service import (
    get_upload_service,
    UploadService,
    get_document_service,
    DocumentService,
)

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()


@router.post(
    "/check",
    response_model=FileCheckSuccessResponse,
    summary="检查文件重复性",
    description="批量检查文件哈希是否与后台已有文件重复",
    tags=["文档管理"]
)
async def check_file_duplicates(
    request: FileCheckRequest,
    db: AsyncSession = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service)
):
    try:
        logger.info(f"重复性校验请求: {len(request.files)} 个文件")

        duplicate_files = await upload_service.batch_check_duplicates(
            db,
            [{"filename": item.filename, "hash": item.hash} for item in request.files]
        )

        return FileCheckSuccessResponse(
            code=0,
            message="重复性校验完成",
            data={"duplicate_files": duplicate_files}
        )

    except Exception as e:
        logger.error(f"重复性校验失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "重复性校验失败", "detail": str(e)}
        )


@router.post(
    "/upload",
    response_model=DocumentUploadSuccessResponse,
    responses={
        400: {"model": IntegrityValidationErrorResponse},
        200: {"model": DocumentUploadSuccessResponse},
    },
    summary="单文件上传",
    description="单个文件上传接口，包含完整性验证",
    tags=["文档管理"]
)
async def upload_document(
    file: UploadFile = File(..., description="文件内容"),
    hash: str = Form(..., description="文件的MD5哈希值（32位十六进制字符串）"),
    title: Optional[str] = Form(None, description="文档标题"),
    description: Optional[str] = Form(None, description="文档描述"),
    category: Optional[str] = Form(None, description="文档分类"),
    tags: Optional[str] = Form(None, description="逗号分隔的标签"),
    db: AsyncSession = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service)
):
    try:
        logger.info(f"文件上传请求: {file.filename}, hash: {hash}")

        metadata = {
            "title": title,
            "description": description,
            "category": category,
            "tag": tags
        }

        upload_result = await upload_service.process_upload(
            db=db,
            file=file,
            provided_hash=hash,
            metadata=metadata,
            user_id=None
        )

        if upload_result.get("duplicate", False):
            return DocumentUploadSuccessResponse(
                code=0,
                message="文件已存在",
                data={
                    "document_id": upload_result["document_id"],
                    "filename": upload_result["filename"],
                    "original_filename": upload_result["original_filename"],
                    "file_hash": upload_result["file_hash"],
                    "file_size": upload_result["file_size"],
                    "status": "duplicate",
                    "processing_id": None,
                    "processing_number": 1,
                    "progress_stream_url": None
                }
            )

        return DocumentUploadSuccessResponse(
            code=0,
            message="文档上传成功",
            data={
                "document_id": upload_result["document_id"],
                "filename": upload_result["filename"],
                "original_filename": upload_result["original_filename"],
                "file_hash": upload_result["file_hash"],
                "file_size": upload_result["file_size"],
                "status": upload_result["status"],
                "processing_id": upload_result["processing_id"],
                "processing_number": upload_result["processing_number"],
                "progress_stream_url": upload_result["progress_stream_url"]
            }
        )

    except Exception as e:
        logger.error(f"文件上传失败: {file.filename} - {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文件上传失败", "detail": str(e)}
        )


@router.get(
    "/list",
    response_model=SuccessResponse,
    summary="文档列表查询",
    description="查询文档列表，支持分页、过滤、搜索、排序",
    tags=["文档管理"]
)
async def get_document_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: Optional[str] = Query(None, alias="status", description="状态过滤"),
    enabled: Optional[bool] = Query(None, description="是否启用过滤"),
    category: Optional[str] = Query(None, description="分类过滤"),
    search: Optional[str] = Query(None, description="关键字搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        query_params = DocumentListQuery(
            page=page,
            page_size=page_size,
            status=status_filter,
            enabled=enabled,
            category=category,
            search=search,
            sort_by=sort_by,
            order=order
        )

        result = await document_service.get_document_list(db, query_params)

        return SuccessResponse(
            code=0,
            message="文档列表查询成功",
            data=result
        )

    except Exception as e:
        logger.error(f"文档列表查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文档列表查询失败", "detail": str(e)}
        )


@router.get(
    "/detail",
    response_model=DocumentDetailSuccessResponse,
    summary="文档详情查询",
    description="查询文档详情，包含处理历史记录",
    tags=["文档管理"]
)
async def get_document_detail(
    document_id: str = Query(..., description="文档ID"),
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        result = await document_service.get_document_detail(db, document_id)

        if not result:
            return JSONResponse(
                status_code=200,
                content={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"}
            )

        return DocumentDetailSuccessResponse(
            code=0,
            message="文档详情查询成功",
            data=result
        )

    except Exception as e:
        logger.error(f"文档详情查询失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文档详情查询失败", "detail": str(e)}
        )


@router.put(
    "/enable",
    response_model=SuccessResponse,
    summary="启用文档",
    description="启用文档，使其可用于知识库重建和检索",
    tags=["文档管理"]
)
async def enable_document(
    request: EnableDisableDocumentRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        await document_service.enable_document(db, request.document_id)

        return SuccessResponse(
            code=0,
            message="文档启用成功",
            data={"document_id": request.document_id}
        )

    except Exception as e:
        logger.error(f"文档启用失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文档启用失败", "detail": str(e)}
        )


@router.put(
    "/disable",
    response_model=SuccessResponse,
    summary="停用文档",
    description="停用文档，使其不参与知识库重建和检索",
    tags=["文档管理"]
)
async def disable_document(
    request: EnableDisableDocumentRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        await document_service.disable_document(db, request.document_id)

        return SuccessResponse(
            code=0,
            message="文档停用成功",
            data={"document_id": request.document_id}
        )

    except Exception as e:
        logger.error(f"文档停用失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文档停用失败", "detail": str(e)}
        )


@router.post(
    "/reprocess",
    response_model=ReprocessDocumentSuccessResponse,
    summary="重新处理文档",
    description="重新处理文档，触发文档解析、分块、向量化等处理流程",
    tags=["文档管理"]
)
async def reprocess_document(
    request: ReprocessDocumentRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        result = await document_service.reprocess_document(
            db,
            request.document_id,
            request.force_reprocess
        )

        return ReprocessDocumentSuccessResponse(
            code=0,
            message="文档重新处理已发起",
            data=result
        )

    except Exception as e:
        logger.error(f"文档重新处理失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"code": 500, "message": "文档重新处理失败", "detail": str(e)}
        )

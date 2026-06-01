"""
文档管理API端点

包含文档上传、管理、查询等API端点
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.db.session import get_db
from knowlebase.schemas.document import (
    FileCheckRequest,
    DocumentListQuery,
    EnableDisableDocumentRequest,
    ProcessingTriggerRequest,
    BaseResponse,
    BatchResult,
)
from knowlebase.schemas.resource_errors import ResourceErrorCode
from knowlebase.schemas.errors import BusinessError, UnifiedResponse
from knowlebase.resource.document.service import (
    get_upload_service,
    UploadService,
    get_document_service,
    DocumentService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/check",
    summary="文件重复性校验",
    tags=["文档管理"]
)
async def check(
    request: FileCheckRequest,
    db: AsyncSession = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service)
):
    """批量检查文件哈希是否与已有文件重复"""
    response = UnifiedResponse()
    try:
        logger.info(f"重复性校验请求: {len(request.files)} 个文件")

        duplicates = await upload_service.batch_check_duplicates(
            db,
            [{"filename": item.filename, "hash": item.hash} for item in request.files]
        )
        response.ok({"duplicates": duplicates})

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"重复性校验失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()


@router.post(
    "/upload",
    summary="单文件上传",
    tags=["文档管理"]
)
async def upload(
    file: UploadFile = File(..., description="文件内容"),
    hash: str = Form(..., description="文件的MD5哈希值"),
    title: Optional[str] = Form(None, description="文档标题"),
    db: AsyncSession = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service)
):
    """单文件上传，包含完整性验证"""
    response = UnifiedResponse()
    try:
        logger.info(f"文件上传请求: {file.filename}, hash: {hash}")

        metadata = {"title": title}

        upload_result = await upload_service.process_upload(
            db=db,
            file=file,
            provided_hash=hash,
            metadata=metadata,
            user_id=None
        )
        response.ok(upload_result)

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {file.filename} - {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DOCUMENT_SAVE_FAILED, str(e)))

    return response.to_json()


@router.get(
    "/list",
    summary="文档列表分页查询",
    tags=["文档管理"]
)
async def query(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="启用状态过滤（enabled/disabled）"),
    search: Optional[str] = Query(None, description="关键字搜索"),
    sort_by: str = Query("created_at", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    """查询文档列表，支持分页、过滤、搜索、排序"""
    response = UnifiedResponse()
    try:
        query_params = DocumentListQuery(
            page=page,
            page_size=page_size,
            status=status,
            search=search,
            sort_by=sort_by,
            order=order
        )

        result = await document_service.get_document_list(db, query_params)
        response.ok(result)

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"文档列表查询失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()


@router.get(
    "/detail",
    summary="文档详情查询",
    tags=["文档管理"]
)
async def detail(
    document_id: str = Query(..., description="文档ID"),
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    """查询文档详情，包含处理历史记录"""
    response = UnifiedResponse()
    try:
        result = await document_service.get_document_detail(db, document_id)

        if not result:
            raise BusinessError(ResourceErrorCode.DOCUMENT_NOT_FOUND, "文档不存在")

        response.ok(result)

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"文档详情查询失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()


@router.put(
    "/enable",
    summary="文档启用",
    tags=["文档管理"]
)
async def enable(
    request: EnableDisableDocumentRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    """批量启用文档"""
    response = UnifiedResponse()
    try:
        results = []
        for doc_id in request.document_ids:
            try:
                await document_service.enable_document(db, str(doc_id))
                results.append(BatchResult(id=str(doc_id), status="success"))
            except BusinessError as e:
                results.append(BatchResult(id=str(doc_id), status="failed", reason=e.description))
            except Exception as e:
                logger.error(f"启用文档 {doc_id} 失败: {e}")
                results.append(BatchResult(id=str(doc_id), status="failed", reason=str(e)))

        response.ok({"results": [r.model_dump() for r in results]})

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"文档启用失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()


@router.put(
    "/disable",
    summary="文档停用",
    tags=["文档管理"]
)
async def disable(
    request: EnableDisableDocumentRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    """批量停用文档"""
    response = UnifiedResponse()
    try:
        results = []
        for doc_id in request.document_ids:
            try:
                await document_service.disable_document(db, str(doc_id))
                results.append(BatchResult(id=str(doc_id), status="success"))
            except BusinessError as e:
                results.append(BatchResult(id=str(doc_id), status="failed", reason=e.description))
            except Exception as e:
                logger.error(f"停用文档 {doc_id} 失败: {e}")
                results.append(BatchResult(id=str(doc_id), status="failed", reason=str(e)))

        response.ok({"results": [r.model_dump() for r in results]})

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"文档停用失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()


@router.post(
    "/process",
    summary="文档处理",
    tags=["文档管理"]
)
async def process(
    request: ProcessingTriggerRequest,
    db: AsyncSession = Depends(get_db),
    document_service: DocumentService = Depends(get_document_service)
):
    """批量触发文档处理，启动解析、分块、向量化等处理流水线（DEG 4.10）"""
    response = UnifiedResponse()
    try:
        logger.info(f"批量处理请求: {len(request.document_ids)} 个文档")

        results = await document_service.process_documents(
            db,
            request.document_ids
        )
        response.ok({"results": [r.model_dump() for r in results]})

    except BusinessError:
        raise
    except Exception as e:
        logger.error(f"触发文档处理失败: {e}", exc_info=True)
        response.error(BusinessError(ResourceErrorCode.DATABASE_UNAVAILABLE, str(e)))

    return response.to_json()

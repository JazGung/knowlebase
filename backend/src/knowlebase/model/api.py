"""
模型域 API — /model/*

POST /model/parsing  — 文档解析
POST /model/embedding — 文本向量化
"""

import logging

from fastapi import APIRouter, Request

from knowlebase.schemas.model import (
    ParseRequest,
    EmbeddingRequest,
    ModelErrorCode,
)
from knowlebase.schemas.errors import BusinessError, UnifiedResponse
from knowlebase.model.service import run_parsing, run_embedding

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/parsing",
    summary="文档解析",
)
async def parse(request: Request, body: ParseRequest):
    """解析 PDF/Word 文档为结构化内容"""
    response = UnifiedResponse()
    try:
        result = await run_parsing(
            file_content_b64=body.file_content,
            file_format=body.file_format,
            file_name=body.file_name,
        )
        response.ok(result)

    except BusinessError as e:
        response.error(e)
    except Exception as e:
        logger.error(f"文档解析失败: {e}", exc_info=True)
        response.error(BusinessError(ModelErrorCode.INTERNAL_ERROR, str(e)))

    return response.to_json()


@router.post(
    "/embedding",
    summary="文本向量化",
)
async def embed(request: Request, body: EmbeddingRequest):
    """将文本转换为向量嵌入"""
    response = UnifiedResponse()
    try:
        result = run_embedding(text=body.text)
        response.ok(result)

    except BusinessError as e:
        response.error(e)
    except Exception as e:
        logger.error(f"向量化失败: {e}", exc_info=True)
        response.error(BusinessError(ModelErrorCode.INTERNAL_ERROR, str(e)))

    return response.to_json()

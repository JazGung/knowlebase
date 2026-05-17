"""
模型域 API — /model/*

POST /model/parsing  — 文档解析
POST /model/embedding — 文本向量化
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from knowlebase.schemas.model import (
    ParseRequest,
    ParseResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from knowlebase.model.service import run_parsing, run_embedding

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/parsing",
    summary="文档解析",
)
async def parse(request: Request, body: ParseRequest):
    """解析 PDF/Word 文档为结构化内容"""
    try:
        result = await run_parsing(
            file_content_b64=body.file_content,
            file_format=body.file_format,
            file_name=body.file_name,
        )
        return JSONResponse(content={
            "code": "000000",
            "description": "成功",
            "content": result,
        })
    except ValueError as e:
        return JSONResponse(
            status_code=200,
            content={
                "code": "400002",
                "description": str(e),
                "content": None,
            },
        )
    except Exception as e:
        logger.error(f"文档解析失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "code": "500006",
                "description": "文档解析失败",
                "content": None,
            },
        )


@router.post(
    "/embedding",
    summary="文本向量化",
)
async def embed(request: Request, body: EmbeddingRequest):
    """将文本转换为向量嵌入"""
    try:
        result = run_embedding(text=body.text)
        return JSONResponse(content={
            "code": "000000",
            "description": "成功",
            "content": result,
        })
    except Exception as e:
        logger.error(f"向量化失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "code": "500006",
                "description": "向量化失败",
                "content": None,
            },
        )

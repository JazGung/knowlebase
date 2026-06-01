"""
模型域 Service 层

ParseService — 封装 PDF/Word 文档解析
EmbeddingService — 封装 sentence-transformers 向量化
"""

import base64
import logging
from typing import List

from knowlebase.parsers import parse_document
from knowlebase.schemas.model import ModelErrorCode
from knowlebase.schemas.errors import BusinessError
from knowlebase.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)
    return _embedding_instance


async def run_parsing(file_content_b64: str, file_format: str, file_name: str) -> dict:
    """执行文档解析

    Args:
        file_content_b64: base64 编码的文件内容
        file_format: 文件格式（pdf / docx / doc）
        file_name: 文件名

    Returns:
        dict: 解析结果（sections 列表）
    """
    try:
        mime = _format_to_mime(file_format)
    except KeyError:
        raise BusinessError(ModelErrorCode.UNSUPPORTED_FORMAT, f"不支持的文件格式: {file_format}")

    try:
        content = base64.b64decode(file_content_b64)
    except Exception as e:
        raise BusinessError(ModelErrorCode.INVALID_INPUT, f"base64 解码失败: {e}")

    try:
        result = await parse_document(
            content=content,
            filename=file_name,
            mime_type=mime,
        )
    except Exception as e:
        logger.error(f"文档解析失败: {e}", exc_info=True)
        raise BusinessError(ModelErrorCode.INFERENCE_FAILED, f"文档解析失败: {e}")

    return {"sections": _sections_to_dict(result.sections)}


def run_embedding(text: str) -> dict:
    """执行文本向量化

    Args:
        text: 待向量化的文本

    Returns:
        dict: { "vector": [...], "dimension": N }
    """
    if not text or not text.strip():
        raise BusinessError(ModelErrorCode.INVALID_INPUT, "待向量化文本不能为空")

    try:
        svc = get_embedding_service()
    except Exception as e:
        logger.error(f"模型加载失败: {e}", exc_info=True)
        raise BusinessError(ModelErrorCode.MODEL_LOAD_FAILED, f"模型加载失败: {e}")

    try:
        vector = svc.encode_single(text)
    except Exception as e:
        logger.error(f"向量化失败: {e}", exc_info=True)
        raise BusinessError(ModelErrorCode.INFERENCE_FAILED, f"向量化失败: {e}")

    return {
        "vector": vector,
        "dimension": len(vector),
    }


def _format_to_mime(file_format: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
    }[file_format]


def _sections_to_dict(sections: list) -> list:
    result = []
    for sec in sections:
        item = {"title": sec.title, "content": []}
        for el in sec.content:
            el_dict = {"type": el.type}
            if el.type == "text":
                el_dict["text"] = el.text
            elif el.type == "image":
                el_dict["image_path"] = el.image_path
                el_dict["caption"] = el.caption
            elif el.type == "table":
                el_dict["headers"] = el.headers
                el_dict["rows"] = el.rows
            elif el.type == "section":
                el_dict["section"] = _sections_to_dict([el.section])[0]
            item["content"].append(el_dict)
        result.append(item)
    return result

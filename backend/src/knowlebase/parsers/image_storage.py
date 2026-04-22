"""图片存储服务

图片 MD5 hash 去重 + MinIO 存储。
上传前检查 MinIO 是否已存在，存在则复用。
"""

import hashlib
import logging
from io import BytesIO
from typing import Optional

from knowlebase.services.minio_service import get_minio_service
from knowlebase.core.config import settings

logger = logging.getLogger(__name__)

# 独立图片存储桶
IMAGE_BUCKET = settings.minio_document_bucket
IMAGE_PREFIX = "images/"


def _compute_hash(data: bytes) -> str:
    """计算字节数据的 MD5 哈希"""
    return hashlib.md5(data).hexdigest()


def store_image(img_bytes: bytes, ext: str = "png") -> str:
    """存储图片到 MinIO，带去重

    Args:
        img_bytes: 图片原始字节
        ext: 图片格式后缀（默认 png）

    Returns:
        MinIO 对象路径，如 "images/a1b2c3d4e5f6.png"
    """
    img_hash = _compute_hash(img_bytes)
    object_name = f"{IMAGE_PREFIX}{img_hash}.{ext}"

    minio_svc = get_minio_service()

    # 检查是否已存在（去重）
    if minio_svc.file_exists(IMAGE_BUCKET, object_name):
        logger.debug(f"图片已存在，复用: {object_name}")
        return object_name

    # 上传
    minio_svc.upload_file(
        bucket_name=IMAGE_BUCKET,
        object_name=object_name,
        file_data=img_bytes,
        content_type=f"image/{ext}",
    )
    logger.info(f"图片上传成功: {object_name} ({len(img_bytes)} bytes)")
    return object_name


def get_image(object_name: str) -> bytes:
    """从 MinIO 下载图片

    Args:
        object_name: MinIO 对象路径

    Returns:
        图片字节数据
    """
    minio_svc = get_minio_service()
    return minio_svc.download_file(IMAGE_BUCKET, object_name)

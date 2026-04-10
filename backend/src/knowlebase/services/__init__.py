"""基础设施服务模块"""

from knowlebase.services.minio_service import MinioService, minio_service, init_minio, get_minio_service

__all__ = [
    "MinioService",
    "minio_service",
    "init_minio",
    "get_minio_service",
]

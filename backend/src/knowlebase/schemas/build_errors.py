"""
构建域 — 错误码枚举（与 DEG §4.2 一致）
"""

from knowlebase.schemas.errors import ErrorCode


class BuildErrorCode(ErrorCode):
    """构建域错误码"""

    # 警告码 (0xxxxx)
    PROCESSING_IN_PROGRESS = ("001003", "文档正在处理中，请稍后再试")

    # 客户端错误 (4xxxxx)
    DOCUMENT_NOT_FOUND = ("404001", "文档不存在")
    RELATION_NOT_FOUND = ("404003", "文档-版本关联不存在")

    # 服务端错误 (5xxxxx)
    PARSING_FAILED = ("500003", "文档解析失败")
    CHUNKING_FAILED = ("500004", "文档分块失败")
    INTERNAL_ERROR = ("500000", "构建域内部错误")
    STORAGE_UNAVAILABLE = ("503001", "MinIO 存储服务不可用")
    DATABASE_UNAVAILABLE = ("503002", "数据库服务不可用")
    LLM_UNAVAILABLE = ("503003", "LLM 服务不可用")
    SERVICE_UNAVAILABLE = ("503004", "事件总线不可用")

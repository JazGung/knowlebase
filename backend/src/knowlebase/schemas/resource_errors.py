"""
业务资源域 — 错误码枚举（与 DEG §4.2 一致）
"""

from knowlebase.schemas.errors import ErrorCode


class ResourceErrorCode(ErrorCode):
    """业务资源域错误码"""

    # 警告码 (0xxxxx)
    DOCUMENT_ALREADY_ENABLED = ("001001", "文档已启用，无需重复操作")
    DOCUMENT_ALREADY_DISABLED = ("001002", "文档已停用，无需重复操作")
    VERSION_ALREADY_ENABLED = ("001004", "该版本已是启用状态，无需重复操作")
    BUILDING_IN_PROGRESS = ("001004", "知识库版本正在构建中，暂不支持此操作")

    # 客户端错误 (4xxxxx)
    FILE_FORMAT_NOT_SUPPORTED = ("400001", "仅支持 PDF/Word 格式")
    FILE_SIZE_EXCEEDED = ("400002", "文件大小超过 100MB 限制")
    FILE_HASH_MISMATCH = ("400003", "前端哈希与后端计算不一致")
    INVALID_PARAMETER = ("400004", "参数校验失败")
    VERSION_CANNOT_BUILD = ("400005", "该版本无法构建，仅可构建初始化或失败状态的版本")
    VERSION_CANNOT_ENABLE = ("400006", "该版本无法启用，仅可启用成功或已禁用状态的版本")
    DOCUMENT_NOT_FOUND = ("404001", "文档不存在")
    VERSION_NOT_FOUND = ("404002", "版本不存在")
    NO_ENABLED_VERSION = ("404004", "暂无启用的知识库版本，请先创建并启用一个版本")
    FILE_DUPLICATE = ("409001", "文件哈希与已有记录重复")
    VERSION_BUILDING_EXISTS = ("409002", "已有版本正在构建中")
    FILE_NAME_DUPLICATE = ("409003", "文件名与已有记录重复")

    # 服务端错误 (5xxxxx)
    DOCUMENT_SAVE_FAILED = ("500002", "文档持久化失败")
    INTERNAL_ERROR = ("500000", "业务资源域内部错误")
    STORAGE_UNAVAILABLE = ("503001", "MinIO 存储服务不可用")
    DATABASE_UNAVAILABLE = ("503002", "数据库服务不可用")

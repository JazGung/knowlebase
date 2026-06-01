"""
模型域 Pydantic schemas — 请求/响应模型、错误码枚举
"""

from typing import List

from pydantic import BaseModel, Field

from knowlebase.schemas.errors import ErrorCode


class ModelErrorCode(ErrorCode):
    """模型域错误码（与 DEG §4.2 一致）"""
    UNSUPPORTED_FORMAT = ("400002", "不支持的文档格式")
    INVALID_INPUT = ("400003", "无效的模型输入")
    INFERENCE_FAILED = ("500006", "模型推理失败")
    MODEL_LOAD_FAILED = ("503005", "模型加载失败")
    INTERNAL_ERROR = ("500000", "模型域内部错误")


# ==================== 请求/响应模型 ====================


class ParseRequest(BaseModel):
    """文档解析请求"""

    file_content: str = Field(..., description="文件内容（base64 编码）")
    file_format: str = Field(
        ...,
        pattern=r"^(pdf|docx|doc)$",
        description="文件格式",
    )
    file_name: str = Field(..., min_length=1, description="文件名（日志追踪）")


class ParseResponse(BaseModel):
    """文档解析响应 — ParseResult 的 sections 树状结构"""

    sections: list = Field(default_factory=list, description="章节段落列表")


class EmbeddingRequest(BaseModel):
    """向量化请求"""

    text: str = Field(..., min_length=1, description="待向量化的文本")


class EmbeddingResponse(BaseModel):
    """向量化响应"""

    vector: List[float] = Field(..., description="嵌入向量")
    dimension: int = Field(..., description="向量维度")

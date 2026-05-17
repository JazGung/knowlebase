"""
模型域 Pydantic schemas
"""

from typing import List

from pydantic import BaseModel, Field


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

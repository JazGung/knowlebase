"""
检索域 — Pydantic 请求/响应模型
"""

from typing import Optional
from pydantic import BaseModel, Field

from knowlebase.schemas.errors import ErrorCode


# ==================== 请求体 ====================

class SearchRequest(BaseModel):
    """检索 API 请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="检索查询文本")
    top_n: Optional[int] = Field(default=None, ge=1, description="最终返回条数")


class DebugSearchRequest(BaseModel):
    """检索调试请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="检索查询文本")
    version_id: int = Field(..., ge=1, description="知识库版本 ID")
    top_n: Optional[int] = Field(default=None, ge=1, description="最终返回条数")


# ==================== 响应数据 ====================

class SearchResultItem(BaseModel):
    """单条检索结果"""
    chunk_text: str = Field(..., description="分块文本")
    document_name: str = Field(..., description="所属文档名称")
    page_number: int = Field(..., description="所在页码")
    chapter_title: str = Field(..., description="所在章节标题")
    score: float = Field(..., description="相关性分数")


class ChunkTextItem(BaseModel):
    """检索 API 单条结果（仅文本）"""
    chunk_text: str = Field(..., description="分块文本")


class DebugSearchResponse(BaseModel):
    """检索调试响应"""
    es_results: list[SearchResultItem] = Field(default_factory=list, description="ES 原始结果")
    milvus_results: list[SearchResultItem] = Field(default_factory=list, description="Milvus 原始结果")
    neo4j_results: list[SearchResultItem] = Field(default_factory=list, description="Neo4j 原始结果")
    merged_results: list[SearchResultItem] = Field(default_factory=list, description="合并后结果")
    reranked_results: list[SearchResultItem] = Field(default_factory=list, description="重排序后结果")


class VersionOption(BaseModel):
    """版本选项"""
    id: int = Field(..., description="版本 ID")
    version_name: str = Field(..., description="版本名称")
    version_code: int = Field(..., description="版本编码（毫秒时间戳）")
    status: str = Field(..., description="版本状态")
    is_built: bool = Field(..., description="是否已构建")


class VersionListResponse(BaseModel):
    """版本列表响应"""
    versions: list[VersionOption] = Field(default_factory=list, description="可选版本列表")


# ==================== 错误码 ====================

class RetrievalErrorCode(ErrorCode):
    """检索域错误码"""
    RETRIEVAL_NO_ENABLED_VERSION = ("404001", "暂无已启用的知识库版本")
    RETRIEVAL_VERSION_NOT_FOUND = ("404002", "指定的知识库版本不存在")
    RETRIEVAL_VERSION_NOT_BUILT = ("400001", "指定版本尚未构建完成，无可检索数据")
    RETRIEVAL_INTERNAL_ERROR = ("500000", "检索域内部错误")

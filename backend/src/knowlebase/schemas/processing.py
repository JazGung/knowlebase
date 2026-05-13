"""文档处理管理相关 Pydantic 数据模型"""

from typing import Optional, List
from pydantic import BaseModel, Field


class RelationListQuery(BaseModel):
    """文档-版本关联查询请求 (DEG 4.4.1)"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    document_id: Optional[int] = Field(default=None, description="按文档过滤")
    version_id: Optional[int] = Field(default=None, description="按版本过滤")


class RelationListItem(BaseModel):
    """关联记录条目 (DEG 4.4.2)"""
    id: int
    document_id: int
    document_name: str
    version_id: int
    version_name: str
    relation_type: str
    status: str
    attempt_count: int
    created_at: Optional[str] = None


class RelationListResponse(BaseModel):
    """关联查询分页响应"""
    data: List[RelationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class HistoryListQuery(BaseModel):
    """处理记录查询请求 (DEG 4.6.1)"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    relation_id: int = Field(..., ge=1, description="关联记录ID")


class HistoryListItem(BaseModel):
    """处理记录条目 (DEG 4.6.2)"""
    id: int
    processing_id: str
    attempt_no: int
    status: str
    current_stage: Optional[str] = None
    progress: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class HistoryListResponse(BaseModel):
    """处理记录分页响应"""
    data: List[HistoryListItem]
    total: int
    page: int
    page_size: int
    total_pages: int

"""
文档相关Pydantic数据模型

包含文档上传、管理、查询等API的请求和响应模型
"""

import re
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator


class DocumentStatus(str, Enum):
    """文档状态枚举"""
    ENABLED = "enabled"
    DISABLED = "disabled"


class ProcessingStatus(str, Enum):
    """处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FileCheckItem(BaseModel):
    """
    文件检查项

    用于重复性校验接口
    """
    filename: str = Field(..., description="文件名")
    hash: str = Field(..., description="文件MD5哈希值（32位十六进制）")

    @validator("hash")
    def validate_hash(cls, v):
        """验证MD5哈希格式"""
        if not v or len(v) != 32:
            raise ValueError("MD5哈希必须是32位十六进制字符串")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("MD5哈希必须是有效的十六进制字符串")
        return v.lower()

    class Config:
        schema_extra = {
            "example": {
                "filename": "文档1.pdf",
                "hash": "a1b2c3d4e5f678901234567890123456"
            }
        }


class FileCheckRequest(BaseModel):
    """
    重复性校验请求模型

    用于 `/build/document/check` 接口
    """
    files: List[FileCheckItem] = Field(..., description="文件检查项列表")

    @validator("files")
    def validate_files(cls, v):
        """验证文件列表"""
        if not v:
            raise ValueError("文件列表不能为空")
        filenames = [item.filename for item in v]
        if len(filenames) != len(set(filenames)):
            raise ValueError("文件名不能重复")
        return v

    class Config:
        schema_extra = {
            "example": {
                "files": [
                    {
                        "filename": "文档1.pdf",
                        "hash": "a1b2c3d4e5f678901234567890123456"
                    },
                    {
                        "filename": "文档2.docx",
                        "hash": "b2c3d4e5f678901234567890123456a1"
                    }
                ]
            }
        }


class DuplicateFileInfo(BaseModel):
    """
    重复文件信息

    用于重复性校验响应
    """
    filename: str = Field(..., description="文件名")
    hash: str = Field(..., description="文件MD5哈希值")
    existing_document_id: str = Field(..., description="已存在文档的ID")
    existing_filename: str = Field(..., description="已存在文档的文件名")

    class Config:
        schema_extra = {
            "example": {
                "filename": "文档1.pdf",
                "hash": "a1b2c3d4e5f678901234567890123456",
                "existing_document_id": "doc_existing_123",
                "existing_filename": "已存在文档.pdf"
            }
        }


class FileCheckResponse(BaseModel):
    """
    重复性校验响应模型
    """
    duplicates: List[DuplicateFileInfo] = Field(..., description="重复文件列表")

    class Config:
        schema_extra = {
            "example": {
                "duplicates": [
                    {
                        "filename": "文档1.pdf",
                        "hash": "a1b2c3d4e5f678901234567890123456",
                        "existing_document_id": "doc_existing_123",
                        "existing_filename": "已存在文档.pdf"
                    }
                ]
            }
        }


class DocumentUploadRequestMetadata(BaseModel):
    """
    文档上传元数据
    """
    title: Optional[str] = Field(None, description="文档标题")


class DocumentUploadResponse(BaseModel):
    """
    文档上传响应模型

    用于 `/build/document/upload` 接口的成功响应
    """
    document_id: str = Field(..., description="文档ID")
    original_filename: str = Field(..., description="原始文件名")
    file_hash: str = Field(..., description="文件MD5哈希值")
    status: str = Field(..., description="上传状态")

    class Config:
        schema_extra = {
            "example": {
                "document_id": "doc_1234567890",
                "original_filename": "API设计文档.pdf",
                "file_hash": "a1b2c3d4e5f678901234567890123456",
                "status": "success"
            }
        }


class IntegrityValidationError(BaseModel):
    """
    完整性验证错误详情

    用于上传文件完整性验证失败响应
    """
    field: str = Field(..., description="字段名")
    error: str = Field(..., description="错误信息")
    expected: str = Field(..., description="期望的哈希值")
    actual: str = Field(..., description="实际计算的哈希值")

    class Config:
        schema_extra = {
            "example": {
                "field": "hash",
                "error": "提供的MD5哈希值与实际文件内容不匹配",
                "expected": "a1b2c3d4e5f678901234567890123456",
                "actual": "different_md5_value_here"
            }
        }


class DocumentListQuery(BaseModel):
    """
    文档列表查询参数
    """
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: Optional[DocumentStatus] = Field(None, description="启用状态过滤")
    search: Optional[str] = Field(None, description="关键字搜索")
    sort_by: str = Field(default="created_at", description="排序字段")
    order: str = Field(default="desc", description="排序方向")

    @validator("order")
    def validate_order(cls, v):
        """验证排序方向"""
        if v not in ["asc", "desc"]:
            raise ValueError("排序方向必须是 'asc' 或 'desc'")
        return v

    @validator("sort_by")
    def validate_sort_by(cls, v):
        """验证排序字段"""
        valid_fields = ["created_at", "updated_at", "file_size", "title"]
        if v not in valid_fields:
            raise ValueError(f"排序字段必须是以下值之一: {', '.join(valid_fields)}")
        return v


class DocumentDetail(BaseModel):
    """
    文档详情
    """
    id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="存储文件名")
    original_filename: str = Field(..., description="原始文件名")
    title: Optional[str] = Field(None, description="文档标题")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    mime_type: Optional[str] = Field(None, description="文件MIME类型")
    file_hash: str = Field(..., description="文件MD5哈希值")
    status: str = Field(..., description="启用状态：enabled/disabled")
    latest_processing_id: Optional[str] = Field(None, description="最新处理任务ID")
    rebuild_id: Optional[str] = Field(None, description="重建记录ID")
    created_by: Optional[str] = Field(None, description="创建者")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class ProcessingStageItem(BaseModel):
    """
    处理阶段详情
    """
    stage_name: str = Field(..., description="阶段名称")
    status: str = Field(..., description="阶段状态：running/succeeded/failed")
    duration_ms: Optional[int] = Field(None, description="阶段耗时（毫秒）")


class ProcessingHistoryItem(BaseModel):
    """
    处理历史记录项
    """
    processing_id: str = Field(..., description="处理任务ID")
    attempt_no: int = Field(..., description="处理次数")
    status: ProcessingStatus = Field(..., description="处理状态")
    current_stage: Optional[str] = Field(None, description="当前处理阶段")
    progress: int = Field(..., ge=0, le=100, description="处理进度（0-100）")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    stages: Optional[List[ProcessingStageItem]] = Field(None, description="处理阶段列表")


class DocumentDetailResponse(BaseModel):
    """
    文档详情响应模型
    """
    document: DocumentDetail = Field(..., description="文档详情")
    processing_history: List[ProcessingHistoryItem] = Field(..., description="处理历史记录")
    total_processings: int = Field(..., description="总处理次数")


class ReprocessDocumentRequest(BaseModel):
    """
    重新处理文档请求模型
    """
    document_id: int = Field(..., description="文档ID")
    force_reprocess: bool = Field(default=False, description="是否强制重新处理")


class ReprocessDocumentResponse(BaseModel):
    """
    重新处理文档响应模型
    """
    document_id: str = Field(..., description="文档ID")
    processing_id: str = Field(..., description="处理任务ID")
    attempt_no: int = Field(..., description="处理次数")


class BaseResponse(BaseModel):
    """
    统一响应基类

    code: "000000" 为成功，"0xxxxx" 为警告码，"1xxxxx~9xxxxx" 为错误码
    """
    code: str = Field(default="000000", description="响应码")
    description: str = Field(default="成功", description="响应描述")
    content: Optional[Dict[str, Any]] = Field(None, description="响应内容")


class BatchResult(BaseModel):
    """批量操作单条结果"""
    id: str = Field(..., description="记录ID")
    status: str = Field(..., description="success/failed")
    reason: Optional[str] = Field(None, description="失败原因")


class BatchResponse(BaseModel):
    """批量操作响应内容"""
    results: List[BatchResult] = Field(default_factory=list, description="批量操作结果列表")


class EnableDisableDocumentRequest(BaseModel):
    """启用/停用文档请求模型（批量）"""
    document_ids: List[int] = Field(..., description="文档ID列表")


class ProcessingTriggerRequest(BaseModel):
    """触发处理请求模型（批量）"""
    document_ids: List[int] = Field(..., description="文档ID列表")

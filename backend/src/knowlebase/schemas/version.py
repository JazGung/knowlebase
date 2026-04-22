"""
知识库版本相关Pydantic数据模型

包含版本管理、文档-版本关联等API的请求和响应模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class VersionStatus(str, Enum):
    """版本状态枚举"""
    BUILDING = "building"
    SUCCEEDED = "succeeded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


class RelationType(str, Enum):
    """文档-版本关联类型枚举"""
    INITIAL = "initial"
    INCREMENTAL = "incremental"
    REPROCESSED = "reprocessed"


class DocumentVersionStatus(str, Enum):
    """文档在版本中的处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ==================== 查询参数 ====================

class VersionListQuery(BaseModel):
    """
    版本列表查询请求

    用于 `/build/version/list` 接口
    """
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: Optional[VersionStatus] = Field(None, description="状态过滤")

    class Config:
        schema_extra = {
            "example": {
                "page": 1,
                "page_size": 20,
                "status": "succeeded"
            }
        }


class VersionDetailQuery(BaseModel):
    """版本详情查询参数"""
    version_id: str = Field(..., description="版本ID（如 v20260422_103000）")


# ==================== 请求体 ====================

class VersionCreateRequest(BaseModel):
    """
    创建版本请求

    用于 `/build/version/create` 接口
    """
    created_by: Optional[str] = Field(default=None, max_length=100, description="操作人")

    class Config:
        schema_extra = {
            "example": {
                "created_by": "admin"
            }
        }


class VersionEnableRequest(BaseModel):
    """
    启用版本请求

    用于 `/build/version/enable` 接口
    """
    version_id: str = Field(..., description="版本ID")


class VersionDisableRequest(BaseModel):
    """
    停用版本请求

    用于 `/build/version/disable` 接口
    """
    version_id: str = Field(..., description="版本ID")


class VersionDeleteRequest(BaseModel):
    """
    删除版本请求

    用于 `/build/version/delete` 接口
    """
    version_id: str = Field(..., description="版本ID")


# ==================== 响应数据 ====================

class VersionResponse(BaseModel):
    """
    版本响应数据
    """
    id: str = Field(..., description="版本主键ID")
    version_id: str = Field(..., description="版本标识")
    status: str = Field(..., description="版本状态")
    document_count: int = Field(default=0, description="包含的文档数")
    chunk_count: int = Field(default=0, description="包含的chunk总数")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_by: Optional[str] = Field(None, description="操作人")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    class Config:
        schema_extra = {
            "example": {
                "id": "1",
                "version_id": "v20260422_103000",
                "status": "succeeded",
                "document_count": 15,
                "chunk_count": 120,
                "error_message": None,
                "created_by": "admin",
                "started_at": "2026-04-22T10:30:00+08:00",
                "completed_at": "2026-04-22T11:00:00+08:00",
                "created_at": "2026-04-22T10:30:00+08:00",
                "updated_at": "2026-04-22T11:00:00+08:00"
            }
        }


class VersionListData(BaseModel):
    """
    版本列表响应数据
    """
    versions: List[VersionResponse] = Field(..., description="版本列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class VersionDetailData(BaseModel):
    """
    版本详情响应数据
    """
    version: VersionResponse = Field(..., description="版本详情")


class VersionCreateData(BaseModel):
    """
    创建版本响应数据
    """
    version_id: str = Field(..., description="创建的版本ID")
    status: str = Field(..., description="版本状态")


class BaseResponse(BaseModel):
    """
    基础响应模型
    """
    code: int = Field(default=0, description="响应码，0表示成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")


class SuccessResponse(BaseResponse):
    """
    成功响应模型
    """
    code: int = Field(default=0, description="响应码，0表示成功")


class ErrorResponse(BaseResponse):
    """
    错误响应模型
    """
    code: int = Field(..., ge=1, description="错误码，大于0表示错误")
    detail: Optional[Dict[str, Any]] = Field(None, description="错误详情")


# ==================== 特定响应模型 ====================

class VersionListSuccessResponse(SuccessResponse):
    data: VersionListData = Field(..., description="版本列表结果")


class VersionDetailSuccessResponse(SuccessResponse):
    data: VersionDetailData = Field(..., description="版本详情结果")


class VersionCreateSuccessResponse(SuccessResponse):
    data: VersionCreateData = Field(..., description="创建版本结果")


class VersionActionSuccessResponse(SuccessResponse):
    """启用/停用/删除版本成功响应"""
    data: Dict[str, Any] = Field(..., description="操作结果")

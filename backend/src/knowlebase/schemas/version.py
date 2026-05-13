"""
知识库版本相关Pydantic数据模型

包含版本管理API的请求和响应模型
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class VersionStatus(str, Enum):
    """版本状态枚举"""
    INIT = "init"
    BUILDING = "building"
    SUCCEEDED = "succeeded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


# ==================== 查询参数 ====================

class VersionListQuery(BaseModel):
    """版本列表查询参数"""
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


# ==================== 请求体 ====================

class VersionCreateRequest(BaseModel):
    """创建版本请求"""
    created_by: Optional[str] = Field(default=None, max_length=100, description="操作人")

    class Config:
        schema_extra = {
            "example": {
                "created_by": "admin"
            }
        }


class VersionBuildRequest(BaseModel):
    """构建版本请求"""
    version_name: str = Field(..., description="版本名称")

    class Config:
        schema_extra = {
            "example": {
                "version_name": "v20260422_103000"
            }
        }


class VersionEnableRequest(BaseModel):
    """启用版本请求"""
    version_name: str = Field(..., description="版本名称")

    class Config:
        schema_extra = {
            "example": {
                "version_name": "v20260422_103000"
            }
        }


# ==================== 响应数据 ====================

class VersionResponse(BaseModel):
    """版本响应数据"""
    id: str = Field(..., description="版本主键ID")
    version_name: str = Field(..., description="版本名称")
    status: str = Field(..., description="版本状态")
    document_count: int = Field(default=0, description="包含的文档数")
    chunk_count: int = Field(default=0, description="包含的chunk总数")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_by: Optional[str] = Field(None, description="操作人")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    created_at: str = Field(..., description="创建时间")


class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = Field(default=0, description="响应码，0表示成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")


class SuccessResponse(BaseModel):
    """成功响应模型"""
    code: int = Field(default=0, description="响应码")
    message: str = Field(default="成功", description="响应消息")


# ==================== 特定响应模型 ====================

class VersionListData(BaseModel):
    """版本列表响应数据"""
    versions: List[VersionResponse] = Field(..., description="版本列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class VersionListSuccessResponse(SuccessResponse):
    data: VersionListData = Field(..., description="版本列表结果")


class VersionCreateData(BaseModel):
    """创建版本响应数据"""
    version_name: str = Field(..., description="版本名称")
    status: str = Field(..., description="版本状态")


class VersionCreateSuccessResponse(SuccessResponse):
    data: VersionCreateData = Field(..., description="创建版本结果")


class VersionActionSuccessResponse(SuccessResponse):
    """构建/启用操作成功响应"""
    data: Dict[str, Any] = Field(..., description="操作结果")

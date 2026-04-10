"""
文件管理相关Pydantic数据模型

包含孤立文件管理、文件清理等API的请求和响应模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class OrphanedFileInfo(BaseModel):
    """
    孤立文件信息
    """
    filename: str = Field(..., description="文件名（MD5哈希）")
    size: int = Field(..., description="文件大小（字节）")
    last_modified: Optional[datetime] = Field(None, description="最后修改时间")
    age_hours: float = Field(..., description="文件年龄（小时）")

    class Config:
        schema_extra = {
            "example": {
                "filename": "a1b2c3d4e5f678901234567890123456",
                "size": 5242880,
                "last_modified": "2026-04-09T14:30:00Z",
                "age_hours": 5.5
            }
        }


class ScanOrphansResponseData(BaseModel):
    """
    扫描孤立文件响应数据
    """
    total_files: int = Field(..., description="总文件数")
    orphaned_files: int = Field(..., description="孤立文件数")
    orphaned_size: int = Field(..., description="孤立文件总大小（字节）")
    files: List[OrphanedFileInfo] = Field(..., description="孤立文件列表")

    class Config:
        schema_extra = {
            "example": {
                "total_files": 150,
                "orphaned_files": 3,
                "orphaned_size": 10485760,
                "files": [
                    {
                        "filename": "a1b2c3d4e5f678901234567890123456",
                        "size": 5242880,
                        "last_modified": "2026-04-09T14:30:00Z",
                        "age_hours": 5
                    }
                ]
            }
        }


class CleanupOrphansRequest(BaseModel):
    """
    清理孤立文件请求模型
    """
    file_hashes: Optional[List[str]] = Field(None, description="要清理的文件哈希列表，不传则清理所有孤立文件")
    min_age_hours: float = Field(default=1.0, ge=0, description="最小文件年龄（小时），避免误删正在上传的文件")

    @validator("file_hashes")
    def validate_file_hashes(cls, v):
        """验证文件哈希列表"""
        if v is not None:
            for hash_value in v:
                if len(hash_value) != 32:
                    raise ValueError(f"文件哈希必须是32位十六进制字符串: {hash_value}")
                try:
                    int(hash_value, 16)
                except ValueError:
                    raise ValueError(f"文件哈希必须是有效的十六进制字符串: {hash_value}")
        return v


class CleanupOrphansResponseData(BaseModel):
    """
    清理孤立文件响应数据
    """
    cleaned_files: int = Field(..., description="清理的文件数")
    freed_space: int = Field(..., description="释放的空间（字节）")
    failed_files: List[Dict[str, Any]] = Field(default=[], description="清理失败的文件列表")

    class Config:
        schema_extra = {
            "example": {
                "cleaned_files": 3,
                "freed_space": 10485760,
                "failed_files": []
            }
        }


class CleanupLogEntry(BaseModel):
    """
    清理日志条目
    """
    id: str = Field(..., description="日志条目ID")
    file_hash: str = Field(..., description="文件哈希")
    file_size: int = Field(..., description="文件大小（字节）")
    cleanup_reason: str = Field(..., description="清理原因")
    cleaned_at: datetime = Field(..., description="清理时间")
    cleaned_by: str = Field(..., description="清理执行者")
    user_id: Optional[str] = Field(None, description="用户ID（如果适用）")
    additional_info: Optional[str] = Field(None, description="附加信息")

    class Config:
        schema_extra = {
            "example": {
                "id": "log_1234567890",
                "file_hash": "a1b2c3d4e5f678901234567890123456",
                "file_size": 5242880,
                "cleanup_reason": "orphaned",
                "cleaned_at": "2026-04-09T15:30:00Z",
                "cleaned_by": "system",
                "user_id": None,
                "additional_info": "定时任务自动清理"
            }
        }


class CleanupLogQuery(BaseModel):
    """
    清理日志查询参数
    """
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    cleanup_reason: Optional[str] = Field(None, description="清理原因过滤")
    cleaned_by: Optional[str] = Field(None, description="清理执行者过滤")

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """验证日期范围"""
        if "start_date" in values and values["start_date"] and v:
            if v < values["start_date"]:
                raise ValueError("结束日期不能早于开始日期")
        return v

    @validator("cleanup_reason")
    def validate_cleanup_reason(cls, v):
        """验证清理原因"""
        if v is not None:
            valid_reasons = {"orphaned", "manual", "expired"}
            if v not in valid_reasons:
                raise ValueError(f"清理原因必须是以下值之一: {', '.join(valid_reasons)}")
        return v


class CleanupLogResponseData(BaseModel):
    """
    清理日志响应数据
    """
    logs: List[CleanupLogEntry] = Field(..., description="清理日志列表")
    total: int = Field(..., description="总日志数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")

    class Config:
        schema_extra = {
            "example": {
                "logs": [
                    {
                        "id": "log_1234567890",
                        "file_hash": "a1b2c3d4e5f678901234567890123456",
                        "file_size": 5242880,
                        "cleanup_reason": "orphaned",
                        "cleaned_at": "2026-04-09T15:30:00Z",
                        "cleaned_by": "system",
                        "user_id": None,
                        "additional_info": "定时任务自动清理"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
                "total_pages": 1
            }
        }
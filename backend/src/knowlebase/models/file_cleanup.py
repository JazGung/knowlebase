"""
文件清理日志数据库模型

包含文件清理日志的SQLAlchemy模型
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, BigInteger, Text, JSON, TIMESTAMP, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import validates, relationship

from knowlebase.db.session import Base


class FileCleanupLog(Base):
    """
    文件清理日志模型

    对应数据库表: file_cleanup_log
    记录文件清理操作的历史
    """

    __tablename__ = "file_cleanup_log"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="清理日志唯一标识"
    )

    # 文件信息
    file_hash = Column(
        String(32),
        nullable=False,
        comment="文件MD5哈希值"
    )
    file_size = Column(
        BigInteger,
        nullable=False,
        comment="文件大小（字节）"
    )

    # 清理信息
    cleanup_reason = Column(
        String(100),
        nullable=False,
        comment="清理原因：orphaned, manual, expired"
    )
    cleaned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="清理时间"
    )
    cleaned_by = Column(
        String(100),
        nullable=False,
        default="system",
        comment="清理执行者：system 或 管理员用户名"
    )

    # 外键关联（可选，关联到用户）
    user_id = Column(
        BigInteger,
        nullable=True,
        comment="执行清理的用户ID"
    )

    # 附加信息
    additional_info = Column(
        String(500),
        nullable=True,
        comment="附加信息"
    )

    # 约束
    __table_args__ = (
        Index("idx_file_cleanup_hash", "file_hash"),
        Index("idx_file_cleanup_time", "cleaned_at"),
        Index("idx_file_cleanup_reason", "cleanup_reason"),
        Index("idx_file_cleanup_user", "user_id"),
        {"comment": "文件清理日志表"}
    )

    @validates("file_hash")
    def validate_file_hash(self, key, value):
        """验证文件哈希格式"""
        if not value or len(value) != 32:
            raise ValueError("文件哈希必须是32位十六进制字符串")
        # 验证十六进制格式
        try:
            int(value, 16)
        except ValueError:
            raise ValueError("文件哈希必须是有效的十六进制字符串")
        return value.lower()  # 统一转为小写

    @validates("cleanup_reason")
    def validate_cleanup_reason(self, key, value):
        """验证清理原因"""
        valid_reasons = {"orphaned", "manual", "expired"}
        if value not in valid_reasons:
            raise ValueError(f"清理原因必须是以下值之一: {', '.join(valid_reasons)}")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "cleanup_reason": self.cleanup_reason,
            "cleaned_at": self.cleaned_at.isoformat() if self.cleaned_at else None,
            "cleaned_by": self.cleaned_by,
            "user_id": str(self.user_id) if self.user_id else None,
            "additional_info": self.additional_info,
        }

    def __repr__(self):
        return f"<FileCleanupLog(id={self.id}, file_hash={self.file_hash}, reason='{self.cleanup_reason}')>"


class SystemConfig(Base):
    """
    系统配置模型

    对应数据库表: system_config
    存储系统配置项
    """

    __tablename__ = "system_config"

    # 主键
    key = Column(
        String(100),
        primary_key=True,
        comment="配置键"
    )

    # 配置值
    value = Column(
        JSON,
        nullable=False,
        comment="配置值（JSON格式）"
    )

    # 描述信息
    description = Column(
        Text,
        nullable=True,
        comment="配置描述"
    )

    # 更新信息
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间"
    )
    updated_by = Column(
        BigInteger,
        ForeignKey("user.id"),
        nullable=True,
        comment="更新用户ID"
    )

    # 关系
    user = relationship("User", foreign_keys=[updated_by], lazy="selectin")

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": str(self.updated_by) if self.updated_by else None,
        }

    def __repr__(self):
        return f"<SystemConfig(key='{self.key}', value={self.value})>"
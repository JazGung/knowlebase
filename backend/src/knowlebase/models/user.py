"""
用户数据库模型

包含用户信息和权限的SQLAlchemy模型
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Text,
    JSON,
    Integer,
    BigInteger,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates

from knowlebase.db.session import Base


class User(Base):
    """
    用户模型

    对应数据库表: users
    存储用户信息和权限
    """

    __tablename__ = "user"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="用户唯一标识"
    )

    # 用户基本信息
    username = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="用户名"
    )
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="邮箱地址"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="密码哈希值"
    )

    # 权限和状态
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否激活"
    )
    is_superuser = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否超级用户"
    )

    # 时间信息
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间"
    )
    last_login_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="最后登录时间"
    )

    # 关系
    document = relationship("Document", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan", lazy="selectin")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="check_valid_email"
        ),
        Index("idx_users_username", "username", unique=True),
        Index("idx_users_email", "email", unique=True),
        Index("idx_users_is_active", "is_active"),
        Index("idx_users_created_at", "created_at"),
        {"comment": "用户表"}
    )

    @validates("username")
    def validate_username(self, key, value):
        """验证用户名"""
        if not value or len(value.strip()) == 0:
            raise ValueError("用户名不能为空")
        if len(value) > 50:
            raise ValueError("用户名长度不能超过50个字符")
        return value.strip()

    @validates("email")
    def validate_email(self, key, value):
        """验证邮箱地址"""
        if not value or len(value.strip()) == 0:
            raise ValueError("邮箱地址不能为空")
        if len(value) > 255:
            raise ValueError("邮箱地址长度不能超过255个字符")
        # 简单的邮箱格式验证
        if "@" not in value or "." not in value:
            raise ValueError("邮箱地址格式不正确")
        return value.strip().lower()

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """将模型转换为字典"""
        result = {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

        if include_sensitive:
            # 注意：通常不返回密码哈希
            result["password_hash"] = self.password_hash

        return result

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class SearchHistory(Base):
    """
    搜索历史模型

    对应数据库表: search_history
    记录用户的搜索历史
    """

    __tablename__ = "search_history"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="搜索历史唯一标识"
    )

    # 外键关联
    user_id = Column(
        BigInteger,
        ForeignKey("user.id"),
        nullable=True,
        comment="用户ID"
    )

    # 搜索信息
    query_text = Column(
        Text,
        nullable=False,
        comment="搜索查询文本"
    )
    search_type = Column(
        String(20),
        nullable=False,
        default="hybrid",
        comment="搜索类型：keyword, semantic, hybrid, graph"
    )
    total_results = Column(
        Integer,
        nullable=True,
        comment="总结果数量"
    )
    processing_time_ms = Column(
        Integer,
        nullable=True,
        comment="处理时间（毫秒）"
    )

    # 搜索参数
    filters = Column(
        JSON,
        nullable=False,
        default={},
        server_default="{}",
        comment="搜索过滤器（JSON格式）"
    )
    search_params = Column(
        JSON,
        nullable=False,
        default={},
        server_default="{}",
        comment="搜索参数（JSON格式）"
    )

    # 时间戳
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )

    # 关系
    user = relationship("User", back_populates="search_history", lazy="selectin")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "search_type IN ('keyword', 'semantic', 'hybrid', 'graph')",
            name="check_search_type"
        ),
        Index("idx_search_history_user_id", "user_id"),
        Index("idx_search_history_created_at", "created_at"),
        Index("idx_search_history_search_type", "search_type"),
        {"comment": "搜索历史表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "query_text": self.query_text,
            "search_type": self.search_type,
            "total_results": self.total_results,
            "processing_time_ms": self.processing_time_ms,
            "filters": self.filters,
            "search_params": self.search_params,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, user_id={self.user_id}, query='{self.query_text[:50]}...')>"
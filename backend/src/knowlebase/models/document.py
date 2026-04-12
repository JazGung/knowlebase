"""
文档数据库模型

包含文档元数据和相关关系的SQLAlchemy模型
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Boolean,
    Text,
    JSON,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates

from knowlebase.db.session import Base


class Document(Base):
    """
    文档元数据模型

    对应数据库表: document
    """

    __tablename__ = "document"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="文档唯一标识"
    )

    # 用户关联（未来扩展）
    user_id = Column(
        BigInteger,
        ForeignKey("user.id"),
        nullable=True,
        comment="上传用户ID"
    )

    # 文档基本信息
    title = Column(
        String(500),
        nullable=False,
        comment="文档标题"
    )
    description = Column(
        Text,
        nullable=True,
        comment="文档描述"
    )

    # 文件信息
    original_filename = Column(
        String(255),
        nullable=False,
        comment="原始文件名"
    )
    file_hash = Column(
        String(32),
        nullable=False,
        index=True,
        unique=True,
        comment="文件MD5哈希值（32位十六进制）"
    )
    file_size = Column(
        BigInteger,
        nullable=True,
        comment="文件大小（字节）"
    )
    mime_type = Column(
        String(100),
        nullable=True,
        comment="文件MIME类型"
    )
    file_path = Column(
        String(500),
        nullable=True,
        comment="文件存储路径（兼容旧字段）"
    )

    # 文档状态
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="文档状态：pending, processing, success, failed, deleted"
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用（可用于知识库重建）"
    )

    # 处理信息
    processing_id = Column(
        String(36),
        nullable=True,
        comment="当前处理任务ID"
    )
    processing_number = Column(
        Integer,
        nullable=False,
        default=1,
        comment="处理次数（第几次处理）"
    )
    chunk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="分块数量"
    )
    total_tokens = Column(
        Integer,
        nullable=False,
        default=0,
        comment="总token数量"
    )
    embedding_model = Column(
        String(50),
        nullable=True,
        comment="使用的向量嵌入模型"
    )

    # 元数据
    category = Column(
        String(100),
        nullable=True,
        comment="文档分类"
    )
    tag = Column(
        ARRAY(String),
        nullable=True,
        default=[],
        comment="文档标签数组"
    )
    language = Column(
        String(10),
        nullable=False,
        default="zh",
        comment="文档语言代码"
    )
    source_type = Column(
        String(50),
        nullable=True,
        default="upload",
        comment="来源类型：upload, api, crawl, import"
    )

    # 重建关联
    rebuild_id = Column(
        String(36),
        nullable=True,
        comment="关联的重建记录ID"
    )

    # 时间戳
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
    processed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="最后处理完成时间"
    )

    # 关系
    user = relationship("User", back_populates="document", lazy="selectin")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="selectin")
    processing_history = relationship("DocumentProcessingHistory", back_populates="document", cascade="all, delete-orphan", lazy="selectin")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'success', 'failed', 'deleted')",
            name="check_document_status"
        ),
        CheckConstraint(
            "source_type IN ('upload', 'api', 'crawl', 'import')",
            name="check_document_source_type"
        ),
        CheckConstraint(
            "processing_number >= 1",
            name="check_processing_number_positive"
        ),
        Index("idx_documents_file_hash", "file_hash", unique=True),
        Index("idx_documents_status", "status"),
        Index("idx_documents_enabled", "enabled"),
        Index("idx_documents_created_at", "created_at"),
        Index("idx_documents_category", "category"),
        Index("idx_document_tag", "tag", postgresql_using="gin"),
        {"comment": "文档元数据表"}
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

    @validates("status")
    def validate_status(self, key, value):
        """验证状态值"""
        valid_statuses = {"pending", "processing", "success", "failed", "deleted"}
        if value not in valid_statuses:
            raise ValueError(f"状态必须是以下值之一: {', '.join(valid_statuses)}")
        return value

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """将模型转换为字典"""
        result = {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "original_filename": self.original_filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "enabled": self.enabled,
            "processing_id": self.processing_id,
            "processing_number": self.processing_number,
            "chunk_count": self.chunk_count,
            "total_tokens": self.total_tokens,
            "embedding_model": self.embedding_model,
            "category": self.category,
            "tag": self.tag or [],
            "language": self.language,
            "source_type": self.source_type,
            "rebuild_id": self.rebuild_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

        if include_relationships:
            result["user_id"] = str(self.user_id) if self.user_id else None
            if self.chunks:
                result["chunks"] = [chunk.to_dict() for chunk in self.chunks]
            if self.processing_history:
                result["processing_history"] = [history.to_dict() for history in self.processing_history]

        return result

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.original_filename}', status='{self.status}')>"


class DocumentProcessingHistory(Base):
    """
    文档处理历史记录模型

    对应数据库表: document_processing_history
    记录每次文档处理的详细历史
    """

    __tablename__ = "document_processing_history"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="处理历史记录唯一标识"
    )

    # 外键关联
    document_id = Column(
        BigInteger,
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档ID"
    )

    # 处理信息
    processing_id = Column(
        String(36),
        nullable=False,
        comment="处理任务ID"
    )
    processing_number = Column(
        Integer,
        nullable=False,
        comment="处理次数（第几次处理）"
    )
    status = Column(
        String(20),
        nullable=False,
        comment="处理状态：pending, processing, success, failed"
    )
    current_stage = Column(
        String(50),
        nullable=True,
        comment="当前处理阶段"
    )
    progress = Column(
        Integer,
        nullable=False,
        default=0,
        comment="处理进度（0-100）"
    )

    # 时间信息
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="处理开始时间"
    )
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="处理完成时间"
    )

    # 错误信息
    error_message = Column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 处理结果
    result = Column(
        JSON,
        nullable=True,
        comment="处理结果（JSON格式）"
    )

    # 阶段详情
    stages = Column(
        JSON,
        nullable=True,
        comment="处理阶段详情（JSON数组）"
    )

    # 时间戳
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )

    # 关系
    document = relationship("Document", back_populates="processing_history", lazy="selectin")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'success', 'failed')",
            name="check_processing_status"
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="check_progress_range"
        ),
        UniqueConstraint("document_id", "processing_number", name="uq_document_processing_number"),
        Index("idx_processing_history_document_id", "document_id"),
        Index("idx_processing_history_processing_id", "processing_id"),
        Index("idx_processing_history_status", "status"),
        Index("idx_processing_history_created_at", "created_at"),
        {"comment": "文档处理历史记录表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "processing_id": self.processing_id,
            "processing_number": self.processing_number,
            "status": self.status,
            "current_stage": self.current_stage,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "result": self.result,
            "stages": self.stages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocumentProcessingHistory(id={self.id}, document_id={self.document_id}, status='{self.status}', progress={self.progress}%)>"


# 注意：DocumentChunk模型在单独的chunk.py文件中定义
# User模型在user.py文件中定义
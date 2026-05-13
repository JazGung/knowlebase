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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates

from knowlebase.db.session import Base
from knowlebase.models.processing_stage_result import ProcessingStageResult  # noqa: F401


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

    # 用户关联（跨模块，仅存ID值，无外键）
    user_id = Column(
        BigInteger,
        nullable=True,
        comment="上传用户ID"
    )

    # 文档基本信息
    title = Column(
        String(500),
        nullable=False,
        comment="文档标题"
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
        default="enabled",
        comment="文档状态：enabled/disabled"
    )

    # 处理信息
    processing_id = Column(
        String(36),
        nullable=True,
        comment="当前处理任务ID（跨领域引用，无外键约束）"
    )
    attempt_no = Column(
        Integer,
        nullable=False,
        default=1,
        comment="处理次数"
    )
    chunk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="分块数量"
    )
    total_token = Column(
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
    language = Column(
        String(10),
        nullable=False,
        default="zh",
        comment="文档语言代码"
    )
    # 关联构建记录
    build_id = Column(
        String(36),
        nullable=True,
        comment="关联的构建记录ID"
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
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="selectin")

    # 约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('enabled', 'disabled')",
            name="check_document_status"
        ),
        CheckConstraint(
            "attempt_no >= 1",
            name="check_attempt_no_positive"
        ),
        Index("idx_documents_file_hash", "file_hash", unique=True),
        Index("idx_documents_created_at", "created_at"),
        {"comment": "文档元数据表"}
    )

    @validates("file_hash")
    def validate_file_hash(self, key, value):
        """验证文件哈希格式"""
        if not value or len(value) != 32:
            raise ValueError("文件哈希必须是32位十六进制字符串")
        try:
            int(value, 16)
        except ValueError:
            raise ValueError("文件哈希必须是有效的十六进制字符串")
        return value.lower()

    @validates("status")
    def validate_status(self, key, value):
        """验证状态值"""
        valid_statuses = {"enabled", "disabled"}
        if value not in valid_statuses:
            raise ValueError(f"状态必须是以下值之一: {', '.join(valid_statuses)}")
        return value

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """将模型转换为字典"""
        result = {
            "id": str(self.id),
            "title": self.title,
            "original_filename": self.original_filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "processing_id": self.processing_id,
            "attempt_no": self.attempt_no,
            "chunk_count": self.chunk_count,
            "total_token": self.total_token,
            "embedding_model": self.embedding_model,
            "language": self.language,
            "build_id": self.build_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

        if include_relationships:
            result["user_id"] = str(self.user_id) if self.user_id else None
            if self.chunks:
                result["chunks"] = [chunk.to_dict() for chunk in self.chunks]

        return result

    # ---- 领域方法 ----

    @property
    def enabled(self) -> bool:
        """启用状态（兼容属性）"""
        return self.status == "enabled"

    def enable(self) -> None:
        """启用文档"""
        self.status = "enabled"
        self.updated_at = datetime.now()

    def disable(self) -> None:
        """停用文档"""
        self.status = "disabled"
        self.updated_at = datetime.now()

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
    relation_id = Column(
        BigInteger,
        ForeignKey("document_version_relation.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 document_version_relation.id"
    )

    # 处理信息
    processing_id = Column(
        String(36),
        nullable=False,
        comment="处理任务ID"
    )
    attempt_no = Column(
        Integer,
        nullable=False,
        comment="处理次数（第几次处理）"
    )
    status = Column(
        String(20),
        nullable=False,
        comment="处理状态：pending/processing/succeeded/failed"
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
        nullable=False,
        server_default=func.current_timestamp(),
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

    # 时间戳
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )

    # 关系
    relation = relationship(
        "DocumentVersionRelation",
        back_populates="processing_histories",
        foreign_keys=[relation_id],
        lazy="selectin"
    )
    stage_results = relationship(
        "ProcessingStageResult",
        back_populates="processing_history",
        foreign_keys="ProcessingStageResult.processing_id",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # 约束
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed')",
            name="check_processing_status"
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="check_progress_range"
        ),
        UniqueConstraint("relation_id", "attempt_no", name="uk_history_relation_attempt_no"),
        UniqueConstraint("processing_id", name="uk_history_processing_id"),
        Index("idx_processing_history_relation_id", "relation_id"),
        Index("idx_processing_history_processing_id", "processing_id"),
        {"comment": "文档处理历史记录表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "relation_id": str(self.relation_id),
            "processing_id": self.processing_id,
            "attempt_no": self.attempt_no,
            "status": self.status,
            "current_stage": self.current_stage,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    # ---- 领域方法 ----

    def add_stage_result(self, stage_result: "ProcessingStageResult") -> None:
        """添加阶段结果，维护双向关联"""
        stage_result.processing_history = self
        if stage_result not in (self.stage_results or []):
            self.stage_results = (self.stage_results or []) + [stage_result]

    def mark_succeeded(self) -> None:
        """标记处理成功"""
        self.status = "succeeded"
        self.progress = 100
        self.completed_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """标记处理失败"""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.now()

    def update_progress(self, stage: str, progress: int) -> None:
        """更新处理进度"""
        self.current_stage = stage
        self.progress = progress

    def __repr__(self):
        return f"<DocumentProcessingHistory(id={self.id}, relation_id={self.relation_id}, status='{self.status}', progress={self.progress}%)>"


# 注意：DocumentChunk模型在单独的chunk.py文件中定义
# User模型在user.py文件中定义

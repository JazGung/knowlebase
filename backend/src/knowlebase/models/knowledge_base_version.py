"""
知识库版本数据库模型

包含知识库版本元数据的SQLAlchemy模型
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Integer,
    Text,
    TIMESTAMP,
    Index,
)
from sqlalchemy.sql import func

from knowlebase.db.session import Base


class KnowledgeBaseVersion(Base):
    """
    知识库版本模型

    对应数据库表: knowledge_base_version
    """

    __tablename__ = "knowledge_base_version"

    # 主键
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="版本唯一标识"
    )

    # 版本名称
    version_name = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="版本名称（v+时间戳格式 v20260422_103000）"
    )

    # 状态
    status = Column(
        String(20),
        nullable=False,
        default="init",
        comment="版本状态：init|building|succeeded|enabled|disabled|failed"
    )

    # 统计信息
    document_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="包含的文档数"
    )
    chunk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="包含的chunk总数"
    )

    # 错误信息
    error_message = Column(
        Text,
        nullable=True,
        comment="失败时的错误信息"
    )

    # 操作人
    created_by = Column(
        String(100),
        nullable=True,
        comment="操作人"
    )

    # 时间戳
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="开始时间"
    )
    completed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="完成时间"
    )
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

    # 索引
    __table_args__ = (
        Index("idx_kb_version_status", "status"),
        {"comment": "知识库版本表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "version_name": self.version_name,
            "status": self.status,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_by": self.created_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    # ---- 领域方法 ----

    def start_build(self) -> None:
        """开始构建，校验 status 为 init 或 failed"""
        status = self.status or "init"
        if status not in ("init", "failed"):
            raise ValueError(f"版本状态为 {self.status}，无法构建（需为 init 或 failed）")
        self.status = "building"
        self.started_at = datetime.now()

    def complete_build(self, document_count: int, chunk_count: int) -> None:
        """构建成功完成"""
        if self.status != "building":
            raise ValueError(f"版本状态为 {self.status}，无法完成构建（需为 building）")
        self.status = "succeeded"
        self.document_count = document_count
        self.chunk_count = chunk_count
        self.completed_at = datetime.now()

    def fail_build(self, error_message: str) -> None:
        """构建失败"""
        if self.status != "building":
            raise ValueError(f"版本状态为 {self.status}，无法标记失败（需为 building）")
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.now()

    def enable(self) -> None:
        """启用版本"""
        if self.status not in ("succeeded", "disabled"):
            raise ValueError(f"版本状态为 {self.status}，无法启用（需为 succeeded 或 disabled）")
        self.status = "enabled"
        self.updated_at = datetime.now()

    def __repr__(self):
        return f"<KnowledgeBaseVersion(id={self.id}, version_name={self.version_name}, status={self.status})>"

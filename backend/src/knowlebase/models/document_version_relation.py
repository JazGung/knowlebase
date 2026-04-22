"""
文档-版本关联数据库模型

包含文档与知识库版本关联关系的SQLAlchemy模型
"""

from typing import Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from knowlebase.db.session import Base


class DocumentVersionRelation(Base):
    """
    文档-版本关联模型

    对应数据库表: document_version_relation
    """

    __tablename__ = "document_version_relation"

    # 主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="关联唯一标识"
    )

    # 外键关联
    document_id = Column(
        BigInteger,
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档ID"
    )
    version_id = Column(
        BigInteger,
        ForeignKey("knowledge_base_version.id", ondelete="CASCADE"),
        nullable=False,
        comment="版本ID"
    )

    # 关联信息
    relation_type = Column(
        String(20),
        nullable=False,
        comment="关联类型：initial|incremental|reprocessed"
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="处理状态：pending|processing|succeeded|failed"
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

    # 关系
    document = relationship("Document", lazy="selectin")
    version = relationship("KnowledgeBaseVersion", back_populates="document_relations", lazy="selectin")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint("document_id", "version_id", name="uq_document_version"),
        Index("idx_doc_ver_relation_document", "document_id"),
        Index("idx_doc_ver_relation_version", "version_id"),
        Index("idx_doc_ver_relation_status", "status"),
        {"comment": "文档-版本关联表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "version_id": str(self.version_id),
            "relation_type": self.relation_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<DocumentVersionRelation(doc_id={self.document_id}, ver_id={self.version_id}, type={self.relation_type})>"

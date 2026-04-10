"""
文档分块数据库模型

包含文档分块元数据的SQLAlchemy模型
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
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


class DocumentChunk(Base):
    """
    文档分块模型

    对应数据库表: document_chunks
    存储文档分块的元数据，实际内容存储在ElasticSearch中
    """

    __tablename__ = "document_chunks"

    # 主键
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        comment="分块唯一标识"
    )

    # 外键关联
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档ID"
    )

    # 分块信息
    chunk_index = Column(
        Integer,
        nullable=False,
        comment="分块索引（从0开始）"
    )
    chunk_size = Column(
        Integer,
        nullable=False,
        comment="分块大小（字符数）"
    )
    token_count = Column(
        Integer,
        nullable=False,
        comment="分块token数量"
    )

    # 向量信息
    vector_id = Column(
        String(100),
        nullable=True,
        comment="Milvus中的向量ID"
    )
    embedding_model = Column(
        String(50),
        nullable=True,
        comment="使用的向量嵌入模型"
    )

    # 位置信息
    page_number = Column(
        Integer,
        nullable=True,
        comment="页码（PDF文档）"
    )
    section_title = Column(
        String(500),
        nullable=True,
        comment="章节标题"
    )
    start_position = Column(
        Integer,
        nullable=True,
        comment="在文档中的起始位置"
    )
    end_position = Column(
        Integer,
        nullable=True,
        comment="在文档中的结束位置"
    )

    # 元数据
    chunk_metadata = Column(
        JSON,
        nullable=False,
        default={},
        server_default="{}",
        comment="分块元数据（JSON格式）"
    )

    # 时间戳
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )

    # 关系
    document = relationship("Document", back_populates="chunks", lazy="selectin")

    # 约束
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="check_chunk_index_positive"),
        CheckConstraint("chunk_size > 0", name="check_chunk_size_positive"),
        CheckConstraint("token_count >= 0", name="check_token_count_nonnegative"),
        Index("idx_document_chunks_document_id", "document_id"),
        Index("idx_document_chunks_chunk_index", "chunk_index"),
        Index("idx_document_chunks_vector_id", "vector_id"),
        Index("idx_document_chunks_metadata", "chunk_metadata", postgresql_using="gin"),
        Index("idx_document_chunks_page_number", "page_number"),
        {"comment": "文档分块元数据表"}
    )

    @validates("chunk_index")
    def validate_chunk_index(self, key, value):
        """验证分块索引"""
        if value < 0:
            raise ValueError("分块索引不能为负数")
        return value

    @validates("chunk_size")
    def validate_chunk_size(self, key, value):
        """验证分块大小"""
        if value <= 0:
            raise ValueError("分块大小必须大于0")
        return value

    @validates("token_count")
    def validate_token_count(self, key, value):
        """验证token数量"""
        if value < 0:
            raise ValueError("token数量不能为负数")
        return value

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "chunk_index": self.chunk_index,
            "chunk_size": self.chunk_size,
            "token_count": self.token_count,
            "vector_id": self.vector_id,
            "embedding_model": self.embedding_model,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "metadata": self.chunk_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index}, size={self.chunk_size})>"
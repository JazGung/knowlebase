"""
文档分块数据库模型

对应 DEG 1.1.5 document_chunk 表设计。
"""

from typing import Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Text,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates

from knowlebase.db.session import Base


class DocumentChunk(Base):
    """文档分块模型 — 对应 document_chunk 表"""

    __tablename__ = "document_chunk"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键，自增"
    )

    document_id = Column(
        BigInteger,
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 document.id"
    )

    chunk_index = Column(
        Integer,
        nullable=False,
        comment="分块序号，从 0 递增"
    )

    original_text = Column(
        Text,
        nullable=False,
        comment="原始文本，调测用"
    )

    processed_text = Column(
        Text,
        nullable=False,
        comment="处理后文本"
    )

    processed_text_token_count = Column(
        Integer,
        nullable=False,
        comment="processed_text 的 token 数"
    )

    hypothetical_questions = Column(
        "hypothetical_questions",
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="假设性问题列表"
    )

    hypothetical_questions_token_count = Column(
        Integer,
        nullable=False,
        comment="拼接后文本的 token 数"
    )

    relations = Column(
        "relations",
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="关系三元组列表"
    )

    page_range_start = Column(
        Integer,
        nullable=False,
        comment="起始页码"
    )

    page_range_end = Column(
        Integer,
        nullable=False,
        comment="结束页码"
    )

    section_title = Column(
        String(500),
        nullable=False,
        default="",
        comment="所属章节标题"
    )

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
        UniqueConstraint("document_id", "chunk_index", name="uk_document_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="check_chunk_index_nonnegative"),
        Index("idx_chunk_document_id", "document_id"),
        {"comment": "文档分块表"}
    )

    @validates("chunk_index")
    def validate_chunk_index(self, key, value):
        if value < 0:
            raise ValueError("分块序号不能为负数")
        return value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "chunk_index": self.chunk_index,
            "original_text": self.original_text,
            "processed_text": self.processed_text,
            "processed_text_token_count": self.processed_text_token_count,
            "hypothetical_questions": self.hypothetical_questions or [],
            "hypothetical_questions_token_count": self.hypothetical_questions_token_count,
            "relations": self.relations or [],
            "page_range_start": self.page_range_start,
            "page_range_end": self.page_range_end,
            "section_title": self.section_title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"

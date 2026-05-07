"""
处理阶段结果模型

对应 DEG 文档 processing_stage_result 表
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
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from knowlebase.db.session import Base


class ProcessingStageResult(Base):
    """处理阶段结果"""

    __tablename__ = "processing_stage_result"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键"
    )

    processing_id = Column(
        String(36),
        ForeignKey("document_processing_history.processing_id", ondelete="CASCADE"),
        nullable=False,
        comment="关联 document_processing_history.processing_id"
    )

    stage_name = Column(
        String(50),
        nullable=False,
        comment="阶段名：check/parsed/cleaned/images_described/chunked/stored"
    )

    status = Column(
        String(20),
        nullable=False,
        comment="running/succeeded/failed"
    )

    duration_ms = Column(
        Integer,
        nullable=False,
        comment="阶段耗时（毫秒）"
    )

    result_path = Column(
        String(500),
        nullable=True,
        comment="MinIO 路径"
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="失败原因"
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="记录时间"
    )

    # 关系
    processing_history = relationship(
        "DocumentProcessingHistory",
        back_populates="stage_results",
        foreign_keys=[processing_id],
        lazy="selectin"
    )

    # 约束
    __table_args__ = (
        Index("idx_stage_processing_id", "processing_id"),
        {"comment": "处理阶段结果表"}
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "processing_id": self.processing_id,
            "stage_name": self.stage_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "result_path": self.result_path,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (
            f"<ProcessingStageResult(id={self.id}, "
            f"processing_id={self.processing_id}, "
            f"stage='{self.stage_name}', "
            f"status='{self.status}')>"
        )

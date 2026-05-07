"""
Repository 基础设施层

每个 Repository 一对一管理对应领域对象的持久化操作。
"""

from knowlebase.repositories.document_repository import DocumentRepository
from knowlebase.repositories.processing_history_repository import ProcessingHistoryRepository
from knowlebase.repositories.stage_result_repository import StageResultRepository

__all__ = [
    "DocumentRepository",
    "ProcessingHistoryRepository",
    "StageResultRepository",
]

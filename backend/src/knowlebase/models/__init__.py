"""
SQLAlchemy数据库模型模块
"""

from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.models.chunk import DocumentChunk
from knowlebase.models.user import User, SearchHistory
from knowlebase.models.file_cleanup import FileCleanupLog, SystemConfig
from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
from knowlebase.models.document_version_relation import DocumentVersionRelation

__all__ = [
    "Document",
    "DocumentProcessingHistory",
    "DocumentChunk",
    "User",
    "SearchHistory",
    "FileCleanupLog",
    "SystemConfig",
    "KnowledgeBaseVersion",
    "DocumentVersionRelation",
]
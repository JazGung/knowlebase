"""
单元测试 - DocumentService 业务逻辑（不依赖真实数据库和 Minio）
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from knowlebase.admin.document.service import DocumentService
from knowlebase.schemas.document import DocumentListQuery


def make_mock_document(overrides: dict = None) -> MagicMock:
    """创建 mock Document 对象"""
    doc = MagicMock()
    doc.id = f"doc_{uuid.uuid4().hex[:8]}"
    doc.user_id = None
    doc.title = "Test Document"
    doc.description = "Test description"
    doc.original_filename = "test.pdf"
    doc.file_hash = "a" * 32
    doc.file_size = 1024
    doc.mime_type = "application/pdf"
    doc.file_path = None
    doc.status = "success"
    doc.enabled = True
    doc.processing_id = None
    doc.processing_number = 1
    doc.chunk_count = 0
    doc.total_tokens = 0
    doc.embedding_model = None
    doc.category = None
    doc.tag = []
    doc.language = "zh"
    doc.source_type = "upload"
    doc.rebuild_id = None
    doc.created_at = datetime.now()
    doc.updated_at = datetime.now()
    doc.processed_at = None
    if overrides:
        for key, value in overrides.items():
            setattr(doc, key, value)
    return doc


def make_mock_processing(overrides: dict = None) -> MagicMock:
    """创建 mock DocumentProcessingHistory 对象"""
    proc = MagicMock()
    proc.id = f"proc_{uuid.uuid4().hex[:8]}"
    proc.document_id = "doc_test"
    proc.processing_number = 1
    proc.status = "success"
    proc.current_stage = "completed"
    proc.progress = 100
    proc.started_at = datetime.now()
    proc.completed_at = datetime.now()
    proc.error_message = None
    proc.result = {"chunks_count": 5, "vector_count": 5}
    proc.stages = []
    if overrides:
        for key, value in overrides.items():
            setattr(proc, key, value)
    return proc


class TestGetDocumentList:
    """测试文档列表查询"""

    @pytest.fixture
    def service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        mock_db = AsyncMock()
        mock_total_result = AsyncMock()
        mock_total_result.scalar_one = MagicMock(return_value=0)
        mock_list_result = AsyncMock()
        mock_list_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_total_result
            return mock_list_result

        mock_db.execute = mock_execute

        result = await service.get_document_list(mock_db, DocumentListQuery())
        assert result["documents"] == []
        assert result["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_with_documents(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_total_result = AsyncMock()
        mock_total_result.scalar_one = MagicMock(return_value=1)
        mock_list_result = AsyncMock()
        mock_list_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[doc])))

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_total_result
            return mock_list_result

        mock_db.execute = mock_execute

        result = await service.get_document_list(mock_db, DocumentListQuery())
        assert len(result["documents"]) == 1
        assert result["pagination"]["total"] == 1

    @pytest.mark.asyncio
    async def test_search_filter(self, service):
        mock_db = AsyncMock()
        mock_total_result = AsyncMock()
        mock_total_result.scalar_one = MagicMock(return_value=0)
        mock_list_result = AsyncMock()
        mock_list_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_total_result
            return mock_list_result

        mock_db.execute = mock_execute

        await service.get_document_list(mock_db, DocumentListQuery(search="test"))
        # 验证查询包含搜索条件 - 通过调用次数确认执行了
        assert call_count == 2


class TestGetDocumentDetail:
    """测试文档详情查询"""

    @pytest.fixture
    def service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_existing_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        proc = make_mock_processing()

        doc_result = AsyncMock()
        doc_result.scalar_one_or_none = MagicMock(return_value=doc)
        proc_result = AsyncMock()
        proc_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[proc])))

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return doc_result
            return proc_result

        mock_db.execute = mock_execute

        result = await service.get_document_detail(mock_db, "doc_test")
        assert result is not None
        assert "document" in result
        assert "processing_history" in result
        assert result["total_processings"] == 1

    @pytest.mark.asyncio
    async def test_nonexistent_document(self, service):
        mock_db = AsyncMock()
        doc_result = AsyncMock()
        doc_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = mock_execute = AsyncMock(return_value=doc_result)

        result = await service.get_document_detail(mock_db, "doc_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_document_without_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        doc_result = AsyncMock()
        doc_result.scalar_one_or_none = MagicMock(return_value=doc)
        proc_result = AsyncMock()
        proc_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return doc_result
            return proc_result

        mock_db.execute = mock_execute

        result = await service.get_document_detail(mock_db, "doc_test")
        assert result is not None
        assert result["processing_history"] == []
        assert result["total_processings"] == 0


class TestEnableDocument:
    """测试启用文档"""

    @pytest.fixture
    def service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_enable_existing_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"enabled": False})
        mock_db.get = AsyncMock(return_value=doc)

        await service.enable_document(mock_db, doc.id)
        assert doc.enabled is True
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.enable_document(mock_db, "doc_nonexistent")
        assert exc_info.value.status_code == 404


class TestDisableDocument:
    """测试停用文档"""

    @pytest.fixture
    def service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_disable_existing_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"enabled": True})
        mock_db.get = AsyncMock(return_value=doc)

        await service.disable_document(mock_db, doc.id)
        assert doc.enabled is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.disable_document(mock_db, "doc_nonexistent")
        assert exc_info.value.status_code == 404


class TestReprocessDocument:
    """测试重新处理文档"""

    @pytest.fixture
    def service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_reprocess_new(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.get = AsyncMock(return_value=doc)

        max_result = AsyncMock()
        max_result.scalar_one = MagicMock(return_value=0)
        mock_db.execute = AsyncMock(return_value=max_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.reprocess_document(mock_db, doc.id)
        assert result["document_id"] == doc.id
        assert result["processing_number"] == 1
        assert "processing_id" in result
        assert "progress_stream_url" in result

    @pytest.mark.asyncio
    async def test_reprocess_with_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.get = AsyncMock(return_value=doc)

        max_result = AsyncMock()
        max_result.scalar_one = MagicMock(return_value=3)
        mock_db.execute = AsyncMock(return_value=max_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.reprocess_document(mock_db, doc.id)
        assert result["processing_number"] == 4

    @pytest.mark.asyncio
    async def test_reprocess_nonexistent_document(self, service):
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await service.reprocess_document(mock_db, "doc_nonexistent")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reprocess_integer_id_returns_string(self, service):
        """service 接收整数 document_id 时，返回的 document_id 必须是字符串"""
        mock_db = AsyncMock()
        doc = make_mock_document()
        doc.id = 18  # 模拟数据库自增 ID
        mock_db.get = AsyncMock(return_value=doc)

        max_result = AsyncMock()
        max_result.scalar_one = MagicMock(return_value=0)
        mock_db.execute = AsyncMock(return_value=max_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.reprocess_document(mock_db, 18)
        assert isinstance(result["document_id"], str), f"document_id 应为 str, 实际是 {type(result['document_id']).__name__}"
        assert result["document_id"] == "18"

    @pytest.mark.asyncio
    async def test_reprocess_processing_document(self, service):
        """文档正在处理中时抛出 HTTPException"""
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "processing"})
        mock_db.get = AsyncMock(return_value=doc)

        with pytest.raises(HTTPException) as exc_info:
            await service.reprocess_document(mock_db, 5)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reprocess_deleted_document(self, service):
        """已删除文档抛出 HTTPException"""
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "deleted"})
        mock_db.get = AsyncMock(return_value=doc)

        with pytest.raises(HTTPException) as exc_info:
            await service.reprocess_document(mock_db, 5)
        assert exc_info.value.status_code == 400

"""
单元测试 - DocumentService 业务逻辑（mock Repository 层）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from knowlebase.admin.document.service import DocumentService
from knowlebase.schemas.document import DocumentListQuery


def make_mock_document(overrides: dict = None) -> MagicMock:
    doc = MagicMock()
    doc.enable = MagicMock(side_effect=lambda: setattr(doc, "status", "enabled"))
    doc.disable = MagicMock(side_effect=lambda: setattr(doc, "status", "disabled"))
    doc.id = 123
    doc.user_id = None
    doc.title = "Test Document"
    doc.original_filename = "test.pdf"
    doc.file_hash = "a" * 32
    doc.file_size = 1024
    doc.mime_type = "application/pdf"
    doc.status = "enabled"
    doc.processing_id = None
    doc.attempt_no = 1
    doc.chunk_count = 0
    doc.total_token = 0
    doc.embedding_model = None
    doc.language = "zh"
    doc.source_type = "upload"
    doc.rebuild_id = None
    if overrides:
        for key, value in overrides.items():
            setattr(doc, key, value)
    return doc


def make_mock_processing(overrides: dict = None) -> MagicMock:
    proc = MagicMock()
    proc.id = 1
    proc.document_id = 123
    proc.processing_id = "proc_test12345"
    proc.attempt_no = 1
    proc.status = "succeeded"
    proc.current_stage = "stored"
    proc.progress = 100
    proc.started_at = None
    proc.completed_at = None
    proc.error_message = None
    if overrides:
        for key, value in overrides.items():
            setattr(proc, key, value)
    return proc


@pytest.fixture
def service():
    return DocumentService()


def _patch_repos(mock_doc_repo_class, mock_hist_repo_class):
    """辅助: 创建 patched repository 实例"""
    mock_doc_repo = MagicMock()
    mock_hist_repo = MagicMock()
    mock_doc_repo_class.return_value = mock_doc_repo
    mock_hist_repo_class.return_value = mock_hist_repo
    return mock_doc_repo, mock_hist_repo


class TestGetDocumentList:

    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([], 0))
            mock_repo_cls.return_value = mock_repo

            result = await service.get_document_list(mock_db, DocumentListQuery())
            assert result["data"] == []
            assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_with_documents(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([doc], 1))
            mock_repo_cls.return_value = mock_repo

            result = await service.get_document_list(mock_db, DocumentListQuery())
            assert len(result["data"]) == 1
            assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_search_passed_to_repo(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([], 0))
            mock_repo_cls.return_value = mock_repo

            await service.get_document_list(mock_db, DocumentListQuery(search="test"))
            call_args = mock_repo.list_with_filters.call_args
            assert call_args[1]["search"] == "test"

    @pytest.mark.asyncio
    async def test_status_filter_passed_to_repo(self, service):
        mock_db = AsyncMock()
        from knowlebase.schemas.document import DocumentStatus
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([], 0))
            mock_repo_cls.return_value = mock_repo

            await service.get_document_list(mock_db, DocumentListQuery(status=DocumentStatus.ENABLED))
            call_args = mock_repo.list_with_filters.call_args
            assert call_args[1]["status"] == "enabled"


class TestGetDocumentDetail:

    @pytest.mark.asyncio
    async def test_existing_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        proc = make_mock_processing()

        with (
            patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_hist.get_by_document_id = AsyncMock(return_value=[proc])

            result = await service.get_document_detail(mock_db, "123")
            assert result is not None
            assert result["document"]["id"] == 123
            assert result["total_processings"] == 1
            assert len(result["processing_history"]) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_document(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls:
            mock_doc_cls.return_value.get_by_id = AsyncMock(return_value=None)

            result = await service.get_document_detail(mock_db, "999")
            assert result is None

    @pytest.mark.asyncio
    async def test_document_without_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        with (
            patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_hist.get_by_document_id = AsyncMock(return_value=[])

            result = await service.get_document_detail(mock_db, "123")
            assert result is not None
            assert result["processing_history"] == []
            assert result["total_processings"] == 0


class TestEnableDocument:

    @pytest.mark.asyncio
    async def test_enable_disabled_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "disabled"})

        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            await service.enable_document(mock_db, "123")
            assert doc.status == "enabled"
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await service.enable_document(mock_db, "999")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_enable_already_enabled(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "enabled"})

        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            with pytest.raises(HTTPException) as exc_info:
                await service.enable_document(mock_db, "123")
            assert exc_info.value.status_code == 400


class TestDisableDocument:

    @pytest.mark.asyncio
    async def test_disable_enabled_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "enabled"})

        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            await service.disable_document(mock_db, "123")
            assert doc.status == "disabled"
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await service.disable_document(mock_db, "999")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_already_disabled(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "disabled"})

        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            with pytest.raises(HTTPException) as exc_info:
                await service.disable_document(mock_db, "123")
            assert exc_info.value.status_code == 400


class TestProcessDocuments:

    @pytest.mark.asyncio
    async def test_process_single_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        with (
            patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_hist.has_active_processing = AsyncMock(return_value=False)
            mock_hist.get_max_attempt_no = AsyncMock(return_value=0)

            results = await service.process_documents(mock_db, [123])
            assert len(results) == 1
            assert results[0].status == "success"

    @pytest.mark.asyncio
    async def test_process_with_existing_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        with (
            patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_hist.has_active_processing = AsyncMock(return_value=False)
            mock_hist.get_max_attempt_no = AsyncMock(return_value=3)

            results = await service.process_documents(mock_db, [5])
            assert results[0].status == "success"

    @pytest.mark.asyncio
    async def test_process_nonexistent_document(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            results = await service.process_documents(mock_db, [999])
            assert results[0].status == "failed"
            assert "不存在" in results[0].reason

    @pytest.mark.asyncio
    async def test_process_document_with_active_processing(self, service):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        with (
            patch("knowlebase.admin.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=make_mock_document())
            mock_hist.has_active_processing = AsyncMock(return_value=True)

            results = await service.process_documents(mock_db, [5])
            assert results[0].status == "failed"
            assert "处理中" in results[0].reason

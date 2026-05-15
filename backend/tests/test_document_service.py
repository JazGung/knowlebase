"""
单元测试 - DocumentService 业务逻辑（mock Repository 层）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from knowlebase.resource.document.service import DocumentService
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
    doc.build_id = None
    if overrides:
        for key, value in overrides.items():
            setattr(doc, key, value)
    return doc


def make_mock_processing(overrides: dict = None) -> MagicMock:
    proc = MagicMock()
    proc.id = 1
    proc.relation_id = 123
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
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
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
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([doc], 1))
            mock_repo_cls.return_value = mock_repo

            result = await service.get_document_list(mock_db, DocumentListQuery())
            assert len(result["data"]) == 1
            assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_search_passed_to_repo(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
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
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
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
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.resource.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)

            # Mock db.execute for DocumentVersionRelation query
            mock_relation = MagicMock()
            mock_relation.id = 1
            mock_relation.document_id = 123
            exec_result = AsyncMock()
            exec_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_relation])))
            mock_db.execute = AsyncMock(return_value=exec_result)

            mock_hist.get_by_relation_id = AsyncMock(return_value=[proc])

            result = await service.get_document_detail(mock_db, "123")
            assert result is not None
            assert result["document"]["id"] == 123
            assert result["total_processings"] == 1
            assert len(result["processing_history"]) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_document(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls:
            mock_doc_cls.return_value.get_by_id = AsyncMock(return_value=None)

            result = await service.get_document_detail(mock_db, "999")
            assert result is None

    @pytest.mark.asyncio
    async def test_document_without_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.resource.document.service.ProcessingHistoryRepository") as mock_hist_cls,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)

            # Mock db.execute returning no relations
            exec_result = AsyncMock()
            exec_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            mock_db.execute = AsyncMock(return_value=exec_result)

            result = await service.get_document_detail(mock_db, "123")
            assert result is not None
            assert result["processing_history"] == []
            assert result["total_processings"] == 0


class TestEnableDocument:

    @pytest.mark.asyncio
    async def test_enable_disabled_document(self, service):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        doc = make_mock_document(overrides={"status": "disabled"})

        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls,
            patch("knowlebase.resource.document.service.DocumentChunkRepository") as mock_chunk_cls,
        ):
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)
            mock_chunk = MagicMock()
            mock_chunk.update_enabled_by_document_id = AsyncMock()
            mock_chunk_cls.return_value = mock_chunk

            await service.enable_document(mock_db, "123")
            assert doc.status == "enabled"
            mock_chunk.update_enabled_by_document_id.assert_awaited_once_with(123, True)
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await service.enable_document(mock_db, "999")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_enable_already_enabled(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "enabled"})

        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            with pytest.raises(HTTPException) as exc_info:
                await service.enable_document(mock_db, "123")
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_enable_blocked_by_building(self, service):
        mock_db = AsyncMock()
        building_version = MagicMock()
        building_version.status = "building"
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=building_version)
        ))

        with pytest.raises(HTTPException) as exc_info:
            await service.enable_document(mock_db, "123")
        assert exc_info.value.status_code == 400
        assert "构建中" in str(exc_info.value.detail)


class TestDisableDocument:

    @pytest.mark.asyncio
    async def test_disable_enabled_document(self, service):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        doc = make_mock_document(overrides={"status": "enabled"})

        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls,
            patch("knowlebase.resource.document.service.DocumentChunkRepository") as mock_chunk_cls,
        ):
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)
            mock_chunk = MagicMock()
            mock_chunk.update_enabled_by_document_id = AsyncMock()
            mock_chunk_cls.return_value = mock_chunk

            await service.disable_document(mock_db, "123")
            assert doc.status == "disabled"
            mock_chunk.update_enabled_by_document_id.assert_awaited_once_with(123, False)
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disable_nonexistent_document(self, service):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await service.disable_document(mock_db, "999")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_already_disabled(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document(overrides={"status": "disabled"})

        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=doc)

            with pytest.raises(HTTPException) as exc_info:
                await service.disable_document(mock_db, "123")
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_disable_blocked_by_building(self, service):
        mock_db = AsyncMock()
        building_version = MagicMock()
        building_version.status = "building"
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=building_version)
        ))

        with pytest.raises(HTTPException) as exc_info:
            await service.disable_document(mock_db, "123")
        assert exc_info.value.status_code == 400
        assert "构建中" in str(exc_info.value.detail)


def _make_execute_side_effect(enabled_version=True, building_version=None):
    """Helper: returns a side_effect for mock_db.execute
    - 1st call: KnowledgeBaseVersion where status='enabled'
    - 2nd call: KnowledgeBaseVersion where status='building'
    """
    enabled = MagicMock() if enabled_version else None
    building = MagicMock() if building_version else None
    return AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=enabled)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=building)),
    ])


class TestProcessDocuments:

    @pytest.mark.asyncio
    async def test_process_single_document(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.resource.document.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.build.processing.service.get_processing_service") as mock_get_ps,
            patch("knowlebase.resource.document.service.asyncio.create_task") as mock_task,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            # enabled version exists, no building lock
            mock_db.execute = _make_execute_side_effect(enabled_version=True, building_version=None)
            mock_hist.has_active_processing = AsyncMock(return_value=False)
            mock_hist.get_max_attempt_no = AsyncMock(return_value=0)
            mock_hist.add = AsyncMock(return_value=None)

            mock_ps = MagicMock()
            mock_rel = MagicMock()
            mock_rel.id = 1
            mock_rel.document_id = 123
            mock_ps._get_or_create_relation = AsyncMock(return_value=mock_rel)
            mock_get_ps.return_value = mock_ps

            results = await service.process_documents(mock_db, [123])
            assert len(results) == 1
            assert results[0].status == "success"
            mock_hist.add.assert_awaited_once()
            mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_with_existing_history(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.resource.document.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.build.processing.service.get_processing_service") as mock_get_ps,
            patch("knowlebase.resource.document.service.asyncio.create_task") as mock_task,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_db.execute = _make_execute_side_effect(enabled_version=True, building_version=None)
            mock_hist.has_active_processing = AsyncMock(return_value=False)
            mock_hist.get_max_attempt_no = AsyncMock(return_value=3)
            mock_hist.add = AsyncMock(return_value=None)

            mock_ps = MagicMock()
            mock_rel = MagicMock()
            mock_rel.id = 1
            mock_ps._get_or_create_relation = AsyncMock(return_value=mock_rel)
            mock_get_ps.return_value = mock_ps

            results = await service.process_documents(mock_db, [5])
            assert results[0].status == "success"

    @pytest.mark.asyncio
    async def test_process_nonexistent_document(self, service):
        mock_db = AsyncMock()
        # enabled version exists, no building lock → per-doc check fails
        mock_db.execute = _make_execute_side_effect(enabled_version=True, building_version=None)
        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

            results = await service.process_documents(mock_db, [999])
            assert results[0].status == "failed"
            assert "不存在" in results[0].reason

    @pytest.mark.asyncio
    async def test_process_no_enabled_version(self, service):
        mock_db = AsyncMock()
        # no enabled version → early return for ALL documents
        mock_db.execute = _make_execute_side_effect(enabled_version=False, building_version=None)

        with patch("knowlebase.resource.document.service.DocumentRepository") as mock_repo_cls:
            results = await service.process_documents(mock_db, [123])
            assert results[0].status == "failed"
            assert "暂无启用的知识库版本" in results[0].reason

    @pytest.mark.asyncio
    async def test_process_blocked_by_building(self, service):
        mock_db = AsyncMock()
        building_version = MagicMock()
        building_version.status = "building"
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=building_version)
        ))

        results = await service.process_documents(mock_db, [123])
        assert len(results) == 1
        assert results[0].status == "failed"
        assert "构建中" in results[0].reason

    @pytest.mark.asyncio
    async def test_process_active_processing_blocked(self, service):
        mock_db = AsyncMock()
        doc = make_mock_document()
        mock_db.flush = AsyncMock()
        mock_db.execute = _make_execute_side_effect(enabled_version=True, building_version=None)

        with (
            patch("knowlebase.resource.document.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.resource.document.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.build.processing.service.get_processing_service") as mock_get_ps,
        ):
            mock_doc, mock_hist = _patch_repos(mock_doc_cls, mock_hist_cls)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_hist.has_active_processing = AsyncMock(return_value=True)

            mock_ps = MagicMock()
            mock_rel = MagicMock()
            mock_rel.id = 1
            mock_ps._get_or_create_relation = AsyncMock(return_value=mock_rel)
            mock_get_ps.return_value = mock_ps

            results = await service.process_documents(mock_db, [123])
            assert results[0].status == "failed"
            assert "处理中" in results[0].reason

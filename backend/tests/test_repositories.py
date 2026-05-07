"""
单元测试 - Repository 持久化操作（mock AsyncSession）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from knowlebase.repositories import (
    DocumentRepository,
    ProcessingHistoryRepository,
    StageResultRepository,
)
from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.models.processing_stage_result import ProcessingStageResult


def mock_execute_return(return_value):
    """创建 mock execute result，支持 scalar_one_or_none / scalars / scalar_one"""
    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=return_value)
    result.scalar_one = MagicMock(return_value=return_value if return_value is not None else 0)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=return_value if isinstance(return_value, list) else [return_value] if return_value else [])))
    result.all = MagicMock(return_value=return_value if isinstance(return_value, list) else [])
    return result


class TestDocumentRepository:

    @pytest.fixture
    def db(self):
        return AsyncMock()

    def repo(self, db):
        return DocumentRepository(db)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_document(self, db):
        doc = Document(original_filename="test.pdf", file_hash="a" * 32)
        db.execute = AsyncMock(return_value=mock_execute_return(doc))

        result = await self.repo(db).get_by_id(1)
        assert result is doc
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(None))

        result = await self.repo(db).get_by_id(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_hash_returns_document(self, db):
        doc = Document(original_filename="test.pdf", file_hash="b" * 32)
        db.execute = AsyncMock(return_value=mock_execute_return(doc))

        result = await self.repo(db).get_by_hash("b" * 32)
        assert result is doc

    @pytest.mark.asyncio
    async def test_find_duplicates_empty_list(self, db):
        result = await self.repo(db).find_duplicates([])
        assert result == []
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_find_duplicates_returns_matches(self, db):
        doc = Document(original_filename="found.pdf", file_hash="c" * 32)
        db.execute = AsyncMock(return_value=mock_execute_return([doc]))

        result = await self.repo(db).find_duplicates(["c" * 32])
        assert result == [doc]

    @pytest.mark.asyncio
    async def test_list_with_filters_empty(self, db):
        count_result = mock_execute_return(0)
        list_result = mock_execute_return([])
        db.execute = AsyncMock(side_effect=[count_result, list_result])

        docs, total = await self.repo(db).list_with_filters(page=1, page_size=20)
        assert docs == []
        assert total == 0
        assert db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_list_with_filters_status_filter(self, db):
        doc = Document(original_filename="a.pdf", file_hash="d" * 32)
        count_result = mock_execute_return(1)
        list_result = mock_execute_return([doc])
        db.execute = AsyncMock(side_effect=[count_result, list_result])

        docs, total = await self.repo(db).list_with_filters(status="enabled")
        assert total == 1
        assert docs == [doc]

    @pytest.mark.asyncio
    async def test_add_flushes(self, db):
        doc = Document(original_filename="new.pdf", file_hash="e" * 32)
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await self.repo(db).add(doc)
        db.add.assert_called_once_with(doc)
        db.flush.assert_awaited_once()
        assert result is doc


class TestProcessingHistoryRepository:

    @pytest.fixture
    def db(self):
        return AsyncMock()

    def repo(self, db):
        return ProcessingHistoryRepository(db)

    @pytest.mark.asyncio
    async def test_get_by_processing_id_found(self, db):
        proc = DocumentProcessingHistory(document_id=1, processing_id="proc_abc", attempt_no=1)
        db.execute = AsyncMock(return_value=mock_execute_return(proc))

        result = await self.repo(db).get_by_processing_id("proc_abc")
        assert result is proc

    @pytest.mark.asyncio
    async def test_get_by_processing_id_none(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(None))

        result = await self.repo(db).get_by_processing_id("proc_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_by_document_id(self, db):
        proc = DocumentProcessingHistory(document_id=1, processing_id="proc_latest", attempt_no=3)
        db.execute = AsyncMock(return_value=mock_execute_return(proc))

        result = await self.repo(db).get_latest_by_document_id(1)
        assert result is proc

    @pytest.mark.asyncio
    async def test_get_latest_returns_none(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(None))

        result = await self.repo(db).get_latest_by_document_id(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_has_active_processing_true(self, db):
        proc = DocumentProcessingHistory(document_id=1, processing_id="proc_active", attempt_no=1)
        db.execute = AsyncMock(return_value=mock_execute_return(proc))

        result = await self.repo(db).has_active_processing(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_active_processing_false(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(None))

        result = await self.repo(db).has_active_processing(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_max_attempt_no(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(5))

        result = await self.repo(db).get_max_attempt_no(1)
        assert result == 5

    @pytest.mark.asyncio
    async def test_get_max_attempt_no_zero(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(0))

        result = await self.repo(db).get_max_attempt_no(1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_add(self, db):
        proc = DocumentProcessingHistory(document_id=1, processing_id="proc_add", attempt_no=1)
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await self.repo(db).add(proc)
        db.add.assert_called_once_with(proc)
        db.flush.assert_awaited_once()
        assert result is proc


class TestStageResultRepository:

    @pytest.fixture
    def db(self):
        return AsyncMock()

    def repo(self, db):
        return StageResultRepository(db)

    @pytest.mark.asyncio
    async def test_upsert_insert_new(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return(None))
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await self.repo(db).upsert("proc_1", "parsed", "succeeded", 150)
        assert result.processing_id == "proc_1"
        assert result.stage_name == "parsed"
        assert result.status == "succeeded"
        assert result.duration_ms == 150
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upsert_update_existing(self, db):
        existing = ProcessingStageResult(
            processing_id="proc_1", stage_name="parsed",
            status="running", duration_ms=0
        )
        db.execute = AsyncMock(return_value=mock_execute_return(existing))
        db.flush = AsyncMock()

        result = await self.repo(db).upsert("proc_1", "parsed", "succeeded", 200, error_message="oops")
        assert result.status == "succeeded"
        assert result.duration_ms == 200
        assert result.error_message == "oops"
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_processing_id(self, db):
        s1 = ProcessingStageResult(processing_id="proc_1", stage_name="check", status="succeeded", duration_ms=10)
        s2 = ProcessingStageResult(processing_id="proc_1", stage_name="parsed", status="succeeded", duration_ms=150)
        db.execute = AsyncMock(return_value=mock_execute_return([s1, s2]))

        results = await self.repo(db).list_by_processing_id("proc_1")
        assert len(results) == 2
        assert results[0].stage_name == "check"

    @pytest.mark.asyncio
    async def test_list_by_processing_id_empty(self, db):
        db.execute = AsyncMock(return_value=mock_execute_return([]))

        results = await self.repo(db).list_by_processing_id("proc_none")
        assert results == []

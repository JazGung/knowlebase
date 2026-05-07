"""
单元测试 - ProcessingService 流水线编排 和 Processing API 路由
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowlebase.admin.processing.service import ProcessingService


def _make_mock_repos(mock_doc_cls, mock_hist_cls, mock_stage_cls):
    """辅助: 创建 mock repository 实例"""
    mock_doc = MagicMock()
    mock_hist = MagicMock()
    mock_stage = MagicMock()
    mock_doc_cls.return_value = mock_doc
    mock_hist_cls.return_value = mock_hist
    mock_stage_cls.return_value = mock_stage
    return mock_doc, mock_hist, mock_stage


class TestRunStage:

    @pytest.fixture
    def service(self):
        return ProcessingService()

    @pytest.mark.asyncio
    async def test_stage_success(self, service):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        with (
            patch("knowlebase.admin.processing.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.admin.processing.service.StageResultRepository") as mock_stage_cls,
            patch("knowlebase.admin.processing.service.get_event_bus") as mock_eb,
        ):
            mock_doc, mock_hist, mock_stage = _make_mock_repos(mock_doc_cls, mock_hist_cls, mock_stage_cls)
            mock_proc = MagicMock()
            mock_hist.get_by_processing_id = AsyncMock(return_value=mock_proc)
            mock_stage.upsert = AsyncMock()
            mock_bus = MagicMock()
            mock_bus.publish = AsyncMock()
            mock_eb.return_value = mock_bus

            result = await service._run_stage(
                db=mock_db, doc_repo=mock_doc, hist_repo=mock_hist, stage_repo=mock_stage,
                stage_name="parsed", progress=30,
                document_id=1, processing_id="proc_1",
                attempt_no=1, event_bus=mock_bus,
                execute=lambda: "stage_output",
                write_result=True, result_stage_name="parsed",
            )

            assert result == "stage_output"
            # 开始 running → 结束 succeeded 两次 upsert
            assert mock_stage.upsert.await_count == 2
            # 第一阶段调用: upsert(processing_id, stage_name, "running", 0)
            first_call = mock_stage.upsert.await_args_list[0]
            assert first_call[0][1] == "parsed"
            assert first_call[0][2] == "running"
            # 第二阶段调用: upsert(processing_id, stage_name, "succeeded", duration, result_path)
            second_call = mock_stage.upsert.await_args_list[1]
            assert second_call[0][2] == "succeeded"
            mock_bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stage_failure(self, service):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        with (
            patch("knowlebase.admin.processing.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.admin.processing.service.StageResultRepository") as mock_stage_cls,
        ):
            mock_doc, mock_hist, mock_stage = _make_mock_repos(mock_doc_cls, mock_hist_cls, mock_stage_cls)
            mock_hist.get_by_processing_id = AsyncMock(return_value=MagicMock())
            mock_stage.upsert = AsyncMock()
            mock_bus = MagicMock()
            mock_bus.publish = AsyncMock()

            result = await service._run_stage(
                db=mock_db, doc_repo=mock_doc, hist_repo=mock_hist, stage_repo=mock_stage,
                stage_name="parsed", progress=30,
                document_id=1, processing_id="proc_1",
                attempt_no=1, event_bus=mock_bus,
                execute=lambda: (_ for _ in ()).throw(ValueError("测试异常")),
            )

            assert result is None
            # failed 状态写入
            failed_call = mock_stage.upsert.await_args_list[-1]
            assert failed_call[0][2] == "failed"
            assert failed_call[1]["error_message"] == "测试异常"
            mock_bus.publish.assert_awaited_once()


class TestGetProcessingStatus:

    @pytest.fixture
    def service(self):
        return ProcessingService()

    @pytest.mark.asyncio
    async def test_not_found(self, service):
        mock_db = AsyncMock()
        with patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls:
            mock_hist_cls.return_value.get_by_processing_id = AsyncMock(return_value=None)

            result = await service.get_processing_status(mock_db, "proc_none")
            assert result is None

    @pytest.mark.asyncio
    async def test_found_with_stages(self, service):
        mock_db = AsyncMock()
        proc = MagicMock()
        proc.processing_id = "proc_1"
        proc.document_id = 1
        proc.attempt_no = 1
        proc.status = "succeeded"
        proc.current_stage = "stored"
        proc.progress = 100
        proc.started_at = None
        proc.completed_at = None
        proc.error_message = None

        stage = MagicMock()
        stage.stage_name = "check"
        stage.status = "succeeded"
        stage.duration_ms = 10
        stage.error_message = None

        with (
            patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.admin.processing.service.StageResultRepository") as mock_stage_cls,
        ):
            mock_hist_cls.return_value.get_by_processing_id = AsyncMock(return_value=proc)
            mock_stage_cls.return_value.list_by_processing_id = AsyncMock(return_value=[stage])

            result = await service.get_processing_status(mock_db, "proc_1")
            assert result is not None
            assert result["processing_id"] == "proc_1"
            assert result["status"] == "succeeded"
            assert len(result["stages"]) == 1
            assert result["stages"][0]["stage_name"] == "check"


class TestGetProcessingView:

    @pytest.fixture
    def service(self):
        return ProcessingService()

    @pytest.mark.asyncio
    async def test_view_with_pending_document(self, service):
        mock_db = AsyncMock()
        doc = MagicMock()
        doc.id = 1
        doc.original_filename = "pending.pdf"

        with (
            patch("knowlebase.admin.processing.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.admin.processing.service.StageResultRepository") as mock_stage_cls,
        ):
            mock_doc, mock_hist, mock_stage = _make_mock_repos(mock_doc_cls, mock_hist_cls, mock_stage_cls)
            mock_hist.get_latest_by_document_id = AsyncMock(return_value=None)
            mock_doc.get_by_id = AsyncMock(return_value=doc)

            result = await service.get_processing_view(mock_db, [1])
            assert len(result["tabs"]) == 1
            tab = result["tabs"][0]
            assert tab["status"] == "pending"
            assert tab["progress"] == 0

    @pytest.mark.asyncio
    async def test_view_with_processing_document(self, service):
        mock_db = AsyncMock()
        doc = MagicMock()
        doc.id = 1
        doc.original_filename = "processing.pdf"

        proc = MagicMock()
        proc.processing_id = "proc_1"
        proc.attempt_no = 1
        proc.status = "processing"
        proc.progress = 50
        proc.error_message = None

        stage = MagicMock()
        stage.stage_name = "parsed"
        stage.status = "succeeded"

        with (
            patch("knowlebase.admin.processing.service.DocumentRepository") as mock_doc_cls,
            patch("knowlebase.admin.processing.service.ProcessingHistoryRepository") as mock_hist_cls,
            patch("knowlebase.admin.processing.service.StageResultRepository") as mock_stage_cls,
        ):
            mock_doc, mock_hist, mock_stage = _make_mock_repos(mock_doc_cls, mock_hist_cls, mock_stage_cls)
            mock_hist.get_latest_by_document_id = AsyncMock(return_value=proc)
            mock_doc.get_by_id = AsyncMock(return_value=doc)
            mock_stage.list_by_processing_id = AsyncMock(return_value=[stage])

            result = await service.get_processing_view(mock_db, [1])
            tab = result["tabs"][0]
            assert tab["status"] == "processing"
            assert tab["progress"] == 50
            # stages 列表按 STAGE_ORDER 顺序展开
            assert len(tab["stages"]) == 6  # check, parsed, cleaned, images_described, chunked, stored

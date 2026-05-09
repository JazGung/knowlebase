"""
单元测试 - ProcessingService 流水线编排 和 Processing API 路由
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowlebase.admin.processing.service import ProcessingService
from knowlebase.events import DocumentProcessingEvent


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
            mock_doc_event = DocumentProcessingEvent(mock_bus)

            result = await service._run_stage(
                db=mock_db, doc_repo=mock_doc, hist_repo=mock_hist, stage_repo=mock_stage,
                stage_name="parsed", progress=30,
                document_id=1, processing_id="proc_1",
                attempt_no=1, event_bus=mock_bus, doc_event=mock_doc_event,
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
            mock_doc_event = DocumentProcessingEvent(mock_bus)

            result = await service._run_stage(
                db=mock_db, doc_repo=mock_doc, hist_repo=mock_hist, stage_repo=mock_stage,
                stage_name="parsed", progress=30,
                document_id=1, processing_id="proc_1",
                attempt_no=1, event_bus=mock_bus, doc_event=mock_doc_event,
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


class TestParsePageRange:

    def test_none_returns_zero_zero(self):
        from knowlebase.admin.processing.service import ProcessingService
        assert ProcessingService._parse_page_range(None) == (0, 0)

    def test_empty_returns_zero_zero(self):
        from knowlebase.admin.processing.service import ProcessingService
        assert ProcessingService._parse_page_range("") == (0, 0)

    def test_single_page(self):
        from knowlebase.admin.processing.service import ProcessingService
        assert ProcessingService._parse_page_range("5") == (5, 5)

    def test_page_range(self):
        from knowlebase.admin.processing.service import ProcessingService
        assert ProcessingService._parse_page_range("1-3") == (1, 3)

    def test_page_range_with_spaces(self):
        from knowlebase.admin.processing.service import ProcessingService
        assert ProcessingService._parse_page_range(" 10 - 20 ") == (10, 20)


class TestStoreResults:
    """数据入库 (_store_results) 测试 — 使用 mock 验证 6 步流程"""

    @pytest.fixture
    def service(self):
        from knowlebase.admin.processing.service import ProcessingService
        return ProcessingService()

    def _make_chunk(self, index=0):
        """创建模拟 ChunkResult"""
        from knowlebase.chunker.models import ChunkResult, Relation
        return ChunkResult(
            original_text=f"original_{index}",
            processed_text=f"processed_{index}",
            hypothetical_questions=[f"q{index}_a", f"q{index}_b"],
            relations=[Relation(source="E1", relationship="位于", target="E2")],
            page_range="1-2",
            section_title=f"Section {index}",
        )

    @pytest.mark.asyncio
    async def test_store_results_success(self, service):
        """正常流程：6 步全部成功"""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        doc = MagicMock()
        doc.id = 1
        doc.original_filename = "test.pdf"
        proc = MagicMock()
        proc.mark_succeeded = MagicMock()

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id = AsyncMock(return_value=doc)
        mock_hist_repo = MagicMock()
        mock_hist_repo.get_by_processing_id = AsyncMock(return_value=proc)
        mock_stage_repo = MagicMock()

        chunks = [self._make_chunk(i) for i in range(2)]

        with (
            patch("knowlebase.admin.processing.service.get_embedding_service") as mock_emb,
            patch("knowlebase.admin.processing.service.get_es_service") as mock_es,
            patch("knowlebase.admin.processing.service.get_milvus_service") as mock_milvus,
            patch("knowlebase.admin.processing.service.get_neo4j_service") as mock_neo4j,
            patch("knowlebase.admin.processing.service.DocumentChunkRepository") as mock_chunk_repo_cls,
        ):
            mock_emb_svc = MagicMock()
            mock_emb_svc.count_tokens = MagicMock(return_value=100)
            mock_emb_svc.encode = MagicMock(return_value=[[0.1] * 512, [0.2] * 512])
            mock_emb.return_value = mock_emb_svc

            mock_es_svc = MagicMock()
            mock_es_svc.delete_by_document_id = AsyncMock()
            mock_es_svc.index_chunks = AsyncMock()
            mock_es.return_value = mock_es_svc

            mock_milvus_svc = MagicMock()
            mock_milvus_svc.delete_by_document_id = MagicMock()
            mock_milvus_svc.insert_vectors = MagicMock()
            mock_milvus.return_value = mock_milvus_svc

            mock_neo4j_svc = MagicMock()
            mock_neo4j_svc.delete_by_document_id = AsyncMock()
            mock_neo4j_svc.write_graph = AsyncMock()
            mock_neo4j.return_value = mock_neo4j_svc

            mock_chunk_repo = MagicMock()
            mock_chunk_repo.delete_by_document_id = AsyncMock()
            mock_chunk_repo.bulk_insert = AsyncMock()
            mock_chunk_repo_cls.return_value = mock_chunk_repo

            result = await service._store_results(
                db=mock_db,
                doc_repo=mock_doc_repo,
                hist_repo=mock_hist_repo,
                stage_repo=mock_stage_repo,
                document_id=1,
                processing_id="proc_1",
                result=MagicMock(),
                chunks=chunks,
            )

            assert result["status"] == "success"
            assert result["chunks_count"] == 2
            assert doc.chunk_count == 2
            assert doc.total_token == 400  # 2 chunks × 200 tokens each (100+100)
            assert doc.embedding_model is not None
            proc.mark_succeeded.assert_called_once()
            mock_es_svc.index_chunks.assert_awaited_once()
            mock_milvus_svc.insert_vectors.assert_called_once()
            mock_neo4j_svc.write_graph.assert_awaited_once()
            assert mock_db.commit.await_count >= 1

    @pytest.mark.asyncio
    async def test_store_results_pg_failure_rollback(self, service):
        """PostgreSQL 事务写入失败时回滚并标记失败"""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock(side_effect=RuntimeError("PG 写入失败"))
        mock_db.rollback = AsyncMock()

        doc = MagicMock()
        proc = MagicMock()
        proc.mark_failed = MagicMock()

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id = AsyncMock(return_value=doc)
        mock_hist_repo = MagicMock()
        mock_hist_repo.get_by_processing_id = AsyncMock(return_value=proc)
        mock_stage_repo = MagicMock()

        chunks = [self._make_chunk(0)]

        with (
            patch("knowlebase.admin.processing.service.get_embedding_service") as mock_emb,
            patch("knowlebase.admin.processing.service.get_es_service") as mock_es,
            patch("knowlebase.admin.processing.service.get_milvus_service") as mock_milvus,
            patch("knowlebase.admin.processing.service.get_neo4j_service") as mock_neo4j,
            patch("knowlebase.admin.processing.service.DocumentChunkRepository") as mock_chunk_repo_cls,
        ):
            mock_emb_svc = MagicMock()
            mock_emb_svc.count_tokens = MagicMock(return_value=50)
            mock_emb.return_value = mock_emb_svc

            mock_es_svc = MagicMock()
            mock_es_svc.delete_by_document_id = AsyncMock()
            mock_es.return_value = mock_es_svc

            mock_milvus_svc = MagicMock()
            mock_milvus_svc.delete_by_document_id = MagicMock()
            mock_milvus.return_value = mock_milvus_svc

            mock_neo4j_svc = MagicMock()
            mock_neo4j_svc.delete_by_document_id = AsyncMock()
            mock_neo4j.return_value = mock_neo4j_svc

            mock_chunk_repo = MagicMock()
            mock_chunk_repo.delete_by_document_id = AsyncMock()
            mock_chunk_repo.bulk_insert = AsyncMock()
            mock_chunk_repo_cls.return_value = mock_chunk_repo

            result = await service._store_results(
                db=mock_db, doc_repo=mock_doc_repo, hist_repo=mock_hist_repo,
                stage_repo=mock_stage_repo,
                document_id=1, processing_id="proc_1",
                result=MagicMock(), chunks=chunks,
            )

            assert result["status"] == "failed"
            assert "PG 写入失败" in result["error"]
            mock_db.rollback.assert_awaited_once()
            proc.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_results_es_failure(self, service):
        """ES 写入失败时标记失败，不阻止返回"""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        doc = MagicMock()
        proc = MagicMock()
        proc.mark_succeeded = MagicMock()
        proc.mark_failed = MagicMock()

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id = AsyncMock(return_value=doc)
        mock_hist_repo = MagicMock()
        mock_hist_repo.get_by_processing_id = AsyncMock(return_value=proc)
        mock_stage_repo = MagicMock()

        chunks = [self._make_chunk(0)]

        with (
            patch("knowlebase.admin.processing.service.get_embedding_service") as mock_emb,
            patch("knowlebase.admin.processing.service.get_es_service") as mock_es,
            patch("knowlebase.admin.processing.service.get_milvus_service") as mock_milvus,
            patch("knowlebase.admin.processing.service.get_neo4j_service") as mock_neo4j,
            patch("knowlebase.admin.processing.service.DocumentChunkRepository") as mock_chunk_repo_cls,
        ):
            mock_emb_svc = MagicMock()
            mock_emb_svc.count_tokens = MagicMock(return_value=50)
            mock_emb.return_value = mock_emb_svc

            mock_es_svc = MagicMock()
            mock_es_svc.delete_by_document_id = AsyncMock()
            mock_es_svc.index_chunks = AsyncMock(side_effect=RuntimeError("ES 不可用"))
            mock_es.return_value = mock_es_svc

            mock_milvus_svc = MagicMock()
            mock_milvus_svc.delete_by_document_id = MagicMock()
            mock_milvus.return_value = mock_milvus_svc

            mock_neo4j_svc = MagicMock()
            mock_neo4j_svc.delete_by_document_id = AsyncMock()
            mock_neo4j.return_value = mock_neo4j_svc

            mock_chunk_repo = MagicMock()
            mock_chunk_repo.delete_by_document_id = AsyncMock()
            mock_chunk_repo.bulk_insert = AsyncMock()
            mock_chunk_repo_cls.return_value = mock_chunk_repo

            result = await service._store_results(
                db=mock_db, doc_repo=mock_doc_repo, hist_repo=mock_hist_repo,
                stage_repo=mock_stage_repo,
                document_id=1, processing_id="proc_1",
                result=MagicMock(), chunks=chunks,
            )

            assert result["status"] == "failed"
            assert "ES" in result["error"]
            proc.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_results_milvus_failure(self, service):
        """Milvus 写入失败时标记失败"""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        doc = MagicMock()
        proc = MagicMock()
        proc.mark_succeeded = MagicMock()
        proc.mark_failed = MagicMock()

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id = AsyncMock(return_value=doc)
        mock_hist_repo = MagicMock()
        mock_hist_repo.get_by_processing_id = AsyncMock(return_value=proc)
        mock_stage_repo = MagicMock()

        chunks = [self._make_chunk(0)]

        with (
            patch("knowlebase.admin.processing.service.get_embedding_service") as mock_emb,
            patch("knowlebase.admin.processing.service.get_es_service") as mock_es,
            patch("knowlebase.admin.processing.service.get_milvus_service") as mock_milvus,
            patch("knowlebase.admin.processing.service.get_neo4j_service") as mock_neo4j,
            patch("knowlebase.admin.processing.service.DocumentChunkRepository") as mock_chunk_repo_cls,
        ):
            mock_emb_svc = MagicMock()
            mock_emb_svc.count_tokens = MagicMock(return_value=50)
            mock_emb_svc.encode = MagicMock(return_value=[[0.1] * 512])
            mock_emb.return_value = mock_emb_svc

            mock_es_svc = MagicMock()
            mock_es_svc.delete_by_document_id = AsyncMock()
            mock_es_svc.index_chunks = AsyncMock()  # ES succeeds
            mock_es.return_value = mock_es_svc

            mock_milvus_svc = MagicMock()
            mock_milvus_svc.delete_by_document_id = MagicMock()
            mock_milvus_svc.insert_vectors = MagicMock(side_effect=RuntimeError("Milvus 不可用"))
            mock_milvus.return_value = mock_milvus_svc

            mock_neo4j_svc = MagicMock()
            mock_neo4j_svc.delete_by_document_id = AsyncMock()
            mock_neo4j.return_value = mock_neo4j_svc

            mock_chunk_repo = MagicMock()
            mock_chunk_repo.delete_by_document_id = AsyncMock()
            mock_chunk_repo.bulk_insert = AsyncMock()
            mock_chunk_repo_cls.return_value = mock_chunk_repo

            result = await service._store_results(
                db=mock_db, doc_repo=mock_doc_repo, hist_repo=mock_hist_repo,
                stage_repo=mock_stage_repo,
                document_id=1, processing_id="proc_1",
                result=MagicMock(), chunks=chunks,
            )

            assert result["status"] == "failed"
            assert "Milvus" in result["error"]
            proc.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_results_neo4j_failure(self, service):
        """Neo4j 写入失败时标记失败"""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        doc = MagicMock()
        proc = MagicMock()
        proc.mark_succeeded = MagicMock()
        proc.mark_failed = MagicMock()

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id = AsyncMock(return_value=doc)
        mock_hist_repo = MagicMock()
        mock_hist_repo.get_by_processing_id = AsyncMock(return_value=proc)
        mock_stage_repo = MagicMock()

        chunks = [self._make_chunk(0)]

        with (
            patch("knowlebase.admin.processing.service.get_embedding_service") as mock_emb,
            patch("knowlebase.admin.processing.service.get_es_service") as mock_es,
            patch("knowlebase.admin.processing.service.get_milvus_service") as mock_milvus,
            patch("knowlebase.admin.processing.service.get_neo4j_service") as mock_neo4j,
            patch("knowlebase.admin.processing.service.DocumentChunkRepository") as mock_chunk_repo_cls,
        ):
            mock_emb_svc = MagicMock()
            mock_emb_svc.count_tokens = MagicMock(return_value=50)
            mock_emb_svc.encode = MagicMock(return_value=[[0.1] * 512])
            mock_emb.return_value = mock_emb_svc

            mock_es_svc = MagicMock()
            mock_es_svc.delete_by_document_id = AsyncMock()
            mock_es_svc.index_chunks = AsyncMock()
            mock_es.return_value = mock_es_svc

            mock_milvus_svc = MagicMock()
            mock_milvus_svc.delete_by_document_id = MagicMock()
            mock_milvus_svc.insert_vectors = MagicMock()
            mock_milvus.return_value = mock_milvus_svc

            mock_neo4j_svc = MagicMock()
            mock_neo4j_svc.delete_by_document_id = AsyncMock()
            mock_neo4j_svc.write_graph = AsyncMock(side_effect=RuntimeError("Neo4j 不可用"))
            mock_neo4j.return_value = mock_neo4j_svc

            mock_chunk_repo = MagicMock()
            mock_chunk_repo.delete_by_document_id = AsyncMock()
            mock_chunk_repo.bulk_insert = AsyncMock()
            mock_chunk_repo_cls.return_value = mock_chunk_repo

            result = await service._store_results(
                db=mock_db, doc_repo=mock_doc_repo, hist_repo=mock_hist_repo,
                stage_repo=mock_stage_repo,
                document_id=1, processing_id="proc_1",
                result=MagicMock(), chunks=chunks,
            )

            assert result["status"] == "failed"
            assert "Neo4j" in result["error"]
            proc.mark_failed.assert_called_once()

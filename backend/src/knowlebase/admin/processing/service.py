"""
文档处理服务

处理流水线：检查 → 解析 → 清洗 → 图片描述 → 分块 → 数据入库
每阶段完成后写入 processing_stage_result 并发布事件。
服务层委托 Repository 进行数据访问，委托领域对象处理业务逻辑。
"""

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.models.processing_stage_result import ProcessingStageResult
from knowlebase.repositories import (
    DocumentRepository,
    ProcessingHistoryRepository,
    StageResultRepository,
)
from knowlebase.parsers import parse_document
from knowlebase.parsers.base import ParseResult
from knowlebase.cleaners import clean_document
from knowlebase.chunker import chunk_document
from knowlebase.chunker.image_describer import replace_images_with_markers
from knowlebase.services.minio_service import get_minio_service, MinioService
from knowlebase.events import get_event_bus, StageCompletedEvent

logger = logging.getLogger(__name__)

STAGE_ORDER = ["check", "parsed", "cleaned", "images_described", "chunked", "stored"]


class ProcessingService:
    """文档处理服务 — 编排流水线，委托 Repository + 领域对象"""

    # ---- 流水线入口 ----

    async def process_document(
        self,
        db: AsyncSession,
        document_id: int,
        processing_id: str,
        attempt_no: int = 1,
    ) -> Dict:
        """执行完整处理流水线"""
        event_bus = get_event_bus()
        doc_repo = DocumentRepository(db)
        hist_repo = ProcessingHistoryRepository(db)
        stage_repo = StageResultRepository(db)

        # ---- 4.10.5 文档检查 ----
        doc = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="check", progress=10,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: self._check_document(db, doc_repo, hist_repo,
                                                  document_id, processing_id,
                                                  attempt_no, stage_repo),
        )
        if doc is None:
            return {"status": "failed", "error": "文档检查失败"}
        file_hash = doc.file_hash

        # ---- 4.10.6 文档解析 ----
        result = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="parsed", progress=30,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: self._parse_document(db, hist_repo, stage_repo,
                                                  doc, file_hash, processing_id),
            write_result=True, result_stage_name="parsed",
        )
        if result is None:
            return {"status": "failed", "error": "文档解析失败"}

        # ---- 4.10.7 文档清洗 ----
        result = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="cleaned", progress=50,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: self._clean_document(result, file_hash, processing_id),
            write_result=True, result_stage_name="cleaned",
        )
        if result is None:
            return {"status": "failed", "error": "文档清洗失败"}

        # ---- 4.10.8 图片描述 ----
        result = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="images_described", progress=60,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: replace_images_with_markers(result),
        )
        if result is None:
            return {"status": "failed", "error": "图片描述失败"}

        # ---- 4.10.9 文档分块 ----
        chunks = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="chunked", progress=80,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: self._chunk_document(result, doc, processing_id, file_hash),
            write_result=True, result_stage_name="chunked",
        )
        if chunks is None:
            return {"status": "failed", "error": "文档分块失败"}

        # ---- 4.10.10 数据入库 ----
        final = await self._run_stage(
            db=db, doc_repo=doc_repo, hist_repo=hist_repo, stage_repo=stage_repo,
            stage_name="stored", progress=90,
            document_id=document_id, processing_id=processing_id,
            attempt_no=attempt_no, event_bus=event_bus,
            execute=lambda: self._store_results(db, doc_repo, hist_repo, stage_repo,
                                                 document_id, processing_id, result, chunks),
        )
        if final is None:
            return {"status": "failed", "error": "数据入库失败"}

        return final

    # ---- 阶段执行器 ----

    async def _run_stage(
        self,
        db: AsyncSession,
        doc_repo: DocumentRepository,
        hist_repo: ProcessingHistoryRepository,
        stage_repo: StageResultRepository,
        stage_name: str,
        progress: int,
        document_id: int,
        processing_id: str,
        attempt_no: int,
        event_bus,
        execute: Callable,
        write_result: bool = False,
        result_stage_name: str | None = None,
    ) -> Any:
        """统一的阶段执行器：开始标记 → 执行 → 成功标记/失败处理"""
        stage_start = time.monotonic()

        try:
            # 阶段开始：更新进度
            proc = await hist_repo.get_by_processing_id(processing_id)
            if proc:
                proc.update_progress(stage_name, progress)
            await stage_repo.upsert(processing_id, stage_name, "running", 0)
            await db.commit()

            # 执行阶段逻辑
            result = execute()

            # 阶段成功
            duration = int((time.monotonic() - stage_start) * 1000)
            result_path = None
            if write_result and result is not None and result_stage_name:
                result_path = self._write_intermediate_result(
                    result, processing_id, result_stage_name
                )

            await stage_repo.upsert(processing_id, stage_name, "succeeded", duration, result_path)
            await db.commit()

            await event_bus.publish(StageCompletedEvent(
                processing_id=processing_id, stage_name=stage_name,
                status="succeeded", duration_ms=duration,
            ))

            return result

        except Exception as e:
            logger.error(f"阶段 [{stage_name}] 失败: {e}", exc_info=True)
            duration = int((time.monotonic() - stage_start) * 1000)

            await stage_repo.upsert(
                processing_id, stage_name, "failed", duration,
                error_message=str(e)
            )
            await self._ensure_history_and_fail(
                hist_repo, processing_id, document_id, attempt_no, str(e)
            )
            await db.commit()

            await event_bus.publish(StageCompletedEvent(
                processing_id=processing_id, stage_name=stage_name,
                status="failed", duration_ms=duration, error_message=str(e),
            ))

            return None

    # ---- 各阶段具体实现 ----

    async def _check_document(
        self, db: AsyncSession,
        doc_repo: DocumentRepository,
        hist_repo: ProcessingHistoryRepository,
        document_id: int, processing_id: str,
        attempt_no: int,
        stage_repo: StageResultRepository,
    ) -> Document | None:
        """4.10.5 文档检查：验证文档和文件存在性，创建处理历史"""
        doc = await doc_repo.get_by_id(document_id)
        if not doc:
            raise ValueError("文档不存在")

        minio_svc = get_minio_service()
        if not minio_svc.file_exists(settings.minio_document_bucket, doc.file_hash):
            raise ValueError("文档文件不存在")

        # 创建处理历史
        proc = await hist_repo.get_by_processing_id(processing_id)
        if proc is None:
            proc = DocumentProcessingHistory(
                document_id=document_id,
                processing_id=processing_id,
                attempt_no=attempt_no,
            )
            await hist_repo.add(proc)
        proc.update_progress("check", 10)
        proc.started_at = datetime.now()
        doc.add_processing_history(proc)
        return doc

    async def _parse_document(
        self, db: AsyncSession,
        hist_repo: ProcessingHistoryRepository,
        stage_repo: StageResultRepository,
        doc: Document, file_hash: str, processing_id: str,
    ) -> ParseResult:
        """4.10.6 文档解析"""
        minio_svc = get_minio_service()
        content = minio_svc.download_file(settings.minio_document_bucket, file_hash)
        result = await parse_document(
            content, filename=doc.original_filename,
            mime_type=doc.mime_type or "application/octet-stream"
        )
        logger.info(f"解析完成: {doc.original_filename}, sections={len(result.sections)}")
        return result

    async def _clean_document(
        self, result: ParseResult, file_hash: str, processing_id: str
    ) -> ParseResult:
        """4.10.7 文档清洗"""
        result = clean_document(result)
        logger.info(f"清洗完成: sections={len(result.sections)}")
        return result

    async def _chunk_document(
        self, result: ParseResult, doc: Document, processing_id: str, file_hash: str
    ) -> list:
        """4.10.9 文档分块"""
        chunks = chunk_document(result.sections, metadata={"filename": doc.original_filename})
        logger.info(f"分块完成: chunks={len(chunks)}")
        return chunks

    async def _store_results(
        self, db: AsyncSession,
        doc_repo: DocumentRepository,
        hist_repo: ProcessingHistoryRepository,
        stage_repo: StageResultRepository,
        document_id: int, processing_id: str,
        result: ParseResult, chunks: list,
    ) -> Dict:
        """4.10.10 数据入库"""
        doc = await doc_repo.get_by_id(document_id)
        doc.processed_at = datetime.now()
        doc.processing_id = processing_id
        doc.chunk_count = len(chunks)

        proc = await hist_repo.get_by_processing_id(processing_id)
        proc.mark_succeeded()

        logger.info(f"文档处理完成: {doc.original_filename}")
        return {
            "document_id": str(document_id),
            "processing_id": processing_id,
            "status": "success",
            "chunks_count": len(chunks),
        }

    # ---- 中间结果写入 ----

    def _write_intermediate_result(self, data: Any, processing_id: str, stage_name: str) -> str:
        """将中间结果序列化后写入 MinIO，返回路径"""
        minio_svc = get_minio_service()
        if isinstance(data, ParseResult):
            json_str = json.dumps(self._parse_result_to_dict(data), ensure_ascii=False)
        elif isinstance(data, list):
            json_str = json.dumps([self._chunk_result_to_dict(c) for c in data], ensure_ascii=False)
        else:
            json_str = json.dumps(data, ensure_ascii=False)

        result_path = f"processing-results/{processing_id}/{stage_name}.json"
        minio_svc.upload_file(
            settings.minio_document_bucket, result_path,
            json_str.encode("utf-8"), content_type="application/json"
        )
        return result_path

    # ---- 查询方法 ----

    async def get_processing_status(
        self, db: AsyncSession, processing_id: str
    ) -> Optional[Dict]:
        """处理状态查询，包含各阶段元信息（DEG 4.14）"""
        hist_repo = ProcessingHistoryRepository(db)
        proc = await hist_repo.get_by_processing_id(processing_id)
        if not proc:
            return None

        stage_repo = StageResultRepository(db)
        stage_records = await stage_repo.list_by_processing_id(processing_id)

        return {
            "processing_id": proc.processing_id,
            "document_id": str(proc.document_id),
            "attempt_no": proc.attempt_no,
            "status": proc.status,
            "current_stage": proc.current_stage,
            "progress": proc.progress,
            "started_at": proc.started_at.isoformat() if proc.started_at else None,
            "completed_at": proc.completed_at.isoformat() if proc.completed_at else None,
            "error_message": proc.error_message,
            "stages": [{
                "stage_name": s.stage_name,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "error_message": s.error_message,
            } for s in stage_records],
        }

    async def get_stage_result(
        self, db: AsyncSession, processing_id: str, stage_name: str
    ) -> Optional[Dict]:
        """阶段结果详情，从 MinIO 读取 JSON（DEG 4.15）"""
        stage_repo = StageResultRepository(db)
        record = await stage_repo.get_by_processing_and_stage(processing_id, stage_name)
        if not record:
            return None

        if record.status != "succeeded":
            return {
                "stage_name": record.stage_name,
                "status": record.status,
                "duration_ms": record.duration_ms,
                "error_message": record.error_message,
                "result": None,
            }

        result_data = None
        if record.result_path:
            try:
                content = MinioService().download_file(
                    settings.minio_document_bucket, record.result_path
                )
                result_data = json.loads(content.decode("utf-8"))
            except Exception as e:
                logger.error(f"从 MinIO 读取阶段结果失败: {e}")

        return {
            "stage_name": record.stage_name,
            "status": record.status,
            "duration_ms": record.duration_ms,
            "result": result_data,
        }

    async def get_processing_view(
        self, db: AsyncSession, document_ids: List[int]
    ) -> Dict:
        """多文档处理过程视图（DEG 4.16）"""
        doc_repo = DocumentRepository(db)
        hist_repo = ProcessingHistoryRepository(db)
        stage_repo = StageResultRepository(db)
        tabs = []

        for doc_id in document_ids:
            proc = await hist_repo.get_latest_by_document_id(doc_id)
            if not proc:
                doc = await doc_repo.get_by_id(doc_id)
                if doc:
                    tabs.append({
                        "document_id": doc_id,
                        "document_name": doc.original_filename,
                        "processing_id": None,
                        "attempt_no": 0,
                        "status": "pending",
                        "progress": 0,
                        "stages": [],
                        "error_message": None,
                    })
                continue

            stage_records = await stage_repo.list_by_processing_id(proc.processing_id)
            completed_stages = {s.stage_name: s.status for s in stage_records}

            doc = await doc_repo.get_by_id(doc_id)
            stages = []
            for name in STAGE_ORDER:
                status = completed_stages.get(name, "pending")
                stages.append({"name": name, "status": status})

            tabs.append({
                "document_id": doc_id,
                "document_name": doc.original_filename if doc else str(doc_id),
                "processing_id": proc.processing_id,
                "attempt_no": proc.attempt_no,
                "status": proc.status,
                "progress": proc.progress,
                "stages": stages,
                "error_message": proc.error_message,
            })

        return {"tabs": tabs}

    # ---- 内部辅助 ----

    async def _ensure_history_and_fail(
        self,
        hist_repo: ProcessingHistoryRepository,
        processing_id: str, document_id: int,
        attempt_no: int, error_message: str,
    ) -> None:
        """确保处理历史存在并标记失败"""
        try:
            proc = await hist_repo.get_by_processing_id(processing_id)
            if proc is None:
                proc = DocumentProcessingHistory(
                    document_id=document_id,
                    processing_id=processing_id,
                    attempt_no=attempt_no,
                )
                await hist_repo.add(proc)
            proc.mark_failed(error_message)
        except Exception as e:
            logger.error(f"更新处理失败状态时出错: {e}")

    def _parse_result_to_dict(self, result: ParseResult) -> Dict:
        sections = []
        for section in result.sections:
            sections.append(asdict(section))
        return {
            "page_count": result.page_count,
            "has_images": result.has_images,
            "has_tables": result.has_tables,
            "sections": sections,
        }

    def _chunk_result_to_dict(self, chunk) -> Dict:
        return {
            "original_text": chunk.original_text,
            "processed_text": getattr(chunk, "processed_text", ""),
            "hypothetical_questions": getattr(chunk, "hypothetical_questions", []),
            "relations": getattr(chunk, "relations", []),
            "page_range": list(getattr(chunk, "page_range", (0, 0))),
            "section_title": getattr(chunk, "section_title", ""),
        }


def get_processing_service() -> ProcessingService:
    return ProcessingService()

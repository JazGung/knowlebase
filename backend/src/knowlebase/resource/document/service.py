"""
文档管理服务

包含文档上传、管理、查询等业务逻辑。
服务层作为薄编排层，委托 Repository 进行数据访问，委托领域对象处理业务逻辑。
"""

import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.models.document_version_relation import DocumentVersionRelation
from knowlebase.repositories import (
    DocumentRepository,
    DocumentChunkRepository,
    ProcessingHistoryRepository,
)
from knowlebase.schemas.document import (
    DocumentListQuery,
    IntegrityValidationError,
    BatchResult,
)

logger = logging.getLogger(__name__)


async def _check_building_lock(db: AsyncSession) -> None:
    """检查是否存在构建中的知识库版本，存在则禁止操作"""
    from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
    result = await db.execute(
        select(KnowledgeBaseVersion).where(KnowledgeBaseVersion.status == "building").limit(1)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": "知识库版本正在构建中，暂不支持此操作",
                    "detail": {"code_name": "BUILDING_IN_PROGRESS"}},
        )


class UploadService:
    """文档上传服务 — 编排文件验证、MinIO 存储、数据库记录创建"""

    def __init__(self, minio_service):
        self.minio_service = minio_service

    # ---- 验证方法（无 DB 依赖，可独立测试） ----

    async def verify_file_integrity(
        self, content: bytes, provided_hash: str
    ) -> Tuple[bool, Optional[str], Optional[IntegrityValidationError]]:
        """验证文件完整性：重新计算 MD5 并与前端提供的哈希比对"""
        calculated_hash = hashlib.md5(content).hexdigest()
        if calculated_hash.lower() == provided_hash.lower():
            return True, calculated_hash, None
        return False, calculated_hash, IntegrityValidationError(
            field="hash",
            error="提供的MD5哈希值与实际文件内容不匹配",
            expected=provided_hash,
            actual=calculated_hash,
        )

    async def validate_file_format_and_size(
        self, filename: str, file_size: int
    ) -> None:
        """验证文件格式和大小"""
        if len(filename) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文件名过长",
                        "detail": {"field": "filename",
                                   "error": "文件名长度不能超过255个字符",
                                   "actual": len(filename)}},
            )

        valid_extensions = {".pdf", ".docx", ".doc"}
        ext = PurePath(filename).suffix.lower()
        if ext not in valid_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文件格式不支持",
                        "detail": {"field": "file",
                                   "error": f"仅支持 {', '.join(valid_extensions)} 格式",
                                   "actual": ext or "无扩展名"}},
            )

        max_size = settings.max_file_size
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文件大小超出限制",
                        "detail": {"field": "file",
                                   "error": f"文件大小不能超过 {max_mb:.0f}MB",
                                   "actual": f"{file_size / (1024 * 1024):.1f}MB"}},
            )

    # ---- 重复性检查 ----

    async def batch_check_duplicates(
        self, db: AsyncSession, files: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """批量检查重复文件，委托 DocumentRepository"""
        repo = DocumentRepository(db)
        duplicates = []
        for file_info in files:
            fhash = (file_info.get("hash") or "").lower()
            if not fhash or not re.match(r"^[a-fA-F0-9]{32}$", fhash):
                continue
            existing = await repo.get_by_hash(fhash)
            if existing:
                duplicates.append({
                    "filename": file_info.get("filename", "unknown"),
                    "hash": fhash,
                    "existing_document_id": str(existing.id),
                    "existing_filename": existing.original_filename,
                })
        return duplicates

    # ---- 上传主流程 ----

    async def process_upload(
        self,
        db: AsyncSession,
        file: UploadFile,
        provided_hash: str,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """处理文件上传的完整流程"""
        content = await file.read()
        file_size = len(content)
        original_filename = file.filename or "unknown"

        # 1. 完整性验证
        is_valid, calc_hash, error = await self.verify_file_integrity(content, provided_hash)
        if not is_valid:
            detail = error.model_dump() if hasattr(error, "model_dump") else str(error)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "上传文件不完整", "detail": detail},
            )

        # 2. 构建锁检查
        await _check_building_lock(db)

        # 3. 格式/大小验证
        await self.validate_file_format_and_size(original_filename, file_size)

        # 4. 重复性检查
        repo = DocumentRepository(db)
        existing = await repo.get_by_hash(calc_hash)
        if existing:
            return {
                "document_id": str(existing.id),
                "original_filename": existing.original_filename,
                "file_hash": existing.file_hash,
                "status": "duplicate",
            }

        # 5. 存储 + 入库
        return await self._store_and_persist(
            db, repo, content, original_filename, file_size, calc_hash, metadata
        )

    async def _store_and_persist(
        self,
        db: AsyncSession,
        repo: DocumentRepository,
        content: bytes,
        original_filename: str,
        file_size: int,
        file_hash: str,
        metadata: Optional[Dict],
    ) -> Dict:
        """MinIO 存储 → DB 插入 → 触发异步处理"""
        metadata = metadata or {}

        # MinIO 存储
        result = self.minio_service.upload_file(
            bucket_name=settings.minio_document_bucket,
            object_name=file_hash,
            file_data=content,
            content_type="application/octet-stream",
            metadata={
                "file_hash": file_hash,
                "file_size": str(file_size),
                "upload_time": datetime.now().isoformat(),
            },
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": 500, "message": "文件存储失败",
                        "detail": "无法将文件保存到存储系统"},
            )

        processing_id = f"proc_{uuid.uuid4().hex[:12]}"

        doc = Document(
            original_filename=original_filename,
            title=metadata.get("title") or original_filename,
            mime_type="application/octet-stream",
            file_size=file_size,
            file_hash=file_hash,
            status="enabled",
            attempt_no=1,
        )

        try:
            await repo.add(doc)
            await db.commit()
            await db.refresh(doc)

            # 9. 检查是否存在启用的知识库版本
            from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
            ver_result = await db.execute(
                select(KnowledgeBaseVersion).where(KnowledgeBaseVersion.status == "enabled").limit(1)
            )
            if not ver_result.scalar_one_or_none():
                return {
                    "document_id": str(doc.id),
                    "original_filename": original_filename,
                    "file_hash": file_hash,
                    "status": "success",
                    "warning": "NO_ENABLED_VERSION",
                }

            # 10. 异步触发处理
            from knowlebase.build.processing.service import get_processing_service
            asyncio.create_task(
                get_processing_service().process_document(db, doc.id, processing_id, 1)
            )

            return {
                "document_id": str(doc.id),
                "original_filename": original_filename,
                "file_hash": file_hash,
                "status": "success",
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"数据库保存失败: {e}")
            try:
                self.minio_service.delete_file(settings.minio_document_bucket, file_hash)
            except Exception as ce:
                logger.error(f"清理孤立文件失败: {ce}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": 500, "message": "文档保存失败", "detail": str(e)},
            )

    async def cleanup_orphaned_file(self, file_hash: str) -> bool:
        """从 MinIO 删除孤立文件"""
        try:
            if self.minio_service.file_exists(settings.minio_document_bucket, file_hash):
                if self.minio_service.delete_file(settings.minio_document_bucket, file_hash):
                    logger.info(f"清理孤立文件成功: {file_hash}")
                    return True
            return False
        except Exception as e:
            logger.error(f"清理孤立文件异常: {file_hash} - {e}")
            return False


# ---- 依赖注入 ----

_upload_service_instance: Optional[UploadService] = None


def get_upload_service() -> UploadService:
    global _upload_service_instance
    if _upload_service_instance is None:
        from knowlebase.services.minio_service import MinioService
        _upload_service_instance = UploadService(minio_service=MinioService())
    return _upload_service_instance


class DocumentService:
    """文档管理服务 — 薄编排层，委托 Repository + 领域对象"""

    # ---- 查询 ----

    async def get_document_list(
        self, db: AsyncSession, query_params: DocumentListQuery
    ) -> Dict:
        """获取文档列表"""
        repo = DocumentRepository(db)
        documents, total = await repo.list_with_filters(
            page=query_params.page,
            page_size=query_params.page_size,
            status=query_params.status.value if query_params.status else None,
            search=query_params.search,
            sort_by=query_params.sort_by,
            order=query_params.order,
        )

        doc_list = [{
            "id": d.id,
            "filename": d.file_hash,
            "original_filename": d.original_filename,
            "title": d.title,
            "file_size": d.file_size,
            "mime_type": d.mime_type,
            "file_hash": d.file_hash,
            "status": d.status,
            "created_by": None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        } for d in documents]

        return {
            "data": doc_list,
            "total": total,
            "page": query_params.page,
            "page_size": query_params.page_size,
            "total_pages": (total + query_params.page_size - 1) // query_params.page_size,
        }

    async def get_document_detail(self, db: AsyncSession, document_id: str) -> Optional[Dict]:
        """获取文档详情，含处理历史"""
        doc_repo = DocumentRepository(db)
        doc = await doc_repo.get_by_id(int(document_id))
        if not doc:
            return None

        # 通过 document_version_relation 获取处理历史
        hist_repo = ProcessingHistoryRepository(db)
        relations_result = await db.execute(
            select(DocumentVersionRelation).where(
                DocumentVersionRelation.document_id == int(document_id)
            )
        )
        relations = relations_result.scalars().all()

        processings = []
        for rel in relations:
            rel_histories = await hist_repo.get_by_relation_id(rel.id)
            processings.extend(rel_histories)
        # 按 attempt_no 降序排列
        processings.sort(key=lambda p: p.attempt_no, reverse=True)

        return {
            "document": {
                "id": doc.id,
                "filename": doc.file_hash,
                "original_filename": doc.original_filename,
                "title": doc.title,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "file_hash": doc.file_hash,
                "status": doc.status,
                "latest_processing_id": doc.processing_id,
                "build_id": doc.build_id,
                "created_by": None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            },
            "processing_history": [{
                "processing_id": p.processing_id,
                "attempt_no": p.attempt_no,
                "status": p.status,
                "current_stage": p.current_stage,
                "progress": p.progress,
                "started_at": p.started_at.isoformat() if p.started_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                "error_message": p.error_message,
            } for p in processings],
            "total_processings": len(processings),
        }

    # ---- 命令 ----

    async def enable_document(self, db: AsyncSession, document_id: str) -> None:
        """启用文档"""
        await _check_building_lock(db)
        repo = DocumentRepository(db)
        doc = await repo.get_by_id(int(document_id))
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"},
            )
        if doc.status == "enabled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文档已启用，无需重复操作"},
            )
        doc.enable()
        chunk_repo = DocumentChunkRepository(db)
        await chunk_repo.update_enabled_by_document_id(int(document_id), True)
        await db.commit()

    async def disable_document(self, db: AsyncSession, document_id: str) -> None:
        """停用文档"""
        await _check_building_lock(db)
        repo = DocumentRepository(db)
        doc = await repo.get_by_id(int(document_id))
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"},
            )
        if doc.status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文档已停用，无需重复操作"},
            )
        doc.disable()
        chunk_repo = DocumentChunkRepository(db)
        await chunk_repo.update_enabled_by_document_id(int(document_id), False)
        await db.commit()

    async def process_documents(
        self, db: AsyncSession, document_ids: List[int]
    ) -> List[BatchResult]:
        """批量触发文档处理（DEG 4.10）"""
        from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion

        # 1. 校验 document_ids 不为空
        if not document_ids:
            return []

        # 2. 查询当前启用的版本
        ver_result = await db.execute(
            select(KnowledgeBaseVersion).where(KnowledgeBaseVersion.status == "enabled").limit(1)
        )
        version = ver_result.scalar_one_or_none()
        if not version:
            return [BatchResult(id=str(doc_id), status="failed", reason="暂无启用的知识库版本，请先创建并启用一个版本") for doc_id in document_ids]

        # 3. 构建锁检查
        try:
            await _check_building_lock(db)
        except HTTPException:
            return [BatchResult(id=str(doc_id), status="failed", reason="知识库版本正在构建中，暂不支持此操作") for doc_id in document_ids]

        doc_repo = DocumentRepository(db)
        hist_repo = ProcessingHistoryRepository(db)
        from knowlebase.build.processing.service import get_processing_service
        processing_svc = get_processing_service()
        results = []

        for doc_id in document_ids:
            try:
                # 4. 查询文档
                doc = await doc_repo.get_by_id(doc_id)
                if not doc:
                    results.append(BatchResult(id=str(doc_id), status="failed", reason="文档不存在"))
                    continue

                # 4. 查询/创建关联记录
                relation = await processing_svc._get_or_create_relation(db, doc_id)
                if not relation:
                    results.append(BatchResult(id=str(doc_id), status="failed", reason="无启用的知识库版本"))
                    continue

                # 4. 检查是否有正在进行的处理
                if await hist_repo.has_active_processing(relation.id):
                    results.append(BatchResult(id=str(doc_id), status="failed", reason="文档正在处理中，请稍后再试"))
                    continue

                # 4. 创建处理历史记录（同步，status=pending）
                processing_id = f"proc_{uuid.uuid4().hex[:12]}"
                attempt_no = (await hist_repo.get_max_attempt_no(relation.id)) + 1

                proc = DocumentProcessingHistory(
                    relation_id=relation.id,
                    processing_id=processing_id,
                    attempt_no=attempt_no,
                    status="pending",
                )
                await hist_repo.add(proc)

                doc.processing_id = processing_id
                doc.attempt_no = attempt_no
                await db.flush()

                # 5. 调用构建域异步触发处理
                asyncio.create_task(
                    processing_svc.process_document(db, doc.id, processing_id, attempt_no, relation_id=relation.id)
                )

                results.append(BatchResult(
                    id=str(doc_id), status="success",
                    reason=f"processing_id={processing_id}"
                ))

            except Exception as e:
                logger.error(f"触发文档 {doc_id} 处理失败: {e}", exc_info=True)
                results.append(BatchResult(id=str(doc_id), status="failed", reason=str(e)))

        return results


# ---- 依赖注入 ----

_document_service_instance: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    global _document_service_instance
    if _document_service_instance is None:
        _document_service_instance = DocumentService()
    return _document_service_instance

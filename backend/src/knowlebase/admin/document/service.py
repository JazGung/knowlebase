"""文档管理服务

包含文档上传、管理、查询等业务逻辑
"""

import hashlib
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import PurePath
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.schemas.document import (
    DocumentListQuery,
    DocumentStatus,
    IntegrityValidationError,
)
from knowlebase.services.minio_service import MinioService, get_minio_service

logger = logging.getLogger(__name__)


class UploadService:
    """文档上传服务

    处理文件上传的完整流程，包括：
    - 文件完整性验证
    - 文件格式和大小校验
    - 重复性检查
    - Minio 存储
    - 数据库记录创建
    """

    def __init__(self, minio_service: MinioService):
        self.minio_service = minio_service

    async def verify_file_integrity(
        self, content: bytes, provided_hash: str
    ) -> Tuple[bool, Optional[str], Optional[IntegrityValidationError]]:
        """验证文件完整性

        重新计算上传内容的MD5哈希值，与前端提供的哈希进行验证

        Args:
            content: 上传的文件内容
            provided_hash: 前端提供的MD5哈希值

        Returns:
            (is_valid, calculated_hash, error): 验证结果、计算的哈希、错误详情
        """
        calculated_hash = hashlib.md5(content).hexdigest()
        is_match = calculated_hash.lower() == provided_hash.lower()
        if is_match:
            return True, calculated_hash, None
        else:
            error = IntegrityValidationError(
                field="hash",
                error="提供的MD5哈希值与实际文件内容不匹配",
                expected=provided_hash,
                actual=calculated_hash,
            )
            return False, calculated_hash, error

    async def validate_file_format_and_size(
        self, filename: str, file_size: int
    ) -> None:
        """验证文件格式和大小

        Args:
            filename: 文件名
            file_size: 文件大小（字节）

        Raises:
            HTTPException: 验证失败时抛出
        """
        # 检查文件名长度
        if len(filename) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "文件名过长",
                    "detail": {
                        "field": "filename",
                        "error": "文件名长度不能超过255个字符",
                        "actual": len(filename),
                    },
                },
            )

        # 检查文件扩展名
        valid_extensions = {".pdf", ".docx", ".doc"}
        file_path = PurePath(filename)
        extension = file_path.suffix.lower()

        if extension not in valid_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "文件格式不支持",
                    "detail": {
                        "field": "file",
                        "error": f"仅支持 {', '.join(valid_extensions)} 格式",
                        "actual": extension or "无扩展名",
                    },
                },
            )

        # 检查文件大小
        max_file_size = settings.max_file_size
        if file_size > max_file_size:
            max_size_mb = max_file_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "文件大小超出限制",
                    "detail": {
                        "field": "file",
                        "error": f"文件大小不能超过 {max_size_mb:.0f}MB",
                        "actual": f"{file_size / (1024 * 1024):.1f}MB",
                    },
                },
            )

    async def batch_check_duplicates(
        self, db: AsyncSession, files: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """批量检查重复文件

        检查给定的文件哈希是否已存在于数据库中

        Args:
            db: 数据库会话
            files: 文件列表，每个包含 filename 和 hash

        Returns:
            重复文件列表，包含原始文件名、哈希和已存在的文档信息
        """
        duplicates = []

        for file_info in files:
            filename = file_info.get("filename")
            file_hash = file_info.get("hash")

            if not filename or not file_hash:
                continue

            # 验证哈希格式
            if not re.match(r"^[a-fA-F0-9]{32}$", file_hash):
                continue

            # 查询数据库中是否存在相同哈希的文件
            query = select(Document).where(Document.file_hash == file_hash.lower())
            result = await db.execute(query)
            existing_doc = result.scalar_one_or_none()

            if existing_doc:
                duplicates.append(
                    {
                        "filename": filename,
                        "hash": file_hash.lower(),
                        "existing_document_id": str(existing_doc.id),
                        "existing_filename": existing_doc.original_filename,
                    }
                )

        return duplicates

    async def process_upload(
        self,
        db: AsyncSession,
        file: UploadFile,
        provided_hash: str,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """处理文件上传

        完整的文件上传流程：
        1. 读取文件内容
        2. 验证文件完整性
        3. 验证文件格式和大小
        4. 检查是否重复
        5. 处理文件（保存/更新）

        Args:
            db: 数据库会话
            file: 上传的文件
            provided_hash: 前端提供的MD5哈希
            metadata: 文档元数据
            user_id: 用户ID

        Returns:
            上传结果字典
        """
        # 读取文件内容
        content = await file.read()
        file_size = len(content)
        original_filename = file.filename or "unknown"

        # 1. 验证文件完整性
        is_valid, calc_hash, error = await self.verify_file_integrity(
            content, provided_hash
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 400,
                    "message": "上传文件不完整",
                    "detail": error.model_dump()
                    if hasattr(error, "model_dump")
                    else str(error),
                },
            )

        # 2. 验证文件格式和大小
        await self.validate_file_format_and_size(original_filename, file_size)

        # 3. 检查重复性
        query = select(Document).where(Document.file_hash == calc_hash)
        result = await db.execute(query)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            return {
                "document_id": str(existing_doc.id),
                "filename": existing_doc.file_hash,
                "original_filename": existing_doc.original_filename,
                "file_hash": existing_doc.file_hash,
                "file_size": existing_doc.file_size,
                "status": "duplicate",
                "processing_id": None,
                "processing_number": 1,
                "progress_stream_url": None,
            }

        # 4. 处理文件（保存/更新）
        return await self._process_file(
            db=db,
            content=content,
            original_filename=original_filename,
            file_size=file_size,
            file_hash=calc_hash,
            metadata=metadata,
            user_id=user_id,
        )

    async def cleanup_orphaned_file(self, file_hash: str) -> bool:
        """清理孤立文件

        从Minio中删除指定的文件，用于清理没有数据库记录的孤立文件

        Args:
            file_hash: 文件哈希（用作Minio中的文件名）

        Returns:
            是否成功删除
        """
        try:
            exists = self.minio_service.file_exists(settings.minio_document_bucket, file_hash)
            if exists:
                deleted = self.minio_service.delete_file(settings.minio_document_bucket, file_hash)
                if deleted:
                    logger.info(f"清理孤立文件成功: {file_hash}")
                    return True
                else:
                    logger.warning(f"清理孤立文件失败: {file_hash}")
                    return False
            else:
                logger.info(f"孤立文件不存在: {file_hash}")
                return False
        except Exception as e:
            logger.error(f"清理孤立文件异常: {file_hash} - {e}")
            return False

    async def _process_file(
        self,
        db: AsyncSession,
        content: bytes,
        original_filename: str,
        file_size: int,
        file_hash: str,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """内部方法：处理单个文件的上传

        Args:
            db: 数据库会话
            content: 文件内容
            original_filename: 原始文件名
            file_size: 文件大小
            file_hash: MD5 哈希
            metadata: 元数据
            user_id: 用户 ID

        Returns:
            上传结果
        """
        metadata = metadata or {}

        # 使用哈希值作为Minio中的文件名
        minio_filename = file_hash

        # 保存文件到Minio
        # 注意：MinIO metadata 是 HTTP headers，仅支持 ASCII，中文文件名存 PostgreSQL
        minio_result = self.minio_service.upload_file(
            bucket_name=settings.minio_document_bucket,
            object_name=minio_filename,
            file_data=content,
            content_type="application/octet-stream",
            metadata={
                "file_hash": file_hash,
                "file_size": str(file_size),
                "upload_time": datetime.now().isoformat(),
            },
        )

        if not minio_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": 500, "message": "文件存储失败", "detail": "无法将文件保存到存储系统"},
            )

        # 生成处理ID
        processing_id = f"proc_{uuid.uuid4().hex[:12]}"

        # 处理tags
        tags_str = metadata.get("tags")
        tags_list = None
        if tags_str and isinstance(tags_str, str):
            tags_list = [
                tag.strip()
                for tag in tags_str.split(",")
                if tag.strip()
            ]

        # 创建文档记录（id 自增长）
        doc = Document(
            original_filename=original_filename,
            title=metadata.get("title") or original_filename,
            description=metadata.get("description"),
            category=metadata.get("category"),
            tag=tags_list,
            mime_type="application/octet-stream",
            file_size=file_size,
            file_hash=file_hash,
            enabled=True,
        )

        try:
            db.add(doc)
            await db.flush()  # 刷新以获取 doc 的自增 ID

            # 创建处理记录（需要 doc.id）
            proc = DocumentProcessingHistory(
                document_id=doc.id,
                processing_id=processing_id,
                processing_number=1,
                status=DocumentStatus.PENDING,
                current_stage="uploading",
                progress=0,
                started_at=datetime.now(),
            )

            db.add(proc)
            await db.commit()
            await db.refresh(doc)
            await db.refresh(proc)

            # TODO: 触发异步处理任务

            progress_stream_url = f"/build/progress/stream?processing_id={processing_id}"

            return {
                "document_id": str(doc.id),
                "filename": minio_filename,
                "original_filename": original_filename,
                "file_hash": file_hash,
                "file_size": file_size,
                "status": "success",
                "processing_id": processing_id,
                "processing_number": 1,
                "progress_stream_url": progress_stream_url,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"数据库保存失败: {e}")
            # 尝试清理已上传的文件
            try:
                await self.cleanup_orphaned_file(file_hash)
            except Exception as cleanup_error:
                logger.error(f"清理孤立文件失败: {cleanup_error}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": 500, "message": "文档保存失败", "detail": str(e)},
            )


# 依赖注入
_upload_service_instance: Optional[UploadService] = None


def get_upload_service() -> UploadService:
    """获取UploadService实例（用于依赖注入）"""
    global _upload_service_instance
    if _upload_service_instance is None:
        _upload_service_instance = UploadService(
            minio_service=MinioService()
        )
    return _upload_service_instance


class DocumentService:
    """文档管理服务

    处理文档的查询、状态管理等业务逻辑
    """

    async def get_document_list(
        self, db: AsyncSession, query_params: DocumentListQuery
    ) -> Dict:
        """获取文档列表"""
        # 构建基础查询
        query = select(Document)

        # 添加过滤条件
        if query_params.status:
            query = query.where(Document.status == query_params.status)
        if query_params.enabled is not None:
            query = query.where(Document.enabled == query_params.enabled)
        if query_params.category:
            query = query.where(Document.category == query_params.category)
        if query_params.search:
            search_pattern = f"%{query_params.search}%"
            query = query.where(
                or_(
                    Document.original_filename.ilike(search_pattern),
                    Document.title.ilike(search_pattern),
                    Document.description.ilike(search_pattern),
                )
            )

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # 添加排序
        if query_params.sort_by == "created_at":
            order_col = Document.created_at
        elif query_params.sort_by == "updated_at":
            order_col = Document.updated_at
        elif query_params.sort_by == "original_filename":
            order_col = Document.original_filename
        else:
            order_col = Document.created_at

        if query_params.order == "asc":
            query = query.order_by(order_col.asc())
        else:
            query = query.order_by(order_col.desc())

        # 添加分页
        offset = (query_params.page - 1) * query_params.page_size
        query = query.offset(offset).limit(query_params.page_size)

        # 执行查询
        result = await db.execute(query)
        documents = result.scalars().all()

        # 转换为字典
        doc_list = []
        for doc in documents:
            doc_list.append(
                {
                    "id": doc.id,
                    "filename": doc.file_hash,
                    "original_filename": doc.original_filename,
                    "title": doc.title,
                    "description": doc.description,
                    "category": doc.category,
                    "tag": doc.tag or [],
                    "file_size": doc.file_size,
                    "mime_type": doc.mime_type,
                    "file_hash": doc.file_hash,
                    "enabled": doc.enabled,
                    "status": doc.status,
                    "created_by": None,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                }
            )

        return {
            "documents": doc_list,
            "pagination": {
                "page": query_params.page,
                "page_size": query_params.page_size,
                "total": total,
                "total_pages": (total + query_params.page_size - 1) // query_params.page_size,
            },
        }

    async def get_document_detail(self, db: AsyncSession, document_id: str) -> Optional[Dict]:
        """获取文档详情"""
        # 查询文档
        doc_query = select(Document).where(Document.id == document_id)
        doc_result = await db.execute(doc_query)
        doc = doc_result.scalar_one_or_none()

        if not doc:
            return None

        # 查询处理历史
        proc_query = (
            select(DocumentProcessingHistory)
            .where(DocumentProcessingHistory.document_id == document_id)
            .order_by(DocumentProcessingHistory.processing_number.desc())
        )
        proc_result = await db.execute(proc_query)
        processings = proc_result.scalars().all()

        processing_history = []
        for proc in processings:
            proc_dict = {
                "processing_id": proc.id,
                "processing_number": proc.processing_number,
                "status": proc.status,
                "current_stage": proc.current_stage,
                "progress": proc.progress,
                "started_at": proc.started_at.isoformat() if proc.started_at else None,
                "completed_at": proc.completed_at.isoformat() if proc.completed_at else None,
                "error_message": proc.error_message,
                "result": proc.result or {},
                "stage": proc.stage or [],
            }
            processing_history.append(proc_dict)

        return {
            "document": {
                "id": doc.id,
                "filename": doc.file_hash,
                "original_filename": doc.original_filename,
                "title": doc.title,
                "description": doc.description,
                "category": doc.category,
                "tags": doc.tags or [],
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "file_hash": doc.file_hash,
                "enabled": doc.enabled,
                "latest_processing_id": doc.latest_processing_id,
                "rebuild_id": doc.rebuild_id,
                "created_by": doc.created_by,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            },
            "processing_history": processing_history,
            "total_processings": len(processings),
        }

    async def enable_document(self, db: AsyncSession, document_id: str) -> None:
        """启用文档"""
        doc = await db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"},
            )
        if doc.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文档已启用，无需重复操作"},
            )
        doc.enabled = True
        doc.updated_at = datetime.now()
        await db.commit()

    async def disable_document(self, db: AsyncSession, document_id: str) -> None:
        """停用文档"""
        doc = await db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"},
            )
        if not doc.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文档已停用，无需重复操作"},
            )
        doc.enabled = False
        doc.updated_at = datetime.now()
        await db.commit()

    async def reprocess_document(
        self, db: AsyncSession, document_id: str, force_reprocess: bool = False
    ) -> Dict:
        """重新处理文档"""
        doc = await db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 404, "message": "文档不存在", "detail": f"文档ID: {document_id}"},
            )
        if doc.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "文档正在处理中，请稍后再试"},
            )
        if doc.status == "deleted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 400, "message": "已删除的文档不能重新处理"},
            )

        # 查询最大处理次数
        max_query = select(func.coalesce(func.max(DocumentProcessingHistory.processing_number), 0)).where(
            DocumentProcessingHistory.document_id == document_id
        )
        max_result = await db.execute(max_query)
        max_processing_number = max_result.scalar_one()

        new_processing_number = max_processing_number + 1
        processing_id = f"proc_{uuid.uuid4().hex[:12]}"

        proc = DocumentProcessingHistory(
            document_id=document_id,
            processing_id=processing_id,
            processing_number=new_processing_number,
            status=DocumentStatus.PENDING,
            current_stage="uploading",
            progress=0,
            started_at=datetime.now(),
        )

        db.add(proc)
        await db.commit()
        await db.refresh(proc)

        return {
            "document_id": document_id,
            "processing_id": processing_id,
            "processing_number": new_processing_number,
            "progress_stream_url": f"/build/progress/stream?processing_id={processing_id}",
        }


# 依赖注入
_document_service_instance: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取DocumentService实例"""
    global _document_service_instance
    if _document_service_instance is None:
        _document_service_instance = DocumentService()
    return _document_service_instance

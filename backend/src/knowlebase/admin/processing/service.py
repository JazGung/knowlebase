"""文档处理服务

包含文档解析等业务逻辑
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.models.document import Document, DocumentProcessingHistory
from knowlebase.parsers import parse_document
from knowlebase.parsers.base import ParseResult
from knowlebase.cleaners import clean_document
from knowlebase.chunker import chunk_document
from knowlebase.chunker.image_describer import replace_images_with_markers
from knowlebase.services.minio_service import get_minio_service

logger = logging.getLogger(__name__)


class ProcessingService:
    """文档处理服务

    处理流水线：下载 → 解析 → 清洗 → 图片描述 → 分块 → 存储/向量化
    """

    async def process_document(
        self,
        db: AsyncSession,
        document_id: int,
        processing_id: str,
    ) -> Dict:
        """处理单个文档：下载文件并解析

        Args:
            db: 数据库会话
            document_id: 文档 ID
            processing_id: 处理任务 ID

        Returns:
            处理结果字典
        """
        # 1. 查询文档记录
        doc = await db.get(Document, document_id)
        if not doc:
            raise ValueError(f"文档不存在: document_id={document_id}")

        file_hash = doc.file_hash
        mime_type = doc.mime_type or "application/octet-stream"
        filename = doc.original_filename

        logger.info(f"开始处理文档: {filename} (hash={file_hash})")

        # 更新处理历史状态为 processing
        proc = await self._get_processing_record(db, processing_id)
        if proc:
            proc.status = "processing"
            proc.current_stage = "parsing"
            proc.progress = 10
            await db.commit()

        try:
            # 2. 从 MinIO 下载文件
            minio_svc = get_minio_service()
            content = minio_svc.download_file(settings.minio_document_bucket, file_hash)
            logger.info(f"文档下载完成: {filename} ({len(content)} bytes)")

            # 3. 解析文档
            if proc:
                proc.current_stage = "parsing"
                proc.progress = 50
                await db.commit()

            result = await parse_document(content, filename=filename, mime_type=mime_type)
            logger.debug(
                f"解析结果详情: {filename}\n"
                f"{json.dumps(self._parse_result_to_dict(result), ensure_ascii=False, indent=2)}"
            )

            # 3.5. 清洗文档
            result = clean_document(result)
            logger.info(
                f"清洗完成: {filename}, "
                f"sections={len(result.sections)}, "
                f"has_images={result.has_images}"
            )

            # 4. 图片描述 + 分块
            if proc:
                proc.current_stage = "chunking"
                proc.progress = 70
                await db.commit()

            # 图片描述：将 ParsedImage 替换为 [IMAGE_START:caption]描述[IMAGE_END]
            result = replace_images_with_markers(result)

            # LLM 分块
            chunks = chunk_document(result.sections, metadata={"filename": filename})
            logger.info(
                f"分块完成: {filename}, chunks={len(chunks)}, "
                f"total_relations={sum(len(c.relations) for c in chunks)}"
            )

            # TODO: 5. 存储分块结果到向量库/图谱

            # 6. 更新文档状态
            doc.status = "success"
            doc.processed_at = datetime.now()
            doc.processing_id = processing_id

            # 5. 更新处理历史
            if proc:
                proc.status = "success"
                proc.current_stage = "completed"
                proc.progress = 100
                proc.completed_at = datetime.now()
                proc.result = {
                    "page_count": result.page_count,
                    "has_images": result.has_images,
                    "has_tables": result.has_tables,
                    "chunks_count": len(chunks),
                    "relations_count": sum(len(c.relations) for c in chunks),
                }

            await db.commit()
            logger.info(f"文档处理成功: {filename}")

            return {
                "document_id": str(document_id),
                "processing_id": processing_id,
                "status": "success",
                "page_count": result.page_count,
                "chunks_count": len(chunks),
            }

        except Exception as e:
            logger.error(f"文档处理失败: {filename} - {e}", exc_info=True)

            # 更新文档状态为 failed
            try:
                doc.status = "failed"
                if proc:
                    proc.status = "failed"
                    proc.error_message = str(e)
                    proc.completed_at = datetime.now()
                await db.commit()
            except Exception as db_err:
                logger.error(f"更新失败状态时出错: {db_err}")

            raise

    async def _get_processing_record(
        self, db: AsyncSession, processing_id: str
    ):
        """根据 processing_id 查询处理记录"""
        query = select(DocumentProcessingHistory).where(
            DocumentProcessingHistory.processing_id == processing_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    def _parse_result_to_dict(self, result: ParseResult) -> Dict:
        """将 ParseResult dataclass 转为可 JSON 序列化的 dict（用于 debug 日志）"""

        def convert_item(item):
            return asdict(item)

        sections = []
        for section in result.sections:
            sections.append(convert_item(section))

        return {
            "page_count": result.page_count,
            "has_images": result.has_images,
            "has_tables": result.has_tables,
            "sections": sections,
        }


def get_processing_service() -> ProcessingService:
    """获取 ProcessingService 实例"""
    return ProcessingService()

"""
StageResultRepository — 处理阶段结果持久化操作

一对一管理 ProcessingStageResult 领域对象的查询、插入、更新。
"""

import logging
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.processing_stage_result import ProcessingStageResult

logger = logging.getLogger(__name__)


class StageResultRepository:
    """处理阶段结果 Repository"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_processing_and_stage(
        self, processing_id: str, stage_name: str
    ) -> Optional[ProcessingStageResult]:
        """通过 processing_id 和 stage_name 查询阶段结果"""
        result = await self.db.execute(
            select(ProcessingStageResult).where(
                ProcessingStageResult.processing_id == processing_id,
                ProcessingStageResult.stage_name == stage_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_processing_id(
        self, processing_id: str
    ) -> List[ProcessingStageResult]:
        """查询某个处理任务的所有阶段结果（按创建时间升序）"""
        result = await self.db.execute(
            select(ProcessingStageResult)
            .where(ProcessingStageResult.processing_id == processing_id)
            .order_by(ProcessingStageResult.created_at.asc())
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        processing_id: str,
        stage_name: str,
        status: str,
        duration_ms: int,
        result_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ProcessingStageResult:
        """插入或更新阶段结果"""
        existing = await self.get_by_processing_and_stage(processing_id, stage_name)
        if existing is None:
            existing = ProcessingStageResult(
                processing_id=processing_id,
                stage_name=stage_name,
                status=status,
                duration_ms=duration_ms,
                result_path=result_path,
                error_message=error_message,
            )
            self.db.add(existing)
        else:
            existing.status = status
            existing.duration_ms = duration_ms
            if result_path is not None:
                existing.result_path = result_path
            if error_message is not None:
                existing.error_message = error_message
        await self.db.flush()
        return existing

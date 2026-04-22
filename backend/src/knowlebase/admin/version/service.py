"""知识库版本管理服务

包含版本创建、启用、回退、锁定检查等业务逻辑
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
from knowlebase.models.document_version_relation import DocumentVersionRelation
from knowlebase.schemas.version import VersionStatus, RelationType

logger = logging.getLogger(__name__)


class VersionService:
    """知识库版本管理服务"""

    async def list_versions(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[VersionStatus] = None,
    ) -> Tuple[List[KnowledgeBaseVersion], int]:
        """分页查询版本列表

        Returns:
            (versions, total)
        """
        query = select(KnowledgeBaseVersion)
        if status_filter:
            query = query.where(KnowledgeBaseVersion.status == status_filter.value)
        query = query.order_by(KnowledgeBaseVersion.version_id.desc())

        # 查询总数
        count_query = select(func.count()).select_from(KnowledgeBaseVersion)
        if status_filter:
            count_query = count_query.where(KnowledgeBaseVersion.status == status_filter.value)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await db.execute(query)
        versions = result.scalars().all()

        return list(versions), total

    async def get_version_detail(
        self, db: AsyncSession, version_id: str
    ) -> Optional[KnowledgeBaseVersion]:
        """查询版本详情"""
        query = select(KnowledgeBaseVersion).where(
            KnowledgeBaseVersion.version_id == version_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def create_version(
        self, db: AsyncSession, created_by: Optional[str] = None
    ) -> KnowledgeBaseVersion:
        """创建新版本（status = building）

        TODO: 后续在此方法中触发重建流程：
        1) 查询所有 enabled 文档
        2) 对每个文档执行文档处理流程
        3) 全部完成后更新 status = succeeded
        目前仅创建版本记录并标记 succeeded（留空实现）
        """
        # 检查是否已有 building 状态的版本
        existing = await self._get_building_version(db)
        if existing:
            raise ValueError(f"已存在重建中的版本: {existing.version_id}，请等待完成后再操作")

        # 生成版本ID
        now = datetime.now(timezone.utc)
        version_id = f"v{now.strftime('%Y%m%d_%H%M%S')}"

        # 创建版本记录
        version = KnowledgeBaseVersion(
            version_id=version_id,
            status="building",
            created_by=created_by,
            started_at=now,
        )
        db.add(version)
        await db.flush()

        # TODO: 执行重建流程（遍历 enabled 文档并处理）
        # 目前留空，直接标记为 succeeded
        logger.info(f"版本 {version_id} 创建成功（重建流程待实现）")
        version.status = "succeeded"
        version.completed_at = datetime.now(timezone.utc)
        await db.flush()

        return version

    async def enable_version(
        self, db: AsyncSession, version_id: str
    ) -> Tuple[Optional[KnowledgeBaseVersion], KnowledgeBaseVersion]:
        """启用版本

        1) 检查目标版本存在且 status = succeeded
        2) 将当前 enabled 版本改为 disabled
        3) 将目标版本改为 enabled

        Returns:
            (old_enabled_version, new_enabled_version)
        """
        # 查询目标版本
        target = await self.get_version_detail(db, version_id)
        if not target:
            raise ValueError(f"版本不存在: {version_id}")
        if target.status not in ("succeeded", "disabled"):
            raise ValueError(f"版本状态为 {target.status}，无法启用（需为 succeeded 或 disabled）")

        # 将当前 enabled 版本改为 disabled
        old_enabled = await self.get_enabled_version(db)
        if old_enabled:
            old_enabled.status = "disabled"
            await db.flush()
            logger.info(f"版本 {old_enabled.version_id} 已停用")

        # 启用目标版本
        target.status = "enabled"
        await db.flush()
        logger.info(f"版本 {target.version_id} 已启用")

        return old_enabled, target

    async def disable_version(
        self, db: AsyncSession, version_id: str
    ) -> KnowledgeBaseVersion:
        """停用版本（不能停用 enabled 的）"""
        version = await self.get_version_detail(db, version_id)
        if not version:
            raise ValueError(f"版本不存在: {version_id}")
        if version.status == "enabled":
            raise ValueError("不能停用当前启用的版本，请先启用其他版本")
        if version.status not in ("succeeded", "disabled"):
            raise ValueError(f"版本状态为 {version.status}，无法停用")

        version.status = "disabled"
        await db.flush()
        logger.info(f"版本 {version.version_id} 已停用")

        return version

    async def delete_version(
        self, db: AsyncSession, version_id: str
    ) -> KnowledgeBaseVersion:
        """删除版本（不能删除 enabled 的）"""
        version = await self.get_version_detail(db, version_id)
        if not version:
            raise ValueError(f"版本不存在: {version_id}")
        if version.status == "enabled":
            raise ValueError("不能删除当前启用的版本，请先启用其他版本")

        db.delete(version)
        await db.flush()
        logger.info(f"版本 {version.version_id} 已删除")

        return version

    async def get_enabled_version(
        self, db: AsyncSession
    ) -> Optional[KnowledgeBaseVersion]:
        """获取当前 enabled 版本"""
        query = select(KnowledgeBaseVersion).where(
            KnowledgeBaseVersion.status == "enabled"
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def check_building_lock(self, db: AsyncSession) -> Optional[KnowledgeBaseVersion]:
        """检查是否存在 building 版本（重建锁定检查）"""
        return await self._get_building_version(db)

    async def ensure_version_exists(
        self, db: AsyncSession
    ) -> KnowledgeBaseVersion:
        """确保存在 enabled 版本，无则自动创建初始版本"""
        enabled = await self.get_enabled_version(db)
        if enabled:
            return enabled

        # 自动创建初始版本
        now = datetime.now(timezone.utc)
        version_id = f"v{now.strftime('%Y%m%d_%H%M%S')}"
        version = KnowledgeBaseVersion(
            version_id=version_id,
            status="succeeded",  # 初始版本直接标记 succeeded（无重建过程）
            created_by="system",
            started_at=now,
            completed_at=now,
        )
        db.add(version)
        await db.flush()
        logger.info(f"自动创建初始版本: {version_id}")

        return version

    async def create_version_relation(
        self,
        db: AsyncSession,
        document_id: int,
        version_id: int,
        relation_type: RelationType,
        status: str = "pending",
    ) -> DocumentVersionRelation:
        """建立文档-版本关联"""
        relation = DocumentVersionRelation(
            document_id=document_id,
            version_id=version_id,
            relation_type=relation_type.value if isinstance(relation_type, RelationType) else relation_type,
            status=status,
        )
        db.add(relation)
        await db.flush()
        return relation

    async def _get_building_version(
        self, db: AsyncSession
    ) -> Optional[KnowledgeBaseVersion]:
        """查询 building 状态的版本"""
        query = select(KnowledgeBaseVersion).where(
            KnowledgeBaseVersion.status == "building"
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()


# 全局服务实例
_version_service_instance: Optional[VersionService] = None


def get_version_service() -> VersionService:
    """获取VersionService实例"""
    global _version_service_instance
    if _version_service_instance is None:
        _version_service_instance = VersionService()
    return _version_service_instance

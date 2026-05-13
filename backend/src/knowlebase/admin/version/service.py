"""知识库版本管理服务

包含版本创建、构建、启用等业务逻辑
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
from knowlebase.schemas.version import VersionStatus

logger = logging.getLogger(__name__)


class VersionService:
    """知识库版本管理服务"""

    # ---- 查询 ----

    async def list_versions(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[VersionStatus] = None,
    ) -> Tuple[List[KnowledgeBaseVersion], int]:
        """分页查询版本列表，按 version_name 降序"""
        query = select(KnowledgeBaseVersion)
        count_query = select(func.count()).select_from(KnowledgeBaseVersion)
        if status_filter:
            query = query.where(KnowledgeBaseVersion.status == status_filter.value)
            count_query = count_query.where(KnowledgeBaseVersion.status == status_filter.value)
        query = query.order_by(KnowledgeBaseVersion.version_name.desc())

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await db.execute(query)
        versions = result.scalars().all()

        return list(versions), total

    async def get_by_version_name(
        self, db: AsyncSession, version_name: str
    ) -> Optional[KnowledgeBaseVersion]:
        """按 version_name 查询版本"""
        query = select(KnowledgeBaseVersion).where(
            KnowledgeBaseVersion.version_name == version_name
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_enabled_version(
        self, db: AsyncSession
    ) -> Optional[KnowledgeBaseVersion]:
        """获取当前 enabled 版本"""
        query = select(KnowledgeBaseVersion).where(
            KnowledgeBaseVersion.status == "enabled"
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    # ---- 命令 ----

    async def create_version(
        self, db: AsyncSession, created_by: Optional[str] = None
    ) -> KnowledgeBaseVersion:
        """创建新版本，状态=init"""
        now = datetime.now(timezone.utc)
        version_name = f"v{now.strftime('%Y%m%d_%H%M%S')}"

        version = KnowledgeBaseVersion(
            version_name=version_name,
            status="init",
            created_by=created_by,
            started_at=now,
        )
        db.add(version)
        await db.flush()

        logger.info(f"版本 {version_name} 创建成功")
        return version

    async def build_version(
        self, db: AsyncSession, version_name: str
    ) -> KnowledgeBaseVersion:
        """触发版本构建，状态改为 building 后异步执行"""
        version = await self.get_by_version_name(db, version_name)
        if not version:
            raise ValueError(f"版本不存在: {version_name}")

        if version.status not in ("init", "failed"):
            raise ValueError(f"该版本无法构建，仅可构建 初始化 或 失败 状态的版本")

        # 检查是否已有 building 版本
        existing = await self._get_building_version(db)
        if existing:
            raise ValueError(f"已有版本正在构建中，请等待完成后再操作 (版本: {existing.version_name})")

        version.start_build()
        await db.flush()
        logger.info(f"版本 {version_name} 开始构建")

        return version

    async def enable_version(
        self, db: AsyncSession, version_name: str
    ) -> Tuple[Optional[KnowledgeBaseVersion], KnowledgeBaseVersion]:
        """启用版本，自动替换当前启用版本"""
        target = await self.get_by_version_name(db, version_name)
        if not target:
            raise ValueError(f"版本不存在: {version_name}")

        if target.status not in ("succeeded", "disabled"):
            raise ValueError(f"该版本无法启用，仅可启用 成功 或 已禁用 状态的版本")

        if target.status == "enabled":
            raise ValueError("该版本已是启用状态，无需重复操作")

        # 将当前 enabled 版本改为 disabled
        old_enabled = await self.get_enabled_version(db)
        if old_enabled:
            old_enabled.status = "disabled"
            await db.flush()
            logger.info(f"版本 {old_enabled.version_name} 已停用")

        # 启用目标版本
        target.status = "enabled"
        await db.flush()
        logger.info(f"版本 {target.version_name} 已启用")

        return old_enabled, target

    async def ensure_enabled_version_exists(
        self, db: AsyncSession
    ) -> KnowledgeBaseVersion:
        """确保存在 enabled 版本，无则自动创建→构建→启用"""
        enabled = await self.get_enabled_version(db)
        if enabled:
            return enabled

        now = datetime.now(timezone.utc)
        version_name = f"v{now.strftime('%Y%m%d_%H%M%S')}"
        version = KnowledgeBaseVersion(
            version_name=version_name,
            status="succeeded",
            created_by="system",
            started_at=now,
            completed_at=now,
        )
        db.add(version)
        await db.flush()

        # 启用
        version.status = "enabled"
        await db.flush()
        logger.info(f"自动创建并启用初始版本: {version_name}")

        return version

    # ---- 内部 ----

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

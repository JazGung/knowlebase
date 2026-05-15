"""
知识库版本管理测试 — TDD

测试版本模型、服务层的正常和异常流程。
使用 SQLite 内存数据库，无需外部依赖。
"""

import pytest
import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
from knowlebase.schemas.version import VersionStatus
from knowlebase.resource.version.service import VersionService


@pytest.fixture
async def engine():
    """创建 SQLite 内存数据库引擎"""
    e = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with e.begin() as conn:
        # Only create knowledge_base_version table for these tests
        await conn.run_sync(lambda sync_conn: KnowledgeBaseVersion.__table__.create(sync_conn, checkfirst=True))
    yield e
    await e.dispose()


@pytest.fixture
async def db_session(engine):
    """创建数据库会话"""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # 实验前清空
        from sqlalchemy import delete
        await session.execute(delete(KnowledgeBaseVersion))
        await session.commit()
        yield session
        await session.rollback()


@pytest.fixture
def service():
    return VersionService()


# ==================== 模型领域方法 ====================

class TestKnowledgeBaseVersion:
    """KnowledgeBaseVersion 领域模型测试"""

    def test_default_status_is_init(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000")
        # SQL-level default，Python 对象层面 status 为 None（由 DB 填充）
        assert v.status is None or v.status == "init"

    def test_start_build_from_init(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="init")
        v.start_build()
        assert v.status == "building"

    def test_start_build_from_failed(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="failed")
        v.start_build()
        assert v.status == "building"

    def test_start_build_from_succeeded_raises(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="succeeded")
        with pytest.raises(ValueError, match="无法构建"):
            v.start_build()

    def test_start_build_from_building_raises(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="building")
        with pytest.raises(ValueError, match="无法构建"):
            v.start_build()

    def test_complete_build_success(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="building")
        v.complete_build(document_count=5, chunk_count=50)
        assert v.status == "succeeded"
        assert v.document_count == 5
        assert v.chunk_count == 50
        assert v.completed_at is not None

    def test_complete_build_wrong_status_raises(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="init")
        with pytest.raises(ValueError, match="无法完成构建"):
            v.complete_build(5, 50)

    def test_fail_build(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="building")
        v.fail_build("构建超时")
        assert v.status == "failed"
        assert v.error_message == "构建超时"
        assert v.completed_at is not None

    def test_enable_from_succeeded(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="succeeded")
        v.enable()
        assert v.status == "enabled"

    def test_enable_from_disabled(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="disabled")
        v.enable()
        assert v.status == "enabled"

    def test_enable_from_init_raises(self):
        v = KnowledgeBaseVersion(version_name="v20260422_103000", status="init")
        with pytest.raises(ValueError, match="无法启用"):
            v.enable()

    def test_to_dict_returns_all_fields(self):
        v = KnowledgeBaseVersion(
            version_name="v20260422_103000",
            status="init",
            document_count=0,
            chunk_count=0,
            created_by="admin",
        )
        d = v.to_dict()
        assert d["version_name"] == "v20260422_103000"
        assert d["status"] == "init"
        assert d["document_count"] == 0
        assert d["chunk_count"] == 0
        assert d["created_by"] == "admin"
        assert "id" in d
        assert "started_at" in d
        assert "completed_at" in d
        assert "created_at" in d
        assert "updated_at" in d


# ==================== 服务层 ====================

class TestVersionService:
    """VersionService 服务层测试"""

    @pytest.mark.asyncio
    async def test_create_version_init_status(self, db_session, service):
        v = await service.create_version(db_session, created_by="admin")
        await db_session.commit()

        assert v.version_name.startswith("v")
        assert v.status == "init"
        assert v.created_by == "admin"
        assert v.started_at is not None

    @pytest.mark.asyncio
    async def test_list_versions_pagination(self, db_session, service):
        for _ in range(3):
            await service.create_version(db_session, created_by="test")
            await asyncio.sleep(1.1)  # 避免时间戳重复导致 version_name 冲突
        await db_session.commit()

        versions, total = await service.list_versions(db_session, page=1, page_size=2)
        assert len(versions) == 2
        assert total == 3

    @pytest.mark.asyncio
    async def test_list_versions_status_filter(self, db_session, service):
        v = await service.create_version(db_session, created_by="test")
        v.start_build()
        await db_session.commit()

        versions, total = await service.list_versions(
            db_session, status_filter=VersionStatus.BUILDING
        )
        assert total == 1
        assert versions[0].status == "building"

    @pytest.mark.asyncio
    async def test_list_versions_desc_order(self, db_session, service):
        v1 = await service.create_version(db_session, created_by="test")
        await asyncio.sleep(1.1)
        v2 = await service.create_version(db_session, created_by="test")
        await db_session.commit()

        versions, _ = await service.list_versions(db_session)
        assert versions[0].version_name == v2.version_name
        assert versions[1].version_name == v1.version_name

    @pytest.mark.asyncio
    async def test_get_by_version_name_not_found(self, db_session, service):
        v = await service.get_by_version_name(db_session, "nonexistent")
        assert v is None

    @pytest.mark.asyncio
    async def test_get_by_version_name_found(self, db_session, service):
        created = await service.create_version(db_session, created_by="test")
        await db_session.commit()

        found = await service.get_by_version_name(db_session, created.version_name)
        assert found is not None
        assert found.version_name == created.version_name

    @pytest.mark.asyncio
    async def test_build_version_from_init(self, db_session, service):
        v = await service.create_version(db_session, created_by="test")
        await db_session.commit()

        built = await service.build_version(db_session, v.version_name)
        await db_session.commit()

        assert built.status == "building"

    @pytest.mark.asyncio
    async def test_build_version_not_found(self, db_session, service):
        with pytest.raises(ValueError, match="版本不存在"):
            await service.build_version(db_session, "nonexistent")

    @pytest.mark.asyncio
    async def test_build_version_wrong_status(self, db_session, service):
        v = await service.create_version(db_session, created_by="test")
        v.start_build()
        v.complete_build(0, 0)
        await db_session.commit()

        with pytest.raises(ValueError, match="无法构建"):
            await service.build_version(db_session, v.version_name)

    @pytest.mark.asyncio
    async def test_build_version_blocks_if_building_exists(self, db_session, service):
        v1 = await service.create_version(db_session, created_by="test")
        v1.start_build()
        await db_session.commit()

        await asyncio.sleep(1.1)
        v2 = await service.create_version(db_session, created_by="test")
        await db_session.commit()

        with pytest.raises(ValueError, match="已有版本正在构建中"):
            await service.build_version(db_session, v2.version_name)

    @pytest.mark.asyncio
    async def test_enable_version(self, db_session, service):
        v = await service.create_version(db_session, created_by="test")
        v.start_build()
        v.complete_build(1, 10)
        await db_session.commit()

        old, new = await service.enable_version(db_session, v.version_name)
        await db_session.commit()

        assert old is None  # 之前没有启用的版本
        assert new.status == "enabled"

    @pytest.mark.asyncio
    async def test_enable_replaces_previous_enabled(self, db_session, service):
        v1 = await service.create_version(db_session, created_by="test")
        v1.start_build()
        v1.complete_build(1, 10)
        v1.status = "enabled"
        await db_session.commit()

        await asyncio.sleep(1.1)
        v2 = await service.create_version(db_session, created_by="test")
        v2.start_build()
        v2.complete_build(2, 20)
        await db_session.commit()

        old, new = await service.enable_version(db_session, v2.version_name)
        await db_session.commit()

        assert old is not None
        assert old.version_name == v1.version_name
        assert new.version_name == v2.version_name

        # 验证旧版本被禁用
        old_refreshed = await service.get_by_version_name(db_session, v1.version_name)
        assert old_refreshed.status == "disabled"

    @pytest.mark.asyncio
    async def test_enable_already_enabled(self, db_session, service):
        v = await service.create_version(db_session, created_by="test")
        v.start_build()
        v.complete_build(1, 10)
        v.status = "enabled"
        await db_session.commit()

        with pytest.raises(ValueError):
            await service.enable_version(db_session, v.version_name)

    @pytest.mark.asyncio
    async def test_ensure_enabled_version_exists_creates(self, db_session, service):
        v = await service.ensure_enabled_version_exists(db_session)
        await db_session.commit()

        assert v.status == "enabled"
        assert v.version_name.startswith("v")

    @pytest.mark.asyncio
    async def test_ensure_enabled_version_exists_reuses(self, db_session, service):
        v1 = await service.ensure_enabled_version_exists(db_session)
        await db_session.commit()

        v2 = await service.ensure_enabled_version_exists(db_session)
        assert v2.id == v1.id

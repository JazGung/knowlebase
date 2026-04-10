"""
数据库会话管理模块

功能：
1. SQLAlchemy引擎配置
2. 异步会话工厂创建
3. 数据库连接池管理
4. 依赖注入支持
"""

import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """
    SQLAlchemy声明式基类

    所有数据库模型都应继承此类
    """
    pass


class DatabaseSessionManager:
    """
    数据库会话管理器

    管理数据库引擎和会话工厂的生命周期
    """

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def init(self, database_url: str, **engine_kwargs):
        """
        初始化数据库引擎和会话工厂

        Args:
            database_url: 数据库连接URL
            **engine_kwargs: 额外的引擎配置参数
        """
        if self._engine is not None:
            logger.warning("数据库引擎已经初始化")
            return

        # 默认引擎配置
        default_engine_kwargs = {
            "echo": settings.debug,  # 在调试模式下输出SQL语句
            "echo_pool": settings.debug,  # 在调试模式下输出连接池信息
            "pool_pre_ping": True,  # 连接前检查连接是否有效
            "pool_size": 20,  # 连接池大小
            "max_overflow": 10,  # 最大溢出连接数
            "pool_recycle": 3600,  # 连接回收时间（秒）
            "pool_timeout": 30,  # 连接获取超时时间（秒）
            "poolclass": AsyncAdaptedQueuePool,  # 异步适配的连接池
        }

        # 合并配置
        engine_kwargs = {**default_engine_kwargs, **engine_kwargs}

        logger.info(f"初始化数据库引擎: {database_url}")
        logger.debug(f"引擎配置: {engine_kwargs}")

        try:
            self._engine = create_async_engine(database_url, **engine_kwargs)
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,  # 提交后不使对象过期
                autoflush=False,  # 禁用自动刷新
            )
            logger.info("数据库引擎初始化成功")
        except Exception as e:
            logger.error(f"数据库引擎初始化失败: {e}")
            raise

    async def close(self):
        """关闭数据库引擎"""
        if self._engine is None:
            return

        logger.info("关闭数据库引擎...")
        try:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("数据库引擎关闭成功")
        except Exception as e:
            logger.error(f"数据库引擎关闭失败: {e}")
            raise

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话

        Yields:
            AsyncSession: 异步数据库会话

        Usage:
            async with session_manager.get_session() as session:
                # 使用session执行数据库操作
                result = await session.execute(query)
        """
        if self._session_factory is None:
            raise RuntimeError("数据库会话工厂未初始化")

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @property
    def engine(self) -> AsyncEngine:
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("数据库会话工厂未初始化")
        return self._session_factory


# 全局数据库会话管理器实例
session_manager = DatabaseSessionManager()


def init_database():
    """初始化数据库连接"""
    database_url = settings.database_url

    # 确保使用异步PostgreSQL驱动
    if not database_url.startswith("postgresql+asyncpg://"):
        # 替换为异步驱动
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            raise ValueError(f"不支持的数据库URL格式: {database_url}")

    session_manager.init(database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数

    用于FastAPI的路由依赖注入

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            # 使用db执行数据库操作
            pass
    """
    async for session in session_manager.get_session():
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    获取会话工厂的依赖注入函数

    用于需要手动创建会话的场景
    """
    return session_manager.session_factory


# 应用启动时初始化数据库
def initialize_database():
    """应用启动时调用此函数初始化数据库"""
    logger.info("初始化数据库连接...")
    try:
        init_database()
        logger.info("数据库连接初始化完成")
    except Exception as e:
        logger.error(f"数据库连接初始化失败: {e}")
        raise


if __name__ == "__main__":
    # 测试数据库连接
    import asyncio

    async def test_connection():
        initialize_database()

        async with session_manager.get_session() as session:
            # 执行简单的查询测试连接
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            row = result.fetchone()
            print(f"数据库连接测试成功: {row}")

            # 测试Base元数据
            print(f"Base元数据: {Base.metadata}")

    asyncio.run(test_connection())
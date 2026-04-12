"""
FastAPI应用入口点

主要功能：
1. FastAPI应用实例初始化
2. 全局中间件配置（CORS、异常处理等）
3. 路由注册
4. 应用生命周期事件处理
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from knowlebase.core.config import settings
from knowlebase.db.session import session_manager, initialize_database
from knowlebase.services.minio_service import init_minio
from knowlebase.admin import build_router

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器

    处理应用启动和关闭事件
    """
    # 启动事件
    logger.info("应用启动中...")
    logger.info(f"数据库配置: {settings.get_database_config_summary()}")
    logger.info(f"开发模式: {settings.is_local_development()}")

    # 初始化数据库连接
    logger.info("初始化数据库连接...")
    initialize_database()
    logger.info("数据库连接初始化完成")

    # 初始化Minio连接
    logger.info("初始化Minio连接...")
    init_minio()
    logger.info("Minio连接初始化完成")

    yield

    # 关闭事件
    logger.info("应用关闭中...")
    # 清理数据库连接等资源
    try:
        await session_manager.close()
        logger.info("数据库连接关闭完成")
    except Exception as e:
        logger.error(f"关闭数据库连接时出错: {e}")


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例
    """
    app = FastAPI(
        title="知识库构建与检索系统",
        description="企业内部知识库文档管理和智能检索系统",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"全局异常: {exc}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "detail": str(exc) if settings.debug else "内部服务器错误"
            }
        )

    # 健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        return {
            "code": 0,
            "message": "服务正常",
            "data": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2026-04-09T00:00:00Z"
            }
        }

    # 根端点
    @app.get("/")
    async def root():
        """应用根端点"""
        return {
            "code": 0,
            "message": "知识库构建与检索系统 API",
            "data": {
                "name": "知识库构建与检索系统",
                "version": "1.0.0",
                "description": "企业内部知识库文档管理和智能检索系统",
                "docs": "/docs" if settings.debug else None
            }
        }

    # 注册API路由
    app.include_router(build_router, prefix="/build")

    logger.info("FastAPI应用创建完成")
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    logger.info("启动开发服务器...")
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
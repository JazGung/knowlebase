"""管理后台模块"""

from fastapi import APIRouter

from knowlebase.admin.document.api import router as document_router
from knowlebase.admin.processing.api import router as processing_router
from knowlebase.admin.version.api import router as version_router

# 创建/build路由器
build_router = APIRouter()

# 注册文档管理子路由
build_router.include_router(
    document_router,
    prefix="/document",
    tags=["文档管理"]
)

# 注册文档处理子路由
build_router.include_router(
    processing_router,
    prefix="/processing",
    tags=["文档处理"]
)

# 注册知识库版本管理子路由
build_router.include_router(
    version_router,
    prefix="/version",
    tags=["知识库版本管理"]
)

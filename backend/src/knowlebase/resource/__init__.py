"""业务资源域 — /resource/*"""

from fastapi import APIRouter

from knowlebase.resource.document.api import router as document_router
from knowlebase.resource.version.api import router as version_router
from knowlebase.resource.relation.api import router as relation_router

resource_router = APIRouter()

resource_router.include_router(document_router, prefix="/document", tags=["业务资源域-文档管理"])
resource_router.include_router(version_router, prefix="/version", tags=["业务资源域-版本管理"])
resource_router.include_router(relation_router, prefix="/relation", tags=["业务资源域-关联查询"])

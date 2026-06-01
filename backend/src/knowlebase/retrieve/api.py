"""
检索域 — API 端点

POST /retrieval       — 检索 API
POST /retrieval/debug — 检索调试
GET  /retrieval/versions — 可用版本列表
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.db.session import get_db
from knowlebase.models.knowledge_base_version import KnowledgeBaseVersion
from knowlebase.retrieve.schema import (
    SearchRequest,
    DebugSearchRequest,
    DebugSearchResponse,
    VersionOption,
    ChunkTextItem,
    RetrievalErrorCode,
)
from knowlebase.schemas.errors import BusinessError, UnifiedResponse
from knowlebase.retrieve.service import get_search_service, SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", summary="检索 API", description="基于已启用版本执行混合多路检索", tags=["检索域"])
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
):
    response = UnifiedResponse()
    try:
        result = await db.execute(
            select(KnowledgeBaseVersion).where(
                KnowledgeBaseVersion.status == "enabled"
            ).limit(1)
        )
        version = result.scalar_one_or_none()
        if not version:
            raise BusinessError(RetrievalErrorCode.RETRIEVAL_NO_ENABLED_VERSION)

        top_n = request.top_n or settings.search_results_limit

        search_result = await search_service.search(
            db=db, query=request.query, version_id=version.id,
            top_n=top_n, debug=False,
        )

        items = [
            ChunkTextItem(chunk_text=item.chunk_text)
            for item in search_result.reranked_results
        ]
        response.ok({"results": [i.model_dump() for i in items]})

    except BusinessError as e:
        response.error(e)
    except Exception as e:
        logger.error(f"检索失败: {e}", exc_info=True)
        response.error(BusinessError(RetrievalErrorCode.RETRIEVAL_INTERNAL_ERROR, str(e)))

    return response.to_json()


@router.post(
    "/debug", summary="检索调试",
    description="指定知识库版本，查看混合多路检索的完整中间结果",
    tags=["检索域"],
)
async def debug_search(
    request: DebugSearchRequest,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
):
    response = UnifiedResponse()
    try:
        result = await db.execute(
            select(KnowledgeBaseVersion).where(
                KnowledgeBaseVersion.id == request.version_id
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            raise BusinessError(RetrievalErrorCode.RETRIEVAL_VERSION_NOT_FOUND)
        if version.status not in ("succeeded", "enabled", "disabled"):
            raise BusinessError(RetrievalErrorCode.RETRIEVAL_VERSION_NOT_BUILT)

        top_n = request.top_n or settings.search_results_limit

        search_result = await search_service.search(
            db=db, query=request.query, version_id=version.id,
            top_n=top_n, debug=True,
        )

        response.ok(DebugSearchResponse(
            es_results=search_result.es_results,
            milvus_results=search_result.milvus_results,
            neo4j_results=search_result.neo4j_results,
            merged_results=search_result.merged_results,
            reranked_results=search_result.reranked_results,
        ).model_dump())

    except BusinessError as e:
        response.error(e)
    except Exception as e:
        logger.error(f"检索调试失败: {e}", exc_info=True)
        response.error(BusinessError(RetrievalErrorCode.RETRIEVAL_INTERNAL_ERROR, str(e)))

    return response.to_json()


@router.get(
    "/versions", summary="可用版本列表",
    description="返回已构建完成的知识库版本列表，供检索调试页面版本下拉框使用",
    tags=["检索域"],
)
async def get_versions(db: AsyncSession = Depends(get_db)):
    response = UnifiedResponse()
    try:
        result = await db.execute(
            select(KnowledgeBaseVersion)
            .where(
                KnowledgeBaseVersion.status.in_(
                    ["succeeded", "enabled", "disabled", "failed"]
                )
            )
            .order_by(KnowledgeBaseVersion.version_code.desc())
        )
        versions = result.scalars().all()

        response.ok({
            "versions": [
                VersionOption(
                    id=v.id,
                    version_name=v.version_name,
                    version_code=v.version_code,
                    status=v.status,
                    is_built=v.status != "failed",
                ).model_dump()
                for v in versions
            ]
        })

    except BusinessError as e:
        response.error(e)
    except Exception as e:
        logger.error(f"获取版本列表失败: {e}", exc_info=True)
        response.error(BusinessError(RetrievalErrorCode.RETRIEVAL_INTERNAL_ERROR, str(e)))

    return response.to_json()

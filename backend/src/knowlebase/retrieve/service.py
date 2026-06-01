"""
检索域 — SearchService 检索编排器

编排多路召回 → 合并去重 → 补全信息 → 重排序全流程。
"""

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowlebase.core.config import settings
from knowlebase.core.llm_client import create_chat_model, SCENE_ENTITY_EXTRACT
from knowlebase.models.chunk import DocumentChunk
from knowlebase.models.document import Document as DocumentModel
from knowlebase.models.document_version_relation import DocumentVersionRelation
from knowlebase.services.es_service import get_es_service
from knowlebase.services.milvus_service import get_milvus_service
from knowlebase.services.neo4j_service import get_neo4j_service
from knowlebase.services.embedding_service import get_embedding_service
from knowlebase.retrieve.schema import SearchResultItem
from knowlebase.retrieve.strategy import get_merge_strategy, get_rerank_strategy

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """检索中间结果"""
    es_results: list[SearchResultItem] = field(default_factory=list)
    milvus_results: list[SearchResultItem] = field(default_factory=list)
    neo4j_results: list[SearchResultItem] = field(default_factory=list)
    merged_results: list[SearchResultItem] = field(default_factory=list)
    reranked_results: list[SearchResultItem] = field(default_factory=list)


class SearchService:
    """检索服务 — 编排多路召回与融合重排序全流程"""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        version_id: int,
        top_n: int,
        debug: bool = False,
    ) -> SearchResult:
        """执行完整检索流水线

        Args:
            db: 数据库会话
            query: 检索查询文本
            version_id: 知识库版本 ID
            top_n: 最终返回条数
            debug: 是否保留各阶段中间结果
        """
        result = SearchResult()

        # 权重归一化
        raw_weights = [
            settings.search_keyword_weight,
            settings.search_semantic_weight,
            settings.search_graph_weight,
        ]
        total = sum(raw_weights)
        weights = [w / total for w in raw_weights]

        recall_size = int(top_n * settings.search_recall_ratio)

        # 并行召回
        tasks = []
        if raw_weights[0] > 0:
            tasks.append(self._recall_es(query, version_id, recall_size))
        else:
            tasks.append(self._noop([]))
        if raw_weights[1] > 0:
            tasks.append(self._recall_milvus(query, version_id, recall_size))
        else:
            tasks.append(self._noop([]))
        if raw_weights[2] > 0:
            tasks.append(self._recall_neo4j(query, version_id, recall_size))
        else:
            tasks.append(self._noop([]))

        es_raw, milvus_raw, neo4j_raw = await asyncio.gather(*tasks)

        # 填充各路径原始结果
        if debug:
            result.es_results = await self._fill_metadata(db, version_id, es_raw)
            result.milvus_results = await self._fill_metadata(db, version_id, milvus_raw)
            result.neo4j_results = await self._fill_metadata(db, version_id, neo4j_raw)

        # 合并去重
        merge_strategy = get_merge_strategy()
        merged = merge_strategy.merge([es_raw, milvus_raw, neo4j_raw], weights)
        merge_size = int(top_n * settings.search_merge_ratio)
        merged_candidates = merged[:merge_size]

        # 补全信息
        filled = await self._fill_metadata(db, version_id, merged_candidates)
        if debug:
            result.merged_results = filled

        # 重排序
        rerank_strategy = get_rerank_strategy()
        reranked = rerank_strategy.rerank(filled, query, top_n)
        result.reranked_results = reranked

        # debug 模式下的阶段结果：ES/Milvus/Neo4j 返回完整 recall_size 条
        # 非 debug 模式只保留最终结果
        return result

    # ---- 并行召回 ----

    async def _recall_es(self, query: str, version_id: int, size: int) -> list[tuple[str, float]]:
        """ES 全文检索"""
        try:
            es_svc = get_es_service()
            hits = await es_svc.search(query, size, version_id=str(version_id))
            return [(h["chunk_id"], h["score"]) for h in hits]
        except Exception as e:
            logger.error(f"ES 检索失败: {e}", exc_info=True)
            return []

    async def _recall_milvus(self, query: str, version_id: int, size: int) -> list[tuple[str, float]]:
        """Milvus 语义检索"""
        try:
            embedding_svc = get_embedding_service()
            query_vector = embedding_svc.encode_single(query)
            milvus_svc = get_milvus_service()
            hits = milvus_svc.search(query_vector, size, version_id=str(version_id))
            return [(h["chunk_id"], h["score"]) for h in hits]
        except Exception as e:
            logger.error(f"Milvus 检索失败: {e}", exc_info=True)
            return []

    async def _recall_neo4j(self, query: str, version_id: int, size: int) -> list[tuple[str, float]]:
        """Neo4j 图谱检索：LLM 抽取实体 → 图谱搜索"""
        try:
            entities = await self._extract_entities(query)
            if not entities:
                return []
            neo4j_svc = get_neo4j_service()
            hits = await neo4j_svc.search_entities(entities, size)
            return [(h["chunk_id"], h["score"]) for h in hits]
        except Exception as e:
            logger.error(f"Neo4j 检索失败: {e}", exc_info=True)
            return []

    async def _extract_entities(self, query: str) -> list[str]:
        """通过 LLM 从查询文本抽取实体名称列表"""
        try:
            chat_model = create_chat_model(SCENE_ENTITY_EXTRACT, temperature=0)
            prompt = (
                "从以下查询文本中抽取关键实体（人名、地名、组织、产品、技术术语等），"
                "仅返回实体名称列表，每行一个，最多 10 个。不要返回编号或其他内容。\n\n"
                f"查询：{query}"
            )
            response = chat_model.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            content = str(content).strip()
            entities = [line.strip() for line in content.split("\n") if line.strip()]
            return entities[:10]
        except Exception as e:
            logger.warning(f"实体抽取失败: {e}")
            return []

    # ---- 补全信息 ----

    async def _fill_metadata(
        self,
        db: AsyncSession,
        version_id: int,
        candidates: list[tuple[str, float]],
    ) -> list[SearchResultItem]:
        """根据 chunk_id 列表从 PostgreSQL 补全分块文本、文档名称、页码、章节"""
        if not candidates:
            return []

        # 维护分数映射和原始顺序
        score_map = {chunk_id: score for chunk_id, score in candidates}
        chunk_ids = [c[0] for c in candidates]

        result = await db.execute(
            select(
                DocumentChunk.id,
                DocumentChunk.processed_text,
                DocumentChunk.page_range_start,
                DocumentChunk.section_title,
                DocumentModel.file_name,
            )
            .join(DocumentModel, DocumentChunk.document_id == DocumentModel.id)
            .join(
                DocumentVersionRelation,
                DocumentChunk.document_id == DocumentVersionRelation.document_id,
            )
            .where(
                DocumentChunk.id.in_(chunk_ids),
                DocumentVersionRelation.version_id == version_id,
                DocumentVersionRelation.stored == True,
                DocumentChunk.enabled == True,
            )
        )
        rows = result.all()

        items = []
        for row in rows:
            chunk_id = str(row[0])
            items.append(SearchResultItem(
                chunk_text=row[1] or "",
                document_name=row[4] or "未知文档",
                page_number=row[2] or 0,
                chapter_title=row[3] or "",
                score=score_map.get(chunk_id, 0.0),
            ))

        # 按原始合并分数降序排列
        items.sort(key=lambda x: x.score, reverse=True)
        return items

    @staticmethod
    async def _noop(value):
        return value


# 模块级单例
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service

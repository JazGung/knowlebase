"""
Neo4jService — 知识图谱服务

负责图谱节点/关系的写入和按文档清理。
节点跨文档共享，关系按 document_id + chunk_id 区分。
"""

import logging
import re
from typing import List, Dict

from neo4j import AsyncGraphDatabase, AsyncDriver

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)


def _legalize_predicate(predicate: str) -> str:
    """将三元组 predicate 转换为合法的 Neo4j 关系类型：去除空格，特殊字符替换为 _"""
    return re.sub(r"[^\w]", "_", predicate.replace(" ", ""))


class Neo4jService:
    """Neo4j 图谱服务 — 管理 Document/Entity 节点和 CONTAINS/{predicate} 关系"""

    def __init__(self):
        self._driver: AsyncDriver | None = None

    @property
    def driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_url,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            logger.info(f"Neo4j 驱动已创建: {settings.neo4j_url}")
        return self._driver

    async def write_graph(self, document_id: str, relations: List[Dict]) -> None:
        """对每个三元组，执行 MERGE + CONTAINS + {predicate} 关系创建

        Args:
            document_id: 文档ID（字符串形式）
            relations: [{"source": str, "relationship": str, "target": str, "chunk_id": str}, ...]
        """
        if not relations:
            return

        async with self.driver.session() as session:
            for rel in relations:
                source = rel["source"]
                target = rel["target"]
                predicate = _legalize_predicate(rel["relationship"])
                chunk_id = str(rel.get("chunk_id", ""))

                await session.run(
                    f"""
                    MERGE (d:Document {{document_id: $document_id}})
                    MERGE (s:Entity {{name: $source}})
                    MERGE (o:Entity {{name: $target}})
                    MERGE (d)-[:CONTAINS]->(s)
                    MERGE (d)-[:CONTAINS]->(o)
                    MERGE (s)-[:`{predicate}` {{document_id: $document_id, chunk_id: $chunk_id}}]->(o)
                    """,
                    document_id=document_id,
                    source=source,
                    target=target,
                    chunk_id=chunk_id,
                )
        logger.debug(f"Neo4j 图谱写入成功: document_id={document_id}, relations={len(relations)}")

    async def delete_by_document_id(self, document_id: str) -> None:
        """按文档ID清理图谱数据（DEG 4.10.10 步骤 1 的 Neo4j 部分）

        a) 删除 CONTAINS 关系
        b) 删除 document_id 匹配的 {predicate} 关系
        c) 删除 Document 节点
        d) 删除无 CONTAINS 引用的孤儿 Entity
        """
        async with self.driver.session() as session:
            # a) 删除 CONTAINS
            await session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[r:CONTAINS]->(:Entity)
                DELETE r
                """,
                document_id=document_id,
            )
            # b) 删除所有 document_id 匹配的关系（任意类型）
            result = await session.run(
                """
                MATCH ()-[r]->()
                WHERE r.document_id = $document_id
                DELETE r
                RETURN count(r) as deleted_count
                """,
                document_id=document_id,
            )
            record = await result.single()
            logger.debug(f"Neo4j predicate 关系删除: {record['deleted_count'] if record else 0} 条")
            # c) 删除 Document 节点
            await session.run(
                """
                MATCH (d:Document {document_id: $document_id})
                DELETE d
                """,
                document_id=document_id,
            )
            # d) 删除孤儿 Entity
            await session.run(
                """
                MATCH (e:Entity)
                WHERE NOT (e)<-[:CONTAINS]-()
                DELETE e
                """,
            )
        logger.debug(f"Neo4j 清理完成: document_id={document_id}")

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None


_neo4j_service: Neo4jService | None = None


def get_neo4j_service() -> Neo4jService:
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
    return _neo4j_service

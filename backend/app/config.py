"""
配置管理系统

支持多环境配置：
1. 优先读取 backend/.env（本地开发）
2. 然后读取环境变量（容器环境）
3. 最后使用默认值

本地开发时使用 backend/.env（指向 localhost）
容器环境使用 docker-compose.yml 传递的环境变量
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, AnyUrl


class Settings(BaseSettings):
    """
    应用配置类

    配置读取优先级（从高到低）：
    1. backend/.env 文件（本地开发）
    2. 系统环境变量
    3. 默认值
    """

    # ====================
    # 数据库配置
    # ====================

    # PostgreSQL
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_user: str = Field(default="knowlebase", env="POSTGRES_USER")
    postgres_password: str = Field(default="knowlebase_password", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="knowlebase", env="POSTGRES_DB")

    @property
    def database_url(self) -> str:
        """构建 PostgreSQL 连接 URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # ElasticSearch
    elasticsearch_host: str = Field(default="localhost", env="ELASTICSEARCH_HOST")
    elasticsearch_port: int = Field(default=9200, env="ELASTICSEARCH_PORT")
    elasticsearch_username: Optional[str] = Field(default=None, env="ELASTICSEARCH_USERNAME")
    elasticsearch_password: Optional[str] = Field(default=None, env="ELASTICSEARCH_PASSWORD")

    @property
    def elasticsearch_url(self) -> str:
        """构建 ElasticSearch 连接 URL"""
        return f"http://{self.elasticsearch_host}:{self.elasticsearch_port}"

    # Milvus
    milvus_host: str = Field(default="localhost", env="MILVUS_HOST")
    milvus_port: int = Field(default=19530, env="MILVUS_PORT")

    @property
    def milvus_uri(self) -> str:
        """构建 Milvus 连接 URI"""
        return f"{self.milvus_host}:{self.milvus_port}"

    # Neo4j
    neo4j_host: str = Field(default="localhost", env="NEO4J_HOST")
    neo4j_port: int = Field(default=7687, env="NEO4J_PORT")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER")
    neo4j_password: str = Field(default="knowlebase_password", env="NEO4J_PASSWORD")

    @property
    def neo4j_url(self) -> str:
        """构建 Neo4j 连接 URL"""
        return f"bolt://{self.neo4j_host}:{self.neo4j_port}"

    # ====================
    # 应用程序配置
    # ====================

    # FastAPI
    backend_host: str = Field(default="0.0.0.0", env="BACKEND_HOST")
    backend_port: int = Field(default=8000, env="BACKEND_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")

    # 向量嵌入
    embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=512, env="EMBEDDING_DIMENSION")
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")

    # 文档处理
    chunk_size: int = Field(default=500, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="CHUNK_OVERLAP")
    max_file_size: int = Field(default=104857600, env="MAX_FILE_SIZE")  # 100MB

    # 搜索配置
    search_keyword_weight: float = Field(default=0.4, env="SEARCH_KEYWORD_WEIGHT")
    search_semantic_weight: float = Field(default=0.4, env="SEARCH_SEMANTIC_WEIGHT")
    search_graph_weight: float = Field(default=0.2, env="SEARCH_GRAPH_WEIGHT")
    search_results_limit: int = Field(default=20, env="SEARCH_RESULTS_LIMIT")

    # 开发环境标志
    development_mode: bool = Field(default=False, env="DEVELOPMENT_MODE")
    docker_container: bool = Field(default=False, env="DOCKER_CONTAINER")

    # ====================
    # 配置类设置
    # ====================

    class Config:
        # 优先读取 backend/.env（如果存在）
        env_file = Path(__file__).parent.parent / ".env"
        env_file_encoding = "utf-8"

        # 允许环境变量覆盖
        case_sensitive = False

        # 支持 .env 文件中的嵌套配置
        env_nested_delimiter = "__"

    def is_local_development(self) -> bool:
        """判断是否为本地开发环境"""
        return self.development_mode or not self.docker_container

    def get_database_config_summary(self) -> dict:
        """获取数据库配置摘要（不包含密码）"""
        return {
            "postgres": f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
            "elasticsearch": f"{self.elasticsearch_host}:{self.elasticsearch_port}",
            "milvus": f"{self.milvus_host}:{self.milvus_port}",
            "neo4j": f"{self.neo4j_host}:{self.neo4j_port}",
            "development_mode": self.is_local_development(),
            "docker_container": self.docker_container,
        }


# 全局配置实例
settings = Settings()


if __name__ == "__main__":
    # 测试配置加载
    print("配置加载测试:")
    print(f"PostgreSQL URL: {settings.database_url}")
    print(f"ElasticSearch URL: {settings.elasticsearch_url}")
    print(f"Milvus URI: {settings.milvus_uri}")
    print(f"Neo4j URL: {settings.neo4j_url}")
    print(f"开发模式: {settings.is_local_development()}")
    print(f"配置来源: {'backend/.env' if Path(__file__).parent.parent.joinpath('.env').exists() else '环境变量'}")
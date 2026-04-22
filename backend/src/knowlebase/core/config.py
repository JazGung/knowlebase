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
import math
import logging
from pathlib import Path
from typing import Optional, Union
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, AnyUrl

logger = logging.getLogger(__name__)


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
    neo4j_raw_url: Optional[str] = Field(default=None, env="NEO4J_URL")  # 可选，优先使用 .env 中的配置

    @property
    def neo4j_url(self) -> str:
        """构建 Neo4j 连接 URL"""
        if self.neo4j_raw_url:
            return self.neo4j_raw_url
        return f"bolt://{self.neo4j_host}:{self.neo4j_port}"

    # ====================
    # Minio对象存储配置
    # ====================

    # Minio连接配置
    minio_endpoint: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE")  # 是否使用HTTPS
    minio_region: Optional[str] = Field(default=None, env="MINIO_REGION")

    # Minio存储桶配置
    minio_document_bucket: str = Field(default="knowlebase-documents", env="MINIO_DOCUMENT_BUCKET")
    minio_temp_bucket: str = Field(default="knowlebase-temp", env="MINIO_TEMP_BUCKET")

    @property
    def minio_endpoint_url(self) -> str:
        """构建Minio端点URL"""
        protocol = "https" if self.minio_secure else "http"
        return f"{protocol}://{self.minio_endpoint}"

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
    # LLM 模型配置
    # ====================

    # 默认 LLM 配置（MODEL 和 API_KEY 必须有值）
    default_llm_model: str = Field(default="gpt-4o-mini", env="DEFAULT_LLM_MODEL")
    default_llm_api_key: str = Field(default="", env="DEFAULT_LLM_API_KEY")
    default_llm_api_base: str = Field(default="https://api.openai.com/v1", env="DEFAULT_LLM_API_BASE")

    # 分块模型（One-Pass：分块+指代消解+HyDE+图谱三元组）
    chunking_model: str = Field(default="", env="CHUNKING_MODEL")
    chunking_api_key: str = Field(default="", env="CHUNKING_API_KEY")
    chunking_api_base: str = Field(default="", env="CHUNKING_API_BASE")

    # 图片描述模型（视觉模型，用于生成图片文字说明）
    image_describer_model: str = Field(default="", env="IMAGE_DESCRIBER_MODEL")
    image_describer_api_key: str = Field(default="", env="IMAGE_DESCRIBER_API_KEY")
    image_describer_api_base: str = Field(default="", env="IMAGE_DESCRIBER_API_BASE")

    # ====================
    # 分块参数配置
    # ====================

    chunk_max_chars: Union[int, float, str] = Field(default=800, env="CHUNK_MAX_CHARS")
    chunk_min_chars: Union[int, float, str] = Field(default=0.5, env="CHUNK_MIN_CHARS")
    chunk_overlap: Union[int, float, str] = Field(default=0.1, env="CHUNK_OVERLAP")
    chunk_window: Union[int, float, str] = Field(default=1.5, env="CHUNK_WINDOW")

    # ====================
    # 配置类设置
    # ====================

    class Config:
        # 优先读取 backend/.env（如果存在）
        env_file = Path(__file__).parent.parent.parent / ".env"
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
            "minio": f"{self.minio_endpoint}/{self.minio_document_bucket}",
            "development_mode": self.is_local_development(),
            "docker_container": self.docker_container,
        }

    # ====================
    # LLM 配置解析
    # ====================

    def _resolve_llm_config(self, model: str, api_key: str, api_base: str) -> dict:
        """解析 LLM 配置

        规则：
        - MODEL/API_KEY 为空 → 回退到 DEFAULT_LLM_*，仍为空则报错
        - API_BASE 为空 → 不回退（LangChain 使用自身默认值）
        """
        resolved_model = model or self.default_llm_model
        resolved_api_key = api_key or self.default_llm_api_key
        resolved_api_base = api_base  # 空值直接传给 LangChain

        if not resolved_model:
            raise ValueError(
                "LLM 模型未配置。请设置 DEFAULT_LLM_MODEL 或具体模块的 *_MODEL 环境变量。"
            )
        if not resolved_api_key:
            raise ValueError(
                f"LLM API Key 未配置（model={resolved_model}）。"
                "请设置 DEFAULT_LLM_API_KEY 或具体模块的 *_API_KEY 环境变量。"
            )

        return {
            "model": resolved_model,
            "api_key": resolved_api_key,
            "api_base": resolved_api_base,
        }

    def get_chunking_llm_config(self) -> dict:
        """获取分块 LLM 配置"""
        return self._resolve_llm_config(
            self.chunking_model,
            self.chunking_api_key,
            self.chunking_api_base,
        )

    def get_image_describer_llm_config(self) -> dict:
        """获取图片描述 LLM 配置"""
        return self._resolve_llm_config(
            self.image_describer_model,
            self.image_describer_api_key,
            self.image_describer_api_base,
        )

    def log_llm_config_summary(self) -> None:
        """打印 LLM 配置摘要（隐藏 API Key 中间字符）"""
        def mask_key(key: str) -> str:
            if len(key) <= 8:
                return "***"
            return key[:4] + "..." + key[-4:]

        for name, getter in [("分块", self.get_chunking_llm_config),
                             ("图片描述", self.get_image_describer_llm_config)]:
            cfg = getter()
            logger.info(
                f"LLM 配置 ({name}): "
                f"model={cfg['model']}, "
                f"api_key={mask_key(cfg['api_key'])}, "
                f"api_base={cfg['api_base'] or '(LangChain 默认)'}"
            )

    # ====================
    # 分块参数解析
    # ====================

    @staticmethod
    def _resolve_param(value, base: int, range_lo: float, range_hi: float) -> int:
        """解析分块参数

        Args:
            value: 配置值
            base: 基准值（max_chars）
            range_lo: 比例范围下限
            range_hi: 比例范围上限
                - 在 (range_lo, range_hi) 内 → value * base
                - 否则 → value（绝对值）
        """
        try:
            value = float(value)
        except (ValueError, TypeError):
            value = 0

        if range_lo < value < range_hi:
            return math.floor(value * base)
        return math.floor(value)

    def get_chunk_params(self) -> dict:
        """解析并返回分块参数"""
        max_chars = self._resolve_param(self.chunk_max_chars, 800, 0, 0) or 800
        if max_chars <= 0:
            max_chars = 800

        min_chars = self._resolve_param(self.chunk_min_chars, max_chars, 0, 1)
        if min_chars <= 0:
            min_chars = 1

        overlap = self._resolve_param(self.chunk_overlap, max_chars, 0, 1)
        if overlap <= 0:
            overlap = 1

        window = self._resolve_param(self.chunk_window, max_chars, 1, 5)
        if window <= 0:
            window = max_chars

        cfg = {
            "max_chars": max_chars,
            "min_chars": min_chars,
            "overlap": overlap,
            "window": window,
        }
        logger.info(
            f"分块参数: max_chars={max_chars}, min_chars={min_chars}, "
            f"overlap={overlap}, window={window}"
        )
        return cfg


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
"""
单元测试 - 配置模块
"""

import os
import pytest
from unittest.mock import patch
from pathlib import Path

from knowlebase.core.config import Settings


def create_test_settings(**overrides) -> Settings:
    """创建测试用的 Settings 实例，绕过 .env 文件"""
    # 构建一个不含 .env 的配置路径
    merged_env = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_pass",
        "POSTGRES_DB": "test_db",
        "ELASTICSEARCH_HOST": "localhost",
        "ELASTICSEARCH_PORT": "9200",
        "MILVUS_HOST": "localhost",
        "MILVUS_PORT": "19530",
        "NEO4J_HOST": "localhost",
        "NEO4J_PORT": "7687",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "test_key",
        "MINIO_SECRET_KEY": "test_secret",
    }
    # 应用覆盖
    for k, v in overrides.items():
        merged_env[k] = str(v)

    with patch.dict(os.environ, merged_env, clear=False):
        # 使用 _env_file=None 跳过 .env 读取
        return Settings(_env_file=None)


class TestSettingsDefaults:
    """测试默认值"""

    def test_postgres_defaults(self):
        s = create_test_settings()
        assert s.postgres_host == "localhost"
        assert s.postgres_port == 5432
        assert s.postgres_user == "test_user"

    def test_minio_defaults(self):
        s = create_test_settings()
        assert s.minio_document_bucket == "knowlebase-documents"
        assert s.minio_temp_bucket == "knowlebase-temp"
        assert s.minio_secure is False


class TestSettingsComputedProperties:
    """测试计算属性（@property）"""

    def test_database_url(self):
        s = create_test_settings()
        assert s.database_url == "postgresql://test_user:test_pass@localhost:5432/test_db"

    def test_elasticsearch_url(self):
        s = create_test_settings(ELASTICSEARCH_HOST="es.example.com", ELASTICSEARCH_PORT="9201")
        assert s.elasticsearch_url == "http://es.example.com:9201"

    def test_milvus_uri(self):
        s = create_test_settings(MILVUS_HOST="milvus.example.com", MILVUS_PORT="19531")
        assert s.milvus_uri == "milvus.example.com:19531"

    def test_neo4j_url_from_host_port(self):
        s = create_test_settings(NEO4J_HOST="neo.example.com", NEO4J_PORT="7688")
        assert s.neo4j_url == "bolt://neo.example.com:7688"

    def test_neo4j_url_from_raw_url(self):
        s = create_test_settings(NEO4J_RAW_URL="bolt://custom:9999")
        assert s.neo4j_url == "bolt://custom:9999"

    def test_minio_endpoint_url_http(self):
        s = create_test_settings(MINIO_SECURE=False)
        assert s.minio_endpoint_url == "http://localhost:9000"

    def test_minio_endpoint_url_https(self):
        s = create_test_settings(MINIO_SECURE=True)
        assert s.minio_endpoint_url == "https://localhost:9000"


class TestSettingsHelpers:
    """测试辅助方法"""

    def test_is_local_development_default(self):
        s = create_test_settings()
        assert s.is_local_development() is True

    def test_is_local_development_docker(self):
        s = create_test_settings(DOCKER_CONTAINER=True)
        assert s.is_local_development() is False

    def test_is_local_development_explicit(self):
        s = create_test_settings(DEVELOPMENT_MODE=True)
        assert s.is_local_development() is True

    def test_get_database_config_summary(self):
        s = create_test_settings()
        summary = s.get_database_config_summary()
        assert summary["postgres"] == "localhost:5432/test_db"
        assert summary["elasticsearch"] == "localhost:9200"
        assert summary["milvus"] == "localhost:19530"
        assert summary["neo4j"] == "localhost:7687"
        assert summary["minio"] == "localhost:9000/knowlebase-documents"
        # 确保不包含密码
        assert "test_pass" not in str(summary)

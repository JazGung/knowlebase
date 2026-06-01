"""
检索域单元测试

覆盖：策略（合并/重排序）、Schema 校验、配置校验、SearchService。
"""

import sys
import os
import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_backend_dir, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# ==================== 合并策略 ====================

class TestRRFMergeStrategy:
    def test_basic_merge(self):
        from knowlebase.retrieve.strategy import RRFMergeStrategy
        strategy = RRFMergeStrategy()
        es = [("c1", 0.9), ("c2", 0.8)]
        milvus = [("c2", 0.95), ("c3", 0.7)]
        neo4j = [("c3", 0.85)]
        result = strategy.merge([es, milvus, neo4j], [0.4, 0.4, 0.2])
        assert len(result) >= 1
        # 去重：c2 出现在两路中，只保留最高分
        chunk_ids = [c[0] for c in result]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_weight_zero_skip(self):
        from knowlebase.retrieve.strategy import RRFMergeStrategy
        strategy = RRFMergeStrategy()
        es = [("c1", 0.9), ("c2", 0.8)]
        result = strategy.merge([es, [], []], [1.0, 0.0, 0.0])
        assert len(result) == 2
        assert result[0][0] == "c1"

    def test_empty_all(self):
        from knowlebase.retrieve.strategy import RRFMergeStrategy
        strategy = RRFMergeStrategy()
        result = strategy.merge([[], [], []], [0.4, 0.4, 0.2])
        assert result == []


class TestWeightedNormalizationMergeStrategy:
    def test_basic_merge(self):
        from knowlebase.retrieve.strategy import WeightedNormalizationMergeStrategy
        strategy = WeightedNormalizationMergeStrategy()
        es = [("c1", 0.9), ("c2", 0.5)]
        milvus = [("c1", 0.8), ("c3", 0.6)]
        result = strategy.merge([es, milvus, []], [0.5, 0.5, 0.0])
        assert len(result) >= 1
        chunk_ids = [c[0] for c in result]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_single_path(self):
        from knowlebase.retrieve.strategy import WeightedNormalizationMergeStrategy
        strategy = WeightedNormalizationMergeStrategy()
        es = [("c1", 0.9), ("c2", 0.5)]
        result = strategy.merge([es, [], []], [1.0, 0.0, 0.0])
        assert len(result) == 2
        # 单路归一化：唯一值归一化后保持排序
        assert result[0][0] == "c1"


class TestGetMergeStrategy:
    def test_rrf(self, monkeypatch):
        monkeypatch.setattr("knowlebase.retrieve.strategy.settings.search_merge_strategy", "rrf")
        from knowlebase.retrieve.strategy import get_merge_strategy, RRFMergeStrategy
        s = get_merge_strategy()
        assert isinstance(s, RRFMergeStrategy)

    def test_weighted_normalization(self, monkeypatch):
        monkeypatch.setattr(
            "knowlebase.retrieve.strategy.settings.search_merge_strategy",
            "weighted_normalization",
        )
        from knowlebase.retrieve.strategy import get_merge_strategy, WeightedNormalizationMergeStrategy
        s = get_merge_strategy()
        assert isinstance(s, WeightedNormalizationMergeStrategy)

    def test_invalid_strategy_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.retrieve.strategy.settings.search_merge_strategy", "invalid")
        from knowlebase.retrieve.strategy import get_merge_strategy
        with pytest.raises(ValueError):
            get_merge_strategy()


# ==================== 重排序策略 ====================

class TestNoopRerankStrategy:
    def test_returns_top_k(self):
        from knowlebase.retrieve.strategy import NoopRerankStrategy
        from knowlebase.retrieve.schema import SearchResultItem
        strategy = NoopRerankStrategy()
        items = [
            SearchResultItem(chunk_text=f"text{i}", document_name="doc",
                             page_number=1, chapter_title="ch", score=1.0 - i * 0.1)
            for i in range(10)
        ]
        result = strategy.rerank(items, "query", 5)
        assert len(result) == 5
        assert result == items[:5]


class TestGetRerankStrategy:
    def test_none(self, monkeypatch):
        monkeypatch.setattr("knowlebase.retrieve.strategy.settings.search_rerank_strategy", "none")
        from knowlebase.retrieve.strategy import get_rerank_strategy, NoopRerankStrategy
        s = get_rerank_strategy()
        assert isinstance(s, NoopRerankStrategy)

    def test_invalid_strategy_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.retrieve.strategy.settings.search_rerank_strategy", "invalid")
        from knowlebase.retrieve.strategy import get_rerank_strategy
        with pytest.raises(ValueError):
            get_rerank_strategy()


# ==================== Schema ====================

class TestSearchRequestSchema:
    def test_valid_minimal(self):
        from knowlebase.retrieve.schema import SearchRequest
        req = SearchRequest(query="test")
        assert req.query == "test"
        assert req.top_n is None

    def test_valid_full(self):
        from knowlebase.retrieve.schema import SearchRequest
        req = SearchRequest(query="test", top_n=10)
        assert req.top_n == 10

    def test_empty_query_fails(self):
        from knowlebase.retrieve.schema import SearchRequest
        with pytest.raises(ValueError):
            SearchRequest(query="")

    def test_query_too_long_fails(self):
        from knowlebase.retrieve.schema import SearchRequest
        with pytest.raises(ValueError):
            SearchRequest(query="x" * 2001)

    def test_top_n_zero_fails(self):
        from knowlebase.retrieve.schema import SearchRequest
        with pytest.raises(ValueError):
            SearchRequest(query="test", top_n=0)


class TestDebugSearchRequestSchema:
    def test_valid(self):
        from knowlebase.retrieve.schema import DebugSearchRequest
        req = DebugSearchRequest(query="test", version_id=1)
        assert req.version_id == 1

    def test_missing_version_id_fails(self):
        from knowlebase.retrieve.schema import DebugSearchRequest
        with pytest.raises(ValueError):
            DebugSearchRequest(query="test")


class TestSearchResultItem:
    def test_create(self):
        from knowlebase.retrieve.schema import SearchResultItem
        item = SearchResultItem(
            chunk_text="text", document_name="doc",
            page_number=1, chapter_title="ch", score=0.95,
        )
        d = item.model_dump()
        assert d["chunk_text"] == "text"
        assert d["document_name"] == "doc"
        assert d["page_number"] == 1
        assert d["chapter_title"] == "ch"
        assert d["score"] == 0.95


# ==================== 配置校验 ====================

class TestSearchConfigValidation:
    def test_valid_defaults(self, monkeypatch):
        monkeypatch.setattr("knowlebase.core.config.settings.search_keyword_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_semantic_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_graph_weight", 0.2)
        monkeypatch.setattr("knowlebase.core.config.settings.search_recall_ratio", 3.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_ratio", 2.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_strategy", "rrf")
        monkeypatch.setattr("knowlebase.core.config.settings.search_rerank_strategy", "cross_encoder")
        from knowlebase.core.config import settings
        settings.validate_search_config()

    def test_all_zero_weights_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.core.config.settings.search_keyword_weight", 0.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_semantic_weight", 0.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_graph_weight", 0.0)
        from knowlebase.core.config import settings
        with pytest.raises(ValueError, match="全部为 0"):
            settings.validate_search_config()

    def test_negative_weight_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.core.config.settings.search_keyword_weight", -0.1)
        monkeypatch.setattr("knowlebase.core.config.settings.search_semantic_weight", 0.5)
        monkeypatch.setattr("knowlebase.core.config.settings.search_graph_weight", 0.5)
        from knowlebase.core.config import settings
        with pytest.raises(ValueError, match="负值"):
            settings.validate_search_config()

    def test_recall_ratio_below_1_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.core.config.settings.search_keyword_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_semantic_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_graph_weight", 0.2)
        monkeypatch.setattr("knowlebase.core.config.settings.search_recall_ratio", 0.5)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_ratio", 2.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_strategy", "rrf")
        monkeypatch.setattr("knowlebase.core.config.settings.search_rerank_strategy", "cross_encoder")
        from knowlebase.core.config import settings
        with pytest.raises(ValueError, match="SEARCH_RECALL_RATIO"):
            settings.validate_search_config()

    def test_invalid_merge_strategy_raises(self, monkeypatch):
        monkeypatch.setattr("knowlebase.core.config.settings.search_keyword_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_semantic_weight", 0.4)
        monkeypatch.setattr("knowlebase.core.config.settings.search_graph_weight", 0.2)
        monkeypatch.setattr("knowlebase.core.config.settings.search_recall_ratio", 3.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_ratio", 2.0)
        monkeypatch.setattr("knowlebase.core.config.settings.search_merge_strategy", "bad")
        monkeypatch.setattr("knowlebase.core.config.settings.search_rerank_strategy", "cross_encoder")
        from knowlebase.core.config import settings
        with pytest.raises(ValueError, match="SEARCH_MERGE_STRATEGY"):
            settings.validate_search_config()


# ==================== 导入测试 ====================

def test_retrieve_imports():
    modules = [
        ("knowlebase.retrieve", "retrieve_router"),
        ("knowlebase.retrieve.api", "router"),
        ("knowlebase.retrieve.service", "SearchService"),
        ("knowlebase.retrieve.schema", "SearchRequest"),
        ("knowlebase.retrieve.schema", "DebugSearchRequest"),
        ("knowlebase.retrieve.schema", "SearchResultItem"),
        ("knowlebase.retrieve.schema", "DebugSearchResponse"),
        ("knowlebase.retrieve.schema", "RetrievalErrorCode"),
        ("knowlebase.retrieve.schema", "RetrievalError"),
        ("knowlebase.retrieve.schema", "RetrievalResponse"),
        ("knowlebase.retrieve.strategy", "RRFMergeStrategy"),
        ("knowlebase.retrieve.strategy", "WeightedNormalizationMergeStrategy"),
        ("knowlebase.retrieve.strategy", "NoopRerankStrategy"),
        ("knowlebase.retrieve.strategy", "CrossEncoderRerankStrategy"),
        ("knowlebase.retrieve.strategy", "LLMRerankStrategy"),
    ]
    for mod_path, attr_name in modules:
        module = __import__(mod_path, fromlist=[attr_name])
        assert getattr(module, attr_name) is not None, f"{mod_path}.{attr_name} 不存在"

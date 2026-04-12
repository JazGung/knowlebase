"""
单元测试 - API 端点路由注册验证

注意：API 端点依赖数据库会话和 service 实例（通过 FastAPI Depends 注入），
在 pytest 中无法轻易 mock。因此本文件只验证路由注册是否正确，
实际端点逻辑由 test_document_service.py 覆盖。
"""

import pytest

from knowlebase.admin.document.api import router


class TestDocumentEndpointsReachable:
    """验证端点路由注册正确"""

    @pytest.fixture
    def route_paths(self):
        return {route.path: list(route.methods) for route in router.routes}

    def test_check_route_exists(self, route_paths):
        assert "/check" in route_paths

    def test_upload_route_exists(self, route_paths):
        assert "/upload" in route_paths

    def test_list_route_exists(self, route_paths):
        assert "/list" in route_paths

    def test_detail_route_exists(self, route_paths):
        assert "/detail" in route_paths

    def test_enable_route_exists(self, route_paths):
        assert "/enable" in route_paths

    def test_disable_route_exists(self, route_paths):
        assert "/disable" in route_paths

    def test_reprocess_route_exists(self, route_paths):
        assert "/reprocess" in route_paths

    def test_check_is_post(self, route_paths):
        assert "POST" in route_paths["/check"]

    def test_upload_is_post(self, route_paths):
        assert "POST" in route_paths["/upload"]

    def test_list_is_get(self, route_paths):
        assert "GET" in route_paths["/list"]

    def test_detail_is_get(self, route_paths):
        assert "GET" in route_paths["/detail"]

    def test_enable_is_put(self, route_paths):
        assert "PUT" in route_paths["/enable"]

    def test_disable_is_put(self, route_paths):
        assert "PUT" in route_paths["/disable"]

    def test_reprocess_is_post(self, route_paths):
        assert "POST" in route_paths["/reprocess"]

    def test_all_endpoints_registered(self, route_paths):
        expected = {"/check", "/upload", "/list", "/detail", "/enable", "/disable", "/reprocess"}
        assert expected == set(route_paths.keys())

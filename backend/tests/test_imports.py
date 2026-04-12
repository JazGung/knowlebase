#!/usr/bin/env python
"""
测试所有模块导入
"""

import sys
import os

# 添加 src 目录到Python路径
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(backend_dir, "src")
sys.path.insert(0, src_dir)

def test_imports():
    """测试所有模块导入"""
    modules_to_test = [
        ("knowlebase.core.config", "settings"),
        ("knowlebase.db.session", "session_manager"),
        ("knowlebase.services.minio_service", "MinioService"),
        ("knowlebase.admin.document.service", "UploadService"),
        ("knowlebase.admin.document.service", "DocumentService"),
        ("knowlebase.models.document", "Document"),
        ("knowlebase.models.chunk", "DocumentChunk"),
        ("knowlebase.models.user", "User"),
        ("knowlebase.models.file_cleanup", "FileCleanupLog"),
        ("knowlebase.schemas.document", "FileCheckRequest"),
        ("knowlebase.schemas.file_management", "OrphanedFileInfo"),
        ("knowlebase.admin.document.api", "router"),
        ("knowlebase.admin", "build_router"),
        ("knowlebase.main", "app"),
    ]

    print("开始测试模块导入...")
    print("=" * 60)

    success_count = 0
    failure_count = 0

    for module_path, attribute_name in modules_to_test:
        try:
            if attribute_name:
                module = __import__(module_path, fromlist=[attribute_name])
                attr = getattr(module, attribute_name)
                print(f"[OK] {module_path}.{attribute_name}")
                success_count += 1
            else:
                __import__(module_path)
                print(f"[OK] {module_path}")
                success_count += 1
        except ImportError as e:
            print(f"[FAIL] {module_path}.{attribute_name} - ImportError: {e}")
            failure_count += 1
        except AttributeError as e:
            print(f"[FAIL] {module_path}.{attribute_name} - AttributeError: {e}")
            failure_count += 1
        except Exception as e:
            print(f"[FAIL] {module_path}.{attribute_name} - {type(e).__name__}: {e}")
            failure_count += 1

    print("=" * 60)
    print(f"导入测试结果: 成功 {success_count}, 失败 {failure_count}")

    if failure_count == 0:
        print("[OK] 所有模块导入成功!")
        return True
    else:
        print("[FAIL] 有模块导入失败")
        return False

def test_config():
    """测试配置加载"""
    try:
        from knowlebase.core.config import settings
        print("\n测试配置加载...")
        print(f"调试模式: {settings.debug}")
        print(f"数据库URL: {settings.database_url[:50]}...")
        print(f"Minio端点: {settings.minio_endpoint_url}")
        print(f"文档存储桶: {settings.minio_document_bucket}")
        return True
    except Exception as e:
        print(f"配置加载失败: {e}")
        return False

def test_fastapi_app():
    """测试FastAPI应用创建"""
    try:
        from knowlebase.main import app
        print("\n测试FastAPI应用...")
        print(f"应用标题: {app.title}")
        print(f"应用版本: {app.version}")

        # 检查路由
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        print(f"注册路由数量: {len(routes)}")
        print("主要路由:")
        for route in sorted(routes)[:10]:  # 显示前10个路由
            print(f"  - {route}")

        return True
    except Exception as e:
        print(f"FastAPI应用测试失败: {e}")
        return False

if __name__ == "__main__":
    print("知识库构建与检索系统 - 模块导入测试")
    print("=" * 60)

    # 运行测试
    import_ok = test_imports()
    config_ok = test_config()
    app_ok = test_fastapi_app()

    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"  模块导入: {'通过' if import_ok else '失败'}")
    print(f"  配置加载: {'通过' if config_ok else '失败'}")
    print(f"  FastAPI应用: {'通过' if app_ok else '失败'}")

    if import_ok and config_ok and app_ok:
        print("\n[OK] 所有基础测试通过，可以启动服务!")
        sys.exit(0)
    else:
        print("\n[FAIL] 测试失败，请检查以上错误")
        sys.exit(1)
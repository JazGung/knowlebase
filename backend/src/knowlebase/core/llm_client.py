"""LLM 客户端 — 通过 Higress AI 网关统一路由

业务模块仅传 scene（逻辑名），Higress 侧根据逻辑名路由到实际模型。
"""
from langchain.chat_models import init_chat_model
from openai import OpenAI

from knowlebase.core.config import settings

# Higress 场景常量
SCENE_CHUNKING = "chunking"
SCENE_IMAGE_DESC = "image-desc"
SCENE_ENTITY_EXTRACT = "entity-extract"


def create_chat_model(scene: str, temperature: float = 0):
    """创建 LangChain ChatModel，通过 Higress 路由

    Args:
        scene: Higress 逻辑名，如 SCENE_CHUNKING
        temperature: 生成温度
    """
    return init_chat_model(
        model=scene,
        model_provider="openai",
        api_key="higress",
        base_url=settings.llm_api_base,
        temperature=temperature,
    )


def create_openai_client():
    """创建 OpenAI 客户端，通过 Higress 路由"""
    return OpenAI(
        api_key="higress",
        base_url=settings.llm_api_base,
    )

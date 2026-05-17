"""模型域 — /model/*"""

from fastapi import APIRouter

from knowlebase.model.api import router as model_router_inner

model_router = APIRouter()
model_router.include_router(model_router_inner, prefix="", tags=["模型域"])

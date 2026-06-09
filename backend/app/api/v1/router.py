"""v1 路由汇总。"""

from __future__ import annotations

from fastapi import APIRouter

from app.agents import llm_router as ai_router
from app.api.v1 import health
from app.domains.auth import router as auth_router
from app.domains.cooperations import router as cooperations_router
from app.domains.demands import router as demands_router
from app.domains.devices import router as devices_router
from app.domains.invitations import router as invitations_router
from app.domains.properties import router as properties_router
from app.domains.proposals import router as proposals_router
from app.domains.reviews import router as reviews_router
from app.domains.users import router as users_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health.router)
api_router.include_router(auth_router.router)
api_router.include_router(ai_router.router)
api_router.include_router(devices_router.router)
api_router.include_router(properties_router.router)
api_router.include_router(demands_router.router)
api_router.include_router(invitations_router.router)
api_router.include_router(proposals_router.router)
api_router.include_router(cooperations_router.router)
api_router.include_router(reviews_router.router)
api_router.include_router(users_router.router)

from fastapi import APIRouter

from app.api.v1 import health, instruments, markets

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(instruments.router)
api_router.include_router(markets.router)

from fastapi import APIRouter

from app.api.v1 import health, instruments, markets, me, portfolios, watchlists

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(instruments.router)
api_router.include_router(markets.router)
api_router.include_router(me.router)
api_router.include_router(portfolios.router)
api_router.include_router(watchlists.router)

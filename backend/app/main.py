import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import error_body, install_error_handlers
from app.core.logging import configure_logging

logger = logging.getLogger("marketpulse.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="MarketPulse API",
        version=settings.version,
        description=(
            "Multi-asset market data, analytics and research API. "
            "Research aid only, not investment advice."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        try:
            async with asyncio.timeout(settings.request_timeout_seconds):
                response = await call_next(request)
        except TimeoutError:
            response = JSONResponse(
                error_body("timeout", "The request took too long. Please try again."), 504
            )
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": "MarketPulse API", "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()

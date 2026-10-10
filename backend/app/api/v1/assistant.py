from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.ai.provider import ChatProvider, get_provider
from app.api.deps import DbSession, UserId
from app.core.config import Settings
from app.core.rate_limit import rate_limit
from app.services import assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatContext(BaseModel):
    instrument_id: str | None = Field(None, max_length=64)
    portfolio_id: str | None = Field(None, max_length=64)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    context: ChatContext = Field(default_factory=ChatContext)


def _provider(request: Request) -> ChatProvider | None:
    # Tests swap in a scripted provider through app.state.
    override = getattr(request.app.state, "llm_provider", None)
    if override is not None:
        return override
    settings: Settings = request.app.state.settings
    return get_provider(settings)


@router.get("/status", summary="Whether the assistant is configured, and its limits")
def assistant_status(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    out = assistant_service.status(None, settings, None)
    if getattr(request.app.state, "llm_provider", None) is not None:
        out["configured"] = True
    return out


@router.get("/usage", summary="Your assistant usage today")
def assistant_usage(user: UserId, session: DbSession, request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    req, tok, _ = assistant_service.usage_today(session, user)
    return {
        "requests": req,
        "tokens": tok,
        "requests_left": max(0, settings.ai_requests_per_user_day - req),
    }


@router.post(
    "/chat",
    summary="Ask the research assistant",
    dependencies=[rate_limit("assistant", 6)],
)
def chat(user: UserId, session: DbSession, request: Request, body: ChatRequest) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    return assistant_service.answer(
        session,
        settings,
        _provider(request),
        user,
        [m.model_dump() for m in body.messages],
        body.context.model_dump(),
    )

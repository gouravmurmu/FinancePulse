from typing import Any

from fastapi import APIRouter

from app.api.deps import DbSession, UserId
from app.models import Profile

router = APIRouter(tags=["account"])


@router.get("/me", summary="The signed-in user's id and preferences")
def me(user: UserId, session: DbSession) -> dict[str, Any]:
    profile = session.get(Profile, user)
    return {
        "user_id": user,
        "display_name": profile.display_name if profile else None,
        "base_currency": profile.base_currency if profile else "USD",
        "region": profile.region if profile else "global",
    }

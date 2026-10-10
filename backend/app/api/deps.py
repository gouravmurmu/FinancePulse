import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import verify_token
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import get_session

DbSession = Annotated[Session, Depends(get_session)]


def current_user_id(request: Request) -> uuid.UUID:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("unauthorized", "Sign in to continue", 401)
    settings: Settings = request.app.state.settings
    return verify_token(token.strip(), settings)


UserId = Annotated[uuid.UUID, Depends(current_user_id)]

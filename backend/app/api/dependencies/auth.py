from fastapi import (
    HTTPException,
    Request,
    status,
)

from app.core.config import get_settings
from app.models.user import AppUser
from app.services.auth import (
    get_user_by_session_token,
)


def require_user(
    request: Request,
) -> AppUser:
    settings = get_settings()

    token = request.cookies.get(
        settings.session_cookie_name
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user = get_user_by_session_token(
        token
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user

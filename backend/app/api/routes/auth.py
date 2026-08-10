from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.api.dependencies.auth import (
    require_user,
)
from app.core.config import get_settings
from app.models.user import AppUser
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from app.services.auth import (
    authenticate_user,
    revoke_session,
)


router = APIRouter()


def user_response(
    user: AppUser,
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
) -> LoginResponse:
    settings = get_settings()

    result = authenticate_user(
        username=payload.username,
        password=payload.password,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.token,
        max_age=(
            settings.session_ttl_days
            * 24
            * 60
            * 60
        ),
        expires=result.expires_at,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return LoginResponse(
        user=user_response(
            result.user
        )
    )


@router.get(
    "/auth/me",
    response_model=CurrentUserResponse,
)
def me(
    user: AppUser = Depends(
        require_user
    ),
) -> CurrentUserResponse:
    return user_response(user)


@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
)
def logout(
    request: Request,
    response: Response,
) -> LogoutResponse:
    settings = get_settings()

    token = request.cookies.get(
        settings.session_cookie_name
    )

    if token:
        revoke_session(token)

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return LogoutResponse(
        success=True
    )

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy import select

from app.core.config import get_settings
from app.core.passwords import (
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.session import SessionLocal
from app.models.session import AppSession
from app.models.user import AppUser


@dataclass
class LoginResult:
    user: AppUser
    token: str
    expires_at: datetime


def normalize_username(
    username: str,
) -> str:
    return username.strip().casefold()


def hash_session_token(
    token: str,
) -> str:
    return sha256(
        token.encode("utf-8")
    ).hexdigest()


def authenticate_user(
    username: str,
    password: str,
) -> LoginResult | None:
    settings = get_settings()

    normalized = normalize_username(
        username
    )

    now = datetime.now(
        timezone.utc
    )

    expires_at = now + timedelta(
        days=settings.session_ttl_days
    )

    with SessionLocal() as session:
        user = session.execute(
            select(AppUser).where(
                AppUser.username == normalized,
                AppUser.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if user is None:
            return None

        if not verify_password(
            user.password_hash,
            password,
        ):
            return None

        if password_needs_rehash(
            user.password_hash
        ):
            user.password_hash = (
                hash_password(password)
            )

        token = secrets.token_urlsafe(
            32
        )

        db_session = AppSession(
            user_id=user.id,
            token_hash=hash_session_token(
                token
            ),
            expires_at=expires_at,
        )

        user.last_login_at = now

        session.add(db_session)
        session.commit()

        session.refresh(user)

        session.expunge(user)

        return LoginResult(
            user=user,
            token=token,
            expires_at=expires_at,
        )


def get_user_by_session_token(
    token: str,
) -> AppUser | None:
    now = datetime.now(
        timezone.utc
    )

    token_hash = hash_session_token(
        token
    )

    with SessionLocal() as session:
        result = session.execute(
            select(
                AppSession,
                AppUser,
            )
            .join(
                AppUser,
                AppUser.id
                == AppSession.user_id,
            )
            .where(
                AppSession.token_hash
                == token_hash,
                AppSession.revoked_at.is_(
                    None
                ),
                AppSession.expires_at
                > now,
                AppUser.is_active.is_(
                    True
                ),
            )
        ).one_or_none()

        if result is None:
            return None

        app_session, user = result

        app_session.last_seen_at = now

        session.commit()

        session.expunge(user)

        return user


def revoke_session(
    token: str,
) -> bool:
    now = datetime.now(
        timezone.utc
    )

    token_hash = hash_session_token(
        token
    )

    with SessionLocal() as session:
        app_session = session.execute(
            select(AppSession).where(
                AppSession.token_hash
                == token_hash,
                AppSession.revoked_at.is_(
                    None
                ),
            )
        ).scalar_one_or_none()

        if app_session is None:
            return False

        app_session.revoked_at = now

        session.commit()

        return True

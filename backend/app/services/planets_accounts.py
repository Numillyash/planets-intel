from datetime import datetime, timezone
from urllib.parse import urljoin

from sqlalchemy import delete, or_, select, update

from app.core.config import get_settings
from app.core.credentials import encrypt_credential
from app.db.session import SessionLocal
from app.models.dashboard_intel_share import DashboardIntelShare
from app.models.game_intel_grant import GameIntelGrant
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


def normalize_planets_username(
    username: str,
) -> str:
    return username.strip().casefold()


async def load_planets_profile_image_url(
    username: str,
) -> str | None:
    """Load optional public profile presentation metadata.

    Profile images are deliberately not persisted as game/intel facts.  A
    profile or image lookup failure must not make linked accounts unavailable.
    """
    try:
        payload = await PlanetsNuClient().get(
            "account/loadprofile",
            params={"username": username.strip()},
        )
    except PlanetsNuError:
        return None

    if not isinstance(payload, dict):
        return None

    account = payload.get("account")
    if not isinstance(account, dict):
        return None

    raw_image_url = account.get("imageurl")
    if not isinstance(raw_image_url, str) or not raw_image_url.strip():
        return None

    return urljoin(
        get_settings().planetsnu_api_base_url.rstrip("/") + "/",
        raw_image_url.strip(),
    )


async def link_planets_account(
    user_id: int,
    username: str,
    password: str,
) -> PlanetsAccount:
    display_username = username.strip()

    normalized_username = (
        normalize_planets_username(
            display_username
        )
    )

    client = PlanetsNuClient()

    api_key = await client.login(
        username=display_username,
        password=password,
    )

    encrypted_api_key = encrypt_credential(
        api_key
    )

    del api_key

    now = datetime.now(
        timezone.utc
    )

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.planets_username_normalized
                == normalized_username,
            )
        ).scalar_one_or_none()

        if account is None:
            account = PlanetsAccount(
                user_id=user_id,
                planets_username=display_username,
                planets_username_normalized=normalized_username,
                planets_account_id=None,
                api_key_encrypted=encrypted_api_key,
                is_active=True,
                last_verified_at=now,
                last_error=None,
            )

            session.add(account)

        else:
            account.planets_username = (
                display_username
            )

            account.api_key_encrypted = (
                encrypted_api_key
            )

            account.is_active = True
            account.last_verified_at = now
            account.last_error = None
            account.updated_at = now

        session.commit()
        session.refresh(account)
        session.expunge(account)

        return account


def list_planets_accounts(
    user_id: int,
) -> list[PlanetsAccount]:
    with SessionLocal() as session:
        accounts = session.execute(
            select(PlanetsAccount)
            .where(
                PlanetsAccount.user_id
                == user_id,
                PlanetsAccount.is_active.is_(True),
            )
            .order_by(
                PlanetsAccount.id
            )
        ).scalars().all()

        for account in accounts:
            session.expunge(account)

        return list(accounts)


def unlink_planets_account(
    user_id: int,
    account_id: int,
) -> bool:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id
                == account_id,
                PlanetsAccount.user_id
                == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if account is None:
            return False

        now = datetime.now(
            timezone.utc
        )

        # Unlink is also an explicit withdrawal of dashboard-sharing consent.
        # Re-linking the account later must not silently restore old shares.
        session.execute(
            delete(DashboardIntelShare).where(
                or_(
                    DashboardIntelShare.account_low_id
                    == account.id,
                    DashboardIntelShare.account_high_id
                    == account.id,
                )
            )
        )

        # P1: unlink permanently revokes open bilateral consent in every game.
        # Keep old records for audit, never reactivate them upon re-link.
        session.execute(
            update(GameIntelGrant)
            .where(
                or_(
                    GameIntelGrant.grantor_account_id == account.id,
                    GameIntelGrant.grantee_account_id == account.id,
                ),
                GameIntelGrant.revoked_at.is_(None),
            )
            .values(status="revoked", revoked_at=now, updated_at=now)
        )

        account.api_key_encrypted = (
            encrypt_credential(
                "UNLINKED"
            )
        )

        account.is_active = False
        account.last_error = None
        account.updated_at = now

        session.commit()

        return True

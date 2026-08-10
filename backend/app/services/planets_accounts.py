from datetime import datetime, timezone

from sqlalchemy import select

from app.core.credentials import encrypt_credential
from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


def normalize_planets_username(
    username: str,
) -> str:
    return username.strip().casefold()


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
                == user_id
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
            )
        ).scalar_one_or_none()

        if account is None:
            return False

        session.delete(account)
        session.commit()

        return True

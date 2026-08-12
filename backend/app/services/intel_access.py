from dataclasses import dataclass

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.services.intel_sharing import active_dashboard_peer_account_ids


@dataclass(frozen=True)
class AccessibleIntelAccount:
    id: int
    planets_username: str
    planets_account_id: int | None
    is_owned: bool


def accessible_intel_accounts(
    *,
    user_id: int,
) -> list[AccessibleIntelAccount]:
    """Return active linked accounts whose factual intel this user may combine.

    All active accounts owned by the local Intel Client user are included.
    Accounts owned by other local users are included only when an active,
    mutually-approved dashboard intel share connects them to at least one of
    the current user's owned accounts.
    """

    with SessionLocal() as session:
        owned = list(
            session.execute(
                select(PlanetsAccount)
                .where(
                    PlanetsAccount.user_id == user_id,
                    PlanetsAccount.is_active.is_(True),
                )
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )

    owned_ids = {account.id for account in owned}
    peer_ids: set[int] = set()

    for account_id in owned_ids:
        peer_ids.update(
            active_dashboard_peer_account_ids(
                linked_account_id=account_id,
            )
        )

    all_ids = sorted(owned_ids | peer_ids)
    if not all_ids:
        return []

    with SessionLocal() as session:
        accounts = list(
            session.execute(
                select(PlanetsAccount)
                .where(
                    PlanetsAccount.id.in_(all_ids),
                    PlanetsAccount.is_active.is_(True),
                )
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )

    return [
        AccessibleIntelAccount(
            id=account.id,
            planets_username=account.planets_username,
            planets_account_id=account.planets_account_id,
            is_owned=account.id in owned_ids,
        )
        for account in accounts
    ]

from dataclasses import dataclass

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount


@dataclass(frozen=True)
class AccessibleIntelAccount:
    id: int
    planets_username: str
    planets_account_id: int | None
    is_owned: bool


def accessible_intel_accounts(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> list[AccessibleIntelAccount]:
    """P0/P1 deny-by-default: exactly one selected locally owned observer.

    A global dashboard pair, even one approved by both parties, must never
    grant access to another observer's private game data. The game ID is
    mandatory and callers must also constrain their data queries to it.
    This restriction applies equally to public, private and team games.
    P1's mutual game-scoped consent ledger grants NO read entitlements;
    """
    if user_id <= 0 or game_id <= 0 or linked_account_id <= 0:
        return []

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if account is None:
            return []

        return [AccessibleIntelAccount(
            id=account.id,
            planets_username=account.planets_username,
            planets_account_id=account.planets_account_id,
            is_owned=True,
        )]

from typing import Any

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models.dashboard_intel_share import DashboardIntelShare
from app.models.planets_account import PlanetsAccount


class IntelShareError(RuntimeError):
    pass


class IntelShareAccountNotFound(IntelShareError):
    pass


class IntelShareTargetNotFound(IntelShareError):
    pass


class IntelShareTargetAmbiguous(IntelShareError):
    pass


class IntelShareForbidden(IntelShareError):
    pass


def _owned_active_account(
    session,
    *,
    user_id: int,
    account_id: int,
) -> PlanetsAccount | None:
    return session.execute(
        select(PlanetsAccount).where(
            PlanetsAccount.id == account_id,
            PlanetsAccount.user_id == user_id,
            PlanetsAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _share_pair(
    first_account_id: int,
    second_account_id: int,
) -> tuple[int, int]:
    return tuple(sorted((first_account_id, second_account_id)))


def _serialize_share(
    session,
    *,
    share: DashboardIntelShare,
    user_id: int,
) -> dict[str, Any]:
    low = session.execute(
        select(PlanetsAccount).where(
            PlanetsAccount.id == share.account_low_id
        )
    ).scalar_one()
    high = session.execute(
        select(PlanetsAccount).where(
            PlanetsAccount.id == share.account_high_id
        )
    ).scalar_one()

    active = (
        share.approved_low_at is not None
        and share.approved_high_at is not None
        and low.is_active
        and high.is_active
    )

    return {
        "id": share.id,
        "status": "disabled",
        "account_a": {
            "linked_account_id": low.id,
            "planets_username": low.planets_username,
            "is_mine": low.user_id == user_id,
            "is_active": low.is_active,
            "approved": share.approved_low_at is not None,
        },
        "account_b": {
            "linked_account_id": high.id,
            "planets_username": high.planets_username,
            "is_mine": high.user_id == user_id,
            "is_active": high.is_active,
            "approved": share.approved_high_at is not None,
        },
        "created_at": share.created_at,
        "updated_at": share.updated_at,
    }


def list_dashboard_intel_shares(
    *,
    user_id: int,
) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        owned_account_ids = session.execute(
            select(PlanetsAccount.id).where(
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalars().all()

        if not owned_account_ids:
            return []

        shares = session.execute(
            select(DashboardIntelShare)
            .where(
                or_(
                    DashboardIntelShare.account_low_id.in_(owned_account_ids),
                    DashboardIntelShare.account_high_id.in_(owned_account_ids),
                )
            )
            .order_by(DashboardIntelShare.id)
        ).scalars().all()

        return [
            _serialize_share(
                session,
                share=share,
                user_id=user_id,
            )
            for share in shares
        ]


def request_dashboard_intel_share(
    *,
    user_id: int,
    source_account_id: int,
    target_planets_username: str,
) -> dict[str, Any]:
    """P0: legacy account-global consent is not game-scoped authorization."""
    raise IntelShareForbidden(
        "Global sharing is disabled until a game-scoped policy is reviewed"
    )


def accept_dashboard_intel_share(
    *,
    user_id: int,
    share_id: int,
    account_id: int,
) -> dict[str, Any]:
    """P0: keep old agreements revocable, but never activate new approvals."""
    raise IntelShareForbidden(
        "Global sharing is disabled until a game-scoped policy is reviewed"
    )


def revoke_dashboard_intel_share(
    *,
    user_id: int,
    share_id: int,
    account_id: int,
) -> bool:
    with SessionLocal() as session:
        account = _owned_active_account(
            session,
            user_id=user_id,
            account_id=account_id,
        )

        if account is None:
            return False

        share = session.execute(
            select(DashboardIntelShare).where(
                DashboardIntelShare.id == share_id
            )
        ).scalar_one_or_none()

        if share is None:
            return False

        if account.id not in {
            share.account_low_id,
            share.account_high_id,
        }:
            return False

        session.delete(share)
        session.commit()
        return True


def active_dashboard_peer_account_ids(
    *,
    linked_account_id: int,
) -> list[int]:
    """P0 defense in depth: no legacy global agreement authorizes peers."""
    return []

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models.dashboard_intel_share import DashboardIntelShare
from app.models.planets_account import PlanetsAccount
from app.services.planets_accounts import normalize_planets_username


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
        "status": "active" if active else "pending",
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
    normalized_target = normalize_planets_username(
        target_planets_username
    )

    with SessionLocal() as session:
        source = _owned_active_account(
            session,
            user_id=user_id,
            account_id=source_account_id,
        )

        if source is None:
            raise IntelShareAccountNotFound(
                "Source linked Planets.nu account not found"
            )

        if normalized_target == source.planets_username_normalized:
            raise IntelShareError(
                "A linked account cannot share intel with itself"
            )

        targets = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.planets_username_normalized
                == normalized_target,
                PlanetsAccount.is_active.is_(True),
                PlanetsAccount.id != source.id,
            )
        ).scalars().all()

        if not targets:
            raise IntelShareTargetNotFound(
                "Target Planets.nu account is not linked to this service"
            )

        if len(targets) != 1:
            raise IntelShareTargetAmbiguous(
                "More than one linked service account matches that Planets.nu username"
            )

        target = targets[0]
        low_id, high_id = _share_pair(
            source.id,
            target.id,
        )

        share = session.execute(
            select(DashboardIntelShare).where(
                DashboardIntelShare.account_low_id == low_id,
                DashboardIntelShare.account_high_id == high_id,
            )
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if share is None:
            share = DashboardIntelShare(
                account_low_id=low_id,
                account_high_id=high_id,
                requested_by_account_id=source.id,
            )
            session.add(share)
            session.flush()

        if source.id == share.account_low_id:
            share.approved_low_at = share.approved_low_at or now
        else:
            share.approved_high_at = share.approved_high_at or now

        # One local Intel Client user controls both linked accounts, so one
        # authenticated action is sufficient consent for both sides.
        if target.user_id == user_id:
            if target.id == share.account_low_id:
                share.approved_low_at = share.approved_low_at or now
            else:
                share.approved_high_at = share.approved_high_at or now

        share.updated_at = now
        session.commit()
        session.refresh(share)

        return _serialize_share(
            session,
            share=share,
            user_id=user_id,
        )


def accept_dashboard_intel_share(
    *,
    user_id: int,
    share_id: int,
    account_id: int,
) -> dict[str, Any]:
    with SessionLocal() as session:
        account = _owned_active_account(
            session,
            user_id=user_id,
            account_id=account_id,
        )

        if account is None:
            raise IntelShareAccountNotFound(
                "Linked Planets.nu account not found"
            )

        share = session.execute(
            select(DashboardIntelShare).where(
                DashboardIntelShare.id == share_id
            )
        ).scalar_one_or_none()

        if share is None:
            raise IntelShareAccountNotFound(
                "Dashboard intel share not found"
            )

        if account.id not in {
            share.account_low_id,
            share.account_high_id,
        }:
            raise IntelShareForbidden(
                "This linked account is not part of the intel share"
            )

        now = datetime.now(timezone.utc)

        if account.id == share.account_low_id:
            share.approved_low_at = share.approved_low_at or now
        else:
            share.approved_high_at = share.approved_high_at or now

        share.updated_at = now
        session.commit()
        session.refresh(share)

        return _serialize_share(
            session,
            share=share,
            user_id=user_id,
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
    with SessionLocal() as session:
        shares = session.execute(
            select(DashboardIntelShare).where(
                or_(
                    DashboardIntelShare.account_low_id == linked_account_id,
                    DashboardIntelShare.account_high_id == linked_account_id,
                ),
                DashboardIntelShare.approved_low_at.is_not(None),
                DashboardIntelShare.approved_high_at.is_not(None),
            )
        ).scalars().all()

        peer_ids = [
            share.account_high_id
            if share.account_low_id == linked_account_id
            else share.account_low_id
            for share in shares
        ]

        if not peer_ids:
            return []

        active_ids = session.execute(
            select(PlanetsAccount.id).where(
                PlanetsAccount.id.in_(peer_ids),
                PlanetsAccount.is_active.is_(True),
            )
        ).scalars().all()

        return sorted(active_ids)

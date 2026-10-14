"""P1 directional, game-scoped consent ledger. No private read delegation."""
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_intel_grant import GameIntelGrant
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.services.planets_accounts import normalize_planets_username

ALLOWED_SCOPES = frozenset({
    "owned_unit_locations",
    "third_party_contacts",
    "combat_vcr_evidence",
    "owned_planet_details",
    "owned_ship_details",
})


class GrantError(RuntimeError):
    pass


class GrantNotFound(GrantError):
    pass


class GrantForbidden(GrantError):
    pass


class GrantConflict(GrantError):
    pass


def _owned(session, user_id: int, account_id: int) -> PlanetsAccount | None:
    return session.execute(select(PlanetsAccount).where(
        PlanetsAccount.id == account_id,
        PlanetsAccount.user_id == user_id,
        PlanetsAccount.is_active.is_(True),
    )).scalar_one_or_none()


def _slot(session, game: Game, account: PlanetsAccount) -> int | None:
    """Demand a unique active, current-turn roster match, never account-pair trust."""
    username = normalize_planets_username(account.planets_username)
    if not username:
        return None
    predicates = [func.lower(func.trim(GamePlayerSlot.username)) == username]
    if account.planets_account_id is not None and account.planets_account_id > 0:
        predicates.append(GamePlayerSlot.account_id == account.planets_account_id)
    rows = list(session.execute(select(GamePlayerSlot).where(
        GamePlayerSlot.game_id == game.id,
        GamePlayerSlot.status == 1,
        GamePlayerSlot.last_seen_turn == game.current_turn,
        or_(*predicates),
    )).scalars().all())
    # A numeric ID pointing to a different username is an identity conflict.
    matches = [r for r in rows if normalize_planets_username(r.username) == username]
    if len(rows) != 1 or len(matches) != 1:
        return None
    if (
        account.planets_account_id is not None
        and account.planets_account_id > 0
        and matches[0].account_id is not None
        and matches[0].account_id > 0
        and account.planets_account_id != matches[0].account_id
    ):
        return None
    return int(matches[0].slot_id)


def _roster(session, game_id: int, from_account: PlanetsAccount, to_account: PlanetsAccount) -> tuple[int, int, int]:
    game = session.get(Game, game_id)
    if game is None or game.status_id != 2 or game.current_turn <= 0:
        raise GrantConflict("Fresh running-game roster required")
    first = _slot(session, game, from_account)
    second = _slot(session, game, to_account)
    if first is None or second is None or first == second:
        raise GrantConflict("Unambiguous active in-game positions required")
    return first, second, int(game.current_turn)


def _record(grant: GameIntelGrant) -> dict:
    return {
        "id": grant.id,
        "game_id": grant.game_id,
        "grantor_account_id": grant.grantor_account_id,
        "grantee_account_id": grant.grantee_account_id,
        "grantor_slot_id": grant.grantor_slot_id,
        "grantee_slot_id": grant.grantee_slot_id,
        "membership_verified_turn": grant.membership_verified_turn,
        "requested_scopes": grant.requested_scopes,
        "status": grant.status,
        "authorizes_private_intel": False,
        "consented_at": grant.consented_at,
        "revoked_at": grant.revoked_at,
        "created_at": grant.created_at,
        "updated_at": grant.updated_at,
    }


def list_game_grants(*, user_id: int, game_id: int) -> list[dict]:
    with SessionLocal() as session:
        ids = list(session.execute(select(PlanetsAccount.id).where(
            PlanetsAccount.user_id == user_id,
            PlanetsAccount.is_active.is_(True),
        )).scalars().all())
        if not ids:
            return []
        rows = session.execute(select(GameIntelGrant).where(
            GameIntelGrant.game_id == game_id,
            or_(
                GameIntelGrant.grantor_account_id.in_(ids),
                GameIntelGrant.grantee_account_id.in_(ids),
            ),
        ).order_by(GameIntelGrant.id)).scalars().all()
        return [_record(row) for row in rows]


def request_game_grant(
    *, user_id: int, game_id: int, grantor_account_id: int,
    grantee_planets_username: str, requested_scopes: list[str],
) -> dict:
    scopes = sorted(set(requested_scopes))
    if not scopes or len(scopes) != len(requested_scopes) or not set(scopes) <= ALLOWED_SCOPES:
        raise GrantConflict("Invalid or duplicate requested disclosure scopes")

    with SessionLocal() as session:
        grantor = _owned(session, user_id, grantor_account_id)
        if grantor is None:
            raise GrantNotFound("Source linked account not found")
        name = normalize_planets_username(grantee_planets_username)
        if not name or name == grantor.planets_username_normalized:
            raise GrantConflict("Source and destination must be distinct")
        targets = list(session.execute(select(PlanetsAccount).where(
            PlanetsAccount.planets_username_normalized == name,
            PlanetsAccount.is_active.is_(True),
        )).scalars().all())
        if len(targets) != 1:
            raise GrantNotFound("Unique active target linked account not found")
        grantee = targets[0]
        if grantor.user_id == grantee.user_id:
            raise GrantForbidden("Two positions under the same site user may not grant access")

        source_slot, target_slot, turn = _roster(session, game_id, grantor, grantee)
        existing = session.execute(select(GameIntelGrant.id).where(
            GameIntelGrant.game_id == game_id,
            GameIntelGrant.grantor_account_id == grantor.id,
            GameIntelGrant.grantee_account_id == grantee.id,
            GameIntelGrant.revoked_at.is_(None),
        )).scalar_one_or_none()
        if existing is not None:
            raise GrantConflict("An unrevoked game grant already exists")

        row = GameIntelGrant(
            game_id=game_id,
            grantor_account_id=grantor.id,
            grantee_account_id=grantee.id,
            grantor_slot_id=source_slot,
            grantee_slot_id=target_slot,
            membership_verified_turn=turn,
            requested_scopes=scopes,
            status="pending",
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise GrantConflict("An unrevoked game grant already exists") from exc
        session.refresh(row)
        return _record(row)


def consent_game_grant(
    *, user_id: int, game_id: int, grant_id: int, grantee_account_id: int,
) -> dict:
    with SessionLocal() as session:
        grantee = _owned(session, user_id, grantee_account_id)
        if grantee is None:
            raise GrantNotFound("Target account not found")
        row = session.execute(select(GameIntelGrant).where(
            GameIntelGrant.id == grant_id,
            GameIntelGrant.game_id == game_id,
        ).with_for_update()).scalar_one_or_none()
        if row is None or row.grantee_account_id != grantee.id:
            raise GrantNotFound("Game grant not found")
        if row.status != "pending" or row.revoked_at is not None:
            raise GrantConflict("Grant is not pending")
        grantor = session.get(PlanetsAccount, row.grantor_account_id)
        if grantor is None or not grantor.is_active:
            raise GrantConflict("Grantor is no longer active")
        first, second, turn = _roster(session, game_id, grantor, grantee)
        if (first, second) != (row.grantor_slot_id, row.grantee_slot_id):
            raise GrantConflict("Positions changed: request new game-specific consent")
        row.membership_verified_turn = turn
        row.status = "consented_pending_policy"
        row.consented_at = datetime.now(timezone.utc)
        row.updated_at = row.consented_at
        session.commit()
        session.refresh(row)
        return _record(row)


def revoke_game_grant(
    *, user_id: int, game_id: int, grant_id: int, account_id: int,
) -> dict:
    with SessionLocal() as session:
        actor = _owned(session, user_id, account_id)
        if actor is None:
            raise GrantNotFound("Linked account not found")
        row = session.execute(select(GameIntelGrant).where(
            GameIntelGrant.id == grant_id,
            GameIntelGrant.game_id == game_id,
        ).with_for_update()).scalar_one_or_none()
        if row is None or actor.id not in (row.grantor_account_id, row.grantee_account_id):
            raise GrantNotFound("Game grant not found")
        if row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            row.updated_at = row.revoked_at
            row.status = "revoked"
            session.commit()
            session.refresh(row)
        return _record(row)


def has_private_read_authority_from_grant(*, user_id: int, game_id: int, account_id: int) -> bool:
    """P1 policy HOLD: never expose arbitrary private observations or refresh peers.

    Mutual user consent cannot attest Planets.nu diplomacy/field entitlements.
    Future positive permissions require a separate upstream field-verified
    projection, not broadening the P0 selected-observer set.
    """
    return False

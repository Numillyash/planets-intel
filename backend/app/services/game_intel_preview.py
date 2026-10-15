"""Owner-only preview of the exact fields in a proposed game intel grant.

This code never authorizes the grantee to read private observations.
It neither fetches an upstream turn nor combines batches from observers.
"""
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_intel_grant import GameIntelGrant
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.game_intel_grants import GrantNotFound, GrantConflict, _roster, _owned
from app.services.intel_grant_projection import project_current_grant_batch


def preview_game_grant(
    *, user_id: int, game_id: int, grant_id: int, linked_account_id: int,
) -> dict[str, Any]:
    """Return only the grantor's own current-turn scope preview.

    The grantee cannot call this endpoint, even after bilateral consent.
    Preview does not exercise the stored grant as an authorization source.
    The result is a private owner-only diagnostic, never public demo data.
    """
    with SessionLocal() as session:
        grantor = _owned(session, user_id, linked_account_id)
        if grantor is None:
            raise GrantNotFound("Linked source account not found")
        grant = session.execute(select(GameIntelGrant).where(
            GameIntelGrant.id == grant_id,
            GameIntelGrant.game_id == game_id,
            GameIntelGrant.grantor_account_id == grantor.id,
            GameIntelGrant.revoked_at.is_(None),
        )).scalar_one_or_none()
        if grant is None:
            raise GrantNotFound("This user's active game grant not found")
        grantee = session.get(PlanetsAccount, grant.grantee_account_id)
        if grantee is None or not grantee.is_active:
            raise GrantConflict("Grant target account is not active")
        from_slot, to_slot, turn = _roster(session, game_id, grantor, grantee)
        if (from_slot, to_slot) != (grant.grantor_slot_id, grant.grantee_slot_id):
            raise GrantConflict("Game membership changed; request new consent")
        game = session.get(Game, game_id)
        if game is None or game.current_turn != turn:
            raise GrantConflict("No verified current game turn")

        batch = session.execute(select(PrivateObservationBatch).where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.turn == turn,
            PrivateObservationBatch.observer_planets_account_id == grantor.id,
            PrivateObservationBatch.source_player_slot_id == from_slot,
        ).order_by(
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )).scalars().first()
        if batch is None:
            raise GrantConflict("Grantor has no current owned-observer snapshot")

        scopes = frozenset(grant.requested_scopes)
        if grant.sharing_mode == "native":
            # Native never adds an external user's private snapshot.
            return {
                "game_id": game_id, "grant_id": grant_id, "mode": "native",
                "turn": turn, "source_batch_id": None, "preview_only": True,
                "planets": [], "ships": [], "starbases": [],
                "messages": [], "combat_events": [], "third_party_contacts": [],
            }
        if grant.sharing_mode != "unrestricted":
            raise GrantConflict("Unknown disclosure mode")

        fields = project_current_grant_batch(
            session,
            batch=batch,
            scopes=scopes,
            grantor_slot=from_slot,
            grantee_slot=to_slot,
        )
        return {
            "game_id": game_id, "grant_id": grant.id,
            "mode": "unrestricted",
            "turn": turn, "source_batch_id": batch.id,
            "preview_only": True,
            "requested_scopes": sorted(scopes),
            **fields,
        }

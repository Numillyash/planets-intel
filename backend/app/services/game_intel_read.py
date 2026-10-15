"""Recipient-scoped, current-turn, revocable game-intel read projection.

This service never broadens `accessible_intel_accounts` or returns raw peer
snapshots. Every request rechecks the selected recipient, grant, consent, roster,
source batch, scopes and operator activation gate within one DB transaction.
"""
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_intel_grant import GameIntelGrant
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.game_intel_grants import (
    ALLOWED_SCOPES, GrantConflict, GrantForbidden, GrantNotFound, _owned, _roster,
)
from app.services.intel_grant_projection import project_current_grant_batch


def get_received_game_intel(
    *, user_id: int, game_id: int, linked_account_id: int,
) -> dict[str, Any]:
    """One canonical current turn, one local recipient, direct bilateral grants.

    Pre-consent snapshots cannot be re-disclosed. A revoked or roster-stale
    grant fails closed on every request, without mutable client authorization.
    """
    if not get_settings().intel_expanded_sharing_enabled:
        raise GrantForbidden("Scoped cross-player intelligence is disabled on this server")
    if user_id <= 0 or game_id <= 0 or linked_account_id <= 0:
        raise GrantNotFound("Recipient game context not found")

    with SessionLocal() as session:
        recipient = _owned(session, user_id, linked_account_id)
        if recipient is None:
            raise GrantNotFound("Selected recipient is not locally owned and active")
        game = session.get(Game, game_id)
        if game is None or game.status_id != 2 or game.current_turn <= 0:
            raise GrantConflict("Current running game cannot be verified")
        current_turn = int(game.current_turn)

        grants = session.execute(select(GameIntelGrant).where(
            GameIntelGrant.game_id == game_id,
            GameIntelGrant.grantee_account_id == recipient.id,
            GameIntelGrant.status == "consented_pending_policy",
            GameIntelGrant.sharing_mode == "unrestricted",
            GameIntelGrant.consented_at.is_not(None),
            GameIntelGrant.expanded_disclosure_confirmed_at.is_not(None),
            GameIntelGrant.revoked_at.is_(None),
        ).order_by(GameIntelGrant.id)).scalars().all()

        sources: list[dict[str, Any]] = []
        for grant in grants:
            grantor = session.get(PlanetsAccount, grant.grantor_account_id)
            if (
                grantor is None or not grantor.is_active
                or grantor.user_id == recipient.user_id
            ):
                continue
            scopes = grant.requested_scopes
            if (
                not isinstance(scopes, list) or not scopes
                or len(scopes) != len(set(scopes))
                or not set(scopes).issubset(ALLOWED_SCOPES)
            ):
                continue
            if grant.consented_at is None or grant.expanded_disclosure_confirmed_at is None:
                continue
            try:
                grantor_slot, recipient_slot, validated_turn = _roster(
                    session, game_id, grantor, recipient,
                )
            except GrantConflict:
                continue
            if (
                validated_turn != current_turn
                or (grantor_slot, recipient_slot) !=
                (grant.grantor_slot_id, grant.grantee_slot_id)
            ):
                continue

            batch = session.execute(select(PrivateObservationBatch).where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.turn == current_turn,
                PrivateObservationBatch.observer_planets_account_id == grantor.id,
                PrivateObservationBatch.source_player_slot_id == grantor_slot,
                PrivateObservationBatch.observed_at >= grant.consented_at,
                PrivateObservationBatch.observed_at >= grant.expanded_disclosure_confirmed_at,
            ).order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )).scalars().first()
            if batch is None:
                # The source needs to make a new current-turn observation after
                # explicit consent; earlier snapshots cannot be backfilled.
                continue

            fields = project_current_grant_batch(
                session,
                batch=batch,
                scopes=frozenset(scopes),
                grantor_slot=grantor_slot,
                grantee_slot=recipient_slot,
            )
            sources.append({
                "grant_id": grant.id,
                "source_linked_account_id": grantor.id,
                "source_player_slot_id": grantor_slot,
                "source_batch_id": batch.id,
                "source_observed_at": batch.observed_at,
                "requested_scopes": sorted(scopes),
                **fields,
            })

        return {
            "game_id": game_id,
            "turn": current_turn,
            "primary_linked_account_id": recipient.id,
            "mode": "scoped_partner_intel",
            "aggregation_policy": "source_separated_allowlisted_current_turn",
            "sources": sources,
        }

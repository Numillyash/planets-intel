"""Owner-only preview of the exact fields in a proposed game intel grant.

This code never authorizes the grantee to read private observations.
It neither fetches an upstream turn nor combines batches from observers.
"""
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game import Game
from app.models.game_intel_grant import GameIntelGrant
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_message_observation import PrivateMessageObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.services.game_intel_grants import GrantNotFound, GrantConflict, _roster, _owned
from app.services.intel_disclosure_projection import (
    project_owned_entity_fields, project_private_message,
)


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

        planet_rows = session.execute(select(PlanetObservation).where(
            PlanetObservation.batch_id == batch.id,
        )).scalars().all()
        ship_rows = session.execute(select(ShipObservation).where(
            ShipObservation.batch_id == batch.id,
        )).scalars().all()
        base_rows = session.execute(select(StarbaseObservation).where(
            StarbaseObservation.batch_id == batch.id,
        )).scalars().all()
        planet_owners = {planet.planet_id: planet.owner_id for planet in planet_rows}

        planets = [
            {"planet_id": planet.planet_id,
             "info_turn": planet.info_turn,
             "fields": project_owned_entity_fields(
                 kind="planet", raw=planet.payload, scopes=scopes,
                 owner_slot_id=planet.owner_id, grantor_slot_id=from_slot,
             )}
            for planet in planet_rows if planet.owner_id == from_slot
        ]
        ships = [
            {"ship_id": ship.ship_id, "info_turn": ship.info_turn,
             "fields": project_owned_entity_fields(
                 kind="ship", raw=ship.payload, scopes=scopes,
                 owner_slot_id=ship.owner_id, grantor_slot_id=from_slot,
             )}
            for ship in ship_rows if ship.owner_id == from_slot
        ]
        bases = [
            {"starbase_id": base.starbase_id, "info_turn": base.info_turn,
             "fields": project_owned_entity_fields(
                 kind="starbase", raw=base.payload, scopes=scopes,
                 owner_slot_id=planet_owners.get(base.planet_id),
                 grantor_slot_id=from_slot,
             )}
            for base in base_rows
            if planet_owners.get(base.planet_id) == from_slot
            and "starbase_orders_inventory" in scopes
        ]
        third_party = []
        if "third_party_contacts" in scopes:
            for item in planet_rows:
                if item.owner_id is not None and item.owner_id != from_slot:
                    third_party.append({
                        "kind": "planet", "id": item.planet_id,
                        "owner_id": item.owner_id, "info_turn": item.info_turn,
                        "x": item.x, "y": item.y,
                    })
            for item in ship_rows:
                if item.owner_id is not None and item.owner_id != from_slot:
                    third_party.append({
                        "kind": "ship", "id": item.ship_id,
                        "owner_id": item.owner_id, "info_turn": item.info_turn,
                        "x": item.x, "y": item.y,
                    })

        messages = []
        if "private_messages" in scopes:
            rows = session.execute(select(PrivateMessageObservation).where(
                PrivateMessageObservation.batch_id == batch.id,
            )).scalars().all()
            for item in rows:
                projected = project_private_message(
                    message_id=item.message_id, message_turn=item.message_turn,
                    owner_id=item.owner_id, target_id=item.target_id,
                    headline=item.headline, body=item.body, scopes=scopes,
                )
                if projected is not None:
                    messages.append(projected)

        combats = []
        if "combat_vcr_evidence" in scopes:
            for item in session.execute(select(CombatObservation).where(
                CombatObservation.batch_id == batch.id,
            )).scalars().all():
                combats.append({
                    "vcr_id": item.vcr_id, "battle_turn": item.battle_turn,
                    "battle_type": item.battle_type, "x": item.x, "y": item.y,
                    "left_owner_id": item.left_owner_id,
                    "right_owner_id": item.right_owner_id,
                    # Deliberately omit raw combat payload until its
                    # subfields receive an independent whitelist.
                })

        return {
            "game_id": game_id,
            "grant_id": grant.id,
            "mode": "unrestricted",
            "turn": turn,
            "source_batch_id": batch.id,
            "preview_only": True,
            "requested_scopes": sorted(scopes),
            "planets": [p for p in planets if p["fields"]],
            "ships": [s for s in ships if s["fields"]],
            "starbases": [b for b in bases if b["fields"]],
            "messages": messages,
            "combat_events": combats,
            "third_party_contacts": third_party,
        }

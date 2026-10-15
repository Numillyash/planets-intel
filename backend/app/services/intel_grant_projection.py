"""Projection of current-turn, source-owned observations through explicit scopes.

This function does not authorize access. Caller MUST verify grant, recipient,
game, turn, consent, revocation and the source observer before invocation.
Return only whitelisted data, never raw snapshots, private keys or third-party
correspondence.
"""
from typing import Any

from sqlalchemy import select

from app.models.planet_observation import PlanetObservation
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.models.private_message_observation import PrivateMessageObservation
from app.models.combat_observation import CombatObservation
from app.services.intel_disclosure_projection import (
    project_owned_entity_fields, project_private_message,
)


def project_current_grant_batch(
    session,
    *,
    batch,
    scopes: frozenset[str],
    grantor_slot: int,
    grantee_slot: int,
) -> dict[str, Any]:
    planets_data = session.execute(select(PlanetObservation).where(
        PlanetObservation.batch_id == batch.id,
    )).scalars().all()
    ships_data = session.execute(select(ShipObservation).where(
        ShipObservation.batch_id == batch.id,
    )).scalars().all()
    bases_data = session.execute(select(StarbaseObservation).where(
        StarbaseObservation.batch_id == batch.id,
    )).scalars().all()
    planet_owners = {p.planet_id: p.owner_id for p in planets_data}

    planets = [
        {
            "planet_id": p.planet_id, "owner_id": p.owner_id,
            "info_turn": p.info_turn,
            "fields": project_owned_entity_fields(
                kind="planet", raw=p.payload, scopes=scopes,
                owner_slot_id=p.owner_id, grantor_slot_id=grantor_slot,
            ),
        }
        for p in planets_data if p.owner_id == grantor_slot
    ]
    ships = [
        {
            "ship_id": s.ship_id, "owner_id": s.owner_id,
            "info_turn": s.info_turn,
            "fields": project_owned_entity_fields(
                kind="ship", raw=s.payload, scopes=scopes,
                owner_slot_id=s.owner_id, grantor_slot_id=grantor_slot,
            ),
        }
        for s in ships_data if s.owner_id == grantor_slot
    ]
    bases = [
        {
            "starbase_id": b.starbase_id, "planet_id": b.planet_id,
            "info_turn": b.info_turn,
            "fields": project_owned_entity_fields(
                kind="starbase", raw=b.payload, scopes=scopes,
                owner_slot_id=planet_owners.get(b.planet_id),
                grantor_slot_id=grantor_slot,
            ),
        }
        for b in bases_data
        if planet_owners.get(b.planet_id) == grantor_slot
        and "starbase_orders_inventory" in scopes
    ]

    # Third-party contacts never disclose underlying private payloads.
    third_party: list[dict[str, Any]] = []
    if "third_party_contacts" in scopes:
        for p in planets_data:
            if p.owner_id is not None and p.owner_id != grantor_slot:
                third_party.append({
                    "kind": "planet", "id": p.planet_id,
                    "owner_id": p.owner_id, "info_turn": p.info_turn,
                    "x": p.x, "y": p.y,
                })
        for s in ships_data:
            if s.owner_id is not None and s.owner_id != grantor_slot:
                third_party.append({
                    "kind": "ship", "id": s.ship_id,
                    "owner_id": s.owner_id, "info_turn": s.info_turn,
                    "x": s.x, "y": s.y,
                })

    # The owner can consent to their own message to the recipient only.
    # Messages involving third-party correspondents cannot be re-disclosed
    # merely because these two users checked "private messages".
    messages: list[dict[str, Any]] = []
    if "private_messages" in scopes:
        for m in session.execute(select(PrivateMessageObservation).where(
            PrivateMessageObservation.batch_id == batch.id,
        )).scalars().all():
            if (
                m.owner_id != grantor_slot
                or m.target_id != grantee_slot
                or m.message_turn != batch.turn
            ):
                continue
            projected = project_private_message(
                message_id=m.message_id, message_turn=m.message_turn,
                owner_id=m.owner_id, target_id=m.target_id,
                headline=m.headline, body=m.body, scopes=scopes,
            )
            if projected is not None:
                messages.append(projected)

    # VCR raw payload has additional unreviewed fields: only send metadata.
    combats: list[dict[str, Any]] = []
    if "combat_vcr_evidence" in scopes:
        for c in session.execute(select(CombatObservation).where(
            CombatObservation.batch_id == batch.id,
            CombatObservation.battle_turn == batch.turn,
        )).scalars().all():
            combats.append({
                "vcr_id": c.vcr_id, "battle_turn": c.battle_turn,
                "battle_type": c.battle_type, "x": c.x, "y": c.y,
                "left_owner_id": c.left_owner_id,
                "right_owner_id": c.right_owner_id,
            })

    return {
        "planets": [p for p in planets if p["fields"]],
        "ships": [s for s in ships if s["fields"]],
        "starbases": [b for b in bases if b["fields"]],
        "third_party_contacts": third_party,
        "messages": messages,
        "combat_events": combats,
    }

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.models.stellar_cartography_observation import (
    StellarCartographyObservation,
)
from app.services.payload_safety import (
    sanitize_observation_payload,
    sanitize_ship_observation_payload,
)


@dataclass
class _Snapshot:
    account: PlanetsAccount
    batch: PrivateObservationBatch
    planets: list[PlanetObservation]
    ships: list[ShipObservation]
    starbases: list[StarbaseObservation]
    stellar_cartography: list[StellarCartographyObservation]


def _load_latest_snapshot(
    session,
    *,
    account: PlanetsAccount,
    game_id: int,
) -> _Snapshot | None:
    batch = session.execute(
        select(PrivateObservationBatch)
        .where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.observer_planets_account_id == account.id,
        )
        .order_by(
            PrivateObservationBatch.turn.desc(),
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    if batch is None:
        return None

    planets = list(
        session.execute(
            select(PlanetObservation)
            .where(PlanetObservation.batch_id == batch.id)
            .order_by(PlanetObservation.planet_id)
        ).scalars().all()
    )
    ships = list(
        session.execute(
            select(ShipObservation)
            .where(ShipObservation.batch_id == batch.id)
            .order_by(ShipObservation.ship_id)
        ).scalars().all()
    )
    starbases = list(
        session.execute(
            select(StarbaseObservation)
            .where(StarbaseObservation.batch_id == batch.id)
            .order_by(StarbaseObservation.starbase_id)
        ).scalars().all()
    )
    stellar_cartography = list(
        session.execute(
            select(StellarCartographyObservation)
            .where(StellarCartographyObservation.batch_id == batch.id)
            .order_by(
                StellarCartographyObservation.feature_type,
                StellarCartographyObservation.feature_id,
            )
        ).scalars().all()
    )

    return _Snapshot(
        account=account,
        batch=batch,
        planets=planets,
        ships=ships,
        starbases=starbases,
        stellar_cartography=stellar_cartography,
    )


def _entity_freshness(
    snapshot: _Snapshot,
    item,
) -> tuple[int, int, Any, int]:
    effective_turn = (
        item.info_turn if item.info_turn is not None else snapshot.batch.turn
    )
    return (
        effective_turn,
        snapshot.batch.turn,
        snapshot.batch.observed_at,
        snapshot.batch.id,
    )


def _sorted_entries(entries):
    return sorted(
        entries,
        key=lambda entry: _entity_freshness(entry[0], entry[1]),
        reverse=True,
    )


def _provenance(snapshot: _Snapshot, item) -> dict[str, Any]:
    return {
        "linked_account_id": snapshot.account.id,
        "planets_username": snapshot.account.planets_username,
        "player_slot_id": snapshot.batch.source_player_slot_id,
        "batch_id": snapshot.batch.id,
        "batch_turn": snapshot.batch.turn,
        "info_turn": item.info_turn,
        "observed_at": snapshot.batch.observed_at,
    }


def _first_known(entries, attribute: str) -> tuple[Any, int | None]:
    for snapshot, item in _sorted_entries(entries):
        value = getattr(item, attribute)
        if value is not None:
            return value, snapshot.account.id
    return None, None


def _merge_payload(entries) -> tuple[dict[str, Any], dict[str, int]]:
    merged: dict[str, Any] = {}
    field_sources: dict[str, int] = {}

    for snapshot, item in _sorted_entries(entries):
        payload = sanitize_observation_payload(item.payload)
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if value is None or key in merged:
                continue
            merged[key] = value
            field_sources[f"payload.{key}"] = snapshot.account.id

    return merged, field_sources


def _merge_ship_payload(
    entries: list[tuple[_Snapshot, ShipObservation]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Merge ship payloads without turning hidden ammo into factual zeroes.

    Each source account may contribute generic private ammo only for a ship that
    source actually owns. This preserves legitimate multi-account sharing while
    keeping an enemy row's zero placeholder out of the factual union. VCR and
    deterministic replay ammunition remain separate evidence layers.
    """
    merged: dict[str, Any] = {}
    field_sources: dict[str, int] = {}

    for snapshot, item in _sorted_entries(entries):
        payload = sanitize_ship_observation_payload(
            item.payload,
            observer_slot_id=snapshot.batch.source_player_slot_id,
            owner_id=item.owner_id,
        )
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if value is None or key in merged:
                continue
            merged[key] = value
            field_sources[f"payload.{key}"] = snapshot.account.id

    return merged, field_sources


def _base_fields(
    entries,
    attributes: Iterable[str],
) -> tuple[dict[str, Any], dict[str, int]]:
    values: dict[str, Any] = {}
    field_sources: dict[str, int] = {}
    for attribute in attributes:
        value, source_account_id = _first_known(entries, attribute)
        values[attribute] = value
        if source_account_id is not None:
            field_sources[attribute] = source_account_id
    return values, field_sources


def _common_entity_metadata(entries) -> tuple[int, list[dict[str, Any]]]:
    sorted_entries = _sorted_entries(entries)
    selected_source = sorted_entries[0][0].account.id
    provenance = [
        _provenance(snapshot, item)
        for snapshot, item in sorted(
            entries,
            key=lambda entry: entry[0].account.id,
        )
    ]
    return selected_source, provenance


def _merge_planets(
    snapshots: list[_Snapshot],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[tuple[_Snapshot, PlanetObservation]]] = {}
    for snapshot in snapshots:
        for item in snapshot.planets:
            grouped.setdefault(item.planet_id, []).append((snapshot, item))

    result: list[dict[str, Any]] = []
    for planet_id in sorted(grouped):
        entries = grouped[planet_id]
        values, field_sources = _base_fields(
            entries,
            ("owner_id", "info_turn", "name", "x", "y"),
        )
        payload, payload_sources = _merge_payload(entries)
        field_sources.update(payload_sources)
        selected_source, provenance = _common_entity_metadata(entries)
        result.append(
            {
                "planet_id": planet_id,
                **values,
                "payload": payload,
                "selected_source_linked_account_id": selected_source,
                "field_sources": field_sources,
                "provenance": provenance,
            }
        )
    return result


def _merge_ships(
    snapshots: list[_Snapshot],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[tuple[_Snapshot, ShipObservation]]] = {}
    for snapshot in snapshots:
        for item in snapshot.ships:
            grouped.setdefault(item.ship_id, []).append((snapshot, item))

    result: list[dict[str, Any]] = []
    for ship_id in sorted(grouped):
        entries = grouped[ship_id]
        values, field_sources = _base_fields(
            entries,
            ("owner_id", "info_turn", "hull_id", "name", "x", "y", "warp"),
        )
        payload, payload_sources = _merge_ship_payload(entries)
        field_sources.update(payload_sources)
        selected_source, provenance = _common_entity_metadata(entries)
        result.append(
            {
                "ship_id": ship_id,
                **values,
                "payload": payload,
                "selected_source_linked_account_id": selected_source,
                "field_sources": field_sources,
                "provenance": provenance,
            }
        )
    return result


def _merge_starbases(
    snapshots: list[_Snapshot],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[tuple[_Snapshot, StarbaseObservation]]] = {}
    for snapshot in snapshots:
        for item in snapshot.starbases:
            grouped.setdefault(item.starbase_id, []).append((snapshot, item))

    result: list[dict[str, Any]] = []
    for starbase_id in sorted(grouped):
        entries = grouped[starbase_id]
        values, field_sources = _base_fields(
            entries,
            ("planet_id", "race_id", "info_turn"),
        )
        payload, payload_sources = _merge_payload(entries)
        field_sources.update(payload_sources)
        selected_source, provenance = _common_entity_metadata(entries)
        result.append(
            {
                "starbase_id": starbase_id,
                **values,
                "payload": payload,
                "selected_source_linked_account_id": selected_source,
                "field_sources": field_sources,
                "provenance": provenance,
            }
        )
    return result


def _merge_stellar_cartography(
    snapshots: list[_Snapshot],
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, int],
        list[tuple[_Snapshot, StellarCartographyObservation]],
    ] = {}
    for snapshot in snapshots:
        for item in snapshot.stellar_cartography:
            key = (item.feature_type, item.feature_id)
            grouped.setdefault(key, []).append((snapshot, item))

    result: list[dict[str, Any]] = []
    for feature_type, feature_id in sorted(grouped):
        entries = grouped[(feature_type, feature_id)]
        values, field_sources = _base_fields(
            entries,
            ("name", "info_turn", "x", "y", "radius"),
        )
        payload, payload_sources = _merge_payload(entries)
        field_sources.update(payload_sources)
        selected_source, provenance = _common_entity_metadata(entries)
        result.append(
            {
                "feature_type": feature_type,
                "feature_id": feature_id,
                **values,
                "payload": payload,
                "selected_source_linked_account_id": selected_source,
                "field_sources": field_sources,
                "provenance": provenance,
            }
        )
    return result


def _combined_result(
    *,
    game_id: int,
    primary_account: PlanetsAccount,
    primary_snapshot: _Snapshot,
    snapshots: list[_Snapshot],
) -> dict[str, Any]:
    planets = _merge_planets(snapshots)
    ships = _merge_ships(snapshots)
    starbases = _merge_starbases(snapshots)
    stellar_cartography = _merge_stellar_cartography(snapshots)

    feature_counts = {
        "nebula": 0,
        "ion_storm": 0,
        "star_cluster": 0,
    }
    for item in stellar_cartography:
        feature_type = item["feature_type"]
        if feature_type in feature_counts:
            feature_counts[feature_type] += 1

    return {
        "mode": "combined",
        "aggregation_policy": "freshest_field_union",
        "game_id": game_id,
        "turn": max(snapshot.batch.turn for snapshot in snapshots),
        "primary_observer": {
            "linked_account_id": primary_account.id,
            "planets_account_id": primary_account.planets_account_id,
            "planets_username": primary_account.planets_username,
            "player_slot_id": primary_snapshot.batch.source_player_slot_id,
            "is_active": primary_account.is_active,
        },
        "sources": [
            {
                "linked_account_id": snapshot.account.id,
                "planets_account_id": snapshot.account.planets_account_id,
                "planets_username": snapshot.account.planets_username,
                "player_slot_id": snapshot.batch.source_player_slot_id,
                "batch_id": snapshot.batch.id,
                "turn": snapshot.batch.turn,
                "source": snapshot.batch.source,
                "observed_at": snapshot.batch.observed_at,
            }
            for snapshot in snapshots
        ],
        "counts": {
            "planets": len(planets),
            "ships": len(ships),
            "starbases": len(starbases),
            "nebulas": feature_counts["nebula"],
            "ion_storms": feature_counts["ion_storm"],
            "star_clusters": feature_counts["star_cluster"],
        },
        "planets": planets,
        "ships": ships,
        "starbases": starbases,
        "stellar_cartography": stellar_cartography,
    }


def get_combined_private_intel(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    """Legacy entry point delegates to the P0 selected-observer guard."""
    from app.services.accessible_combined_intel import (
        get_accessible_combined_private_intel,
    )

    return get_accessible_combined_private_intel(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
    )

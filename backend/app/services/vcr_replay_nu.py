"""Planets.nu catalog adapter for deterministic VCR replay.

The core replay engine intentionally deals with normalized weapon specs.
This adapter owns Planets.nu's actual RST field names and semantics.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from app.services.vcr_replay import (
    ReplayUnsupported,
    combat_rng_from_settings,
    replay_nuhost_classic,
)


def _integer(record: Mapping[str, Any], key: str) -> int | None:
    value = record.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def normalize_nu_beams(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, int]]:
    """Convert Planets.nu beam records to replay-core weapon fields."""

    result: list[dict[str, int]] = []
    for record in records:
        component_id = _integer(record, "id")
        damage = _integer(record, "damage")
        crewkill = _integer(record, "crewkill")
        if component_id is None or damage is None or crewkill is None:
            continue
        result.append(
            {
                "id": component_id,
                "damage": damage,
                "kill": crewkill,
            }
        )
    return result


def normalize_nu_torpedoes(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, int]]:
    """Convert Planets.nu torpedo records to replay-core weapon fields."""

    result: list[dict[str, int]] = []
    for record in records:
        component_id = _integer(record, "id")
        damage = _integer(record, "damage")
        crewkill = _integer(record, "crewkill")
        if component_id is None or damage is None or crewkill is None:
            continue

        combat_range = _integer(record, "combatrange")
        if combat_range is not None and combat_range != 0:
            range_bonus = combat_range - 300
        elif component_id == 11:
            range_bonus = 40
        else:
            range_bonus = 0

        result.append(
            {
                "id": component_id,
                "damage": damage,
                "kill": crewkill,
                "firingrangebonus": range_bonus,
            }
        )
    return result


def _without_lizard_planet_damage_bonus(
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Neutralize only the Lizard 150% survival rule for ship-vs-planet.

    Planets.nu still reports the attacking ship's factual race id in the VCR,
    but the Lizard Crew Bonus explicitly does not allow survival past 100%
    damage against a planet. The classic core currently derives its damage
    limit from ``raceid``; supplying a replay-only neutral race here preserves
    every other factual combat field while selecting the correct limit.
    """

    raw_left = payload.get("left")
    raw_right = payload.get("right")
    if not isinstance(raw_left, Mapping) or not isinstance(raw_right, Mapping):
        return payload
    if _integer(raw_right, "hullid") is None or int(raw_right.get("hullid", 1)) > 0:
        return payload
    if _integer(raw_left, "raceid") != 2:
        return payload

    adjusted = deepcopy(dict(payload))
    adjusted_left = adjusted.get("left")
    if isinstance(adjusted_left, dict):
        adjusted_left["raceid"] = 0
    return adjusted


def replay_nuhost_from_nu_catalog(
    payload: Mapping[str, Any],
    *,
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay a Nu VCR using the persisted Planets.nu game rule catalog."""

    combat_rng = combat_rng_from_settings(settings)
    if combat_rng is None:
        raise ReplayUnsupported(
            "game rule catalog does not contain combatrng; exact replay is unavailable"
        )

    return replay_nuhost_classic(
        _without_lizard_planet_damage_bonus(payload),
        beams=normalize_nu_beams(beams),
        torpedoes=normalize_nu_torpedoes(torpedoes),
        combat_rng=combat_rng,
    )

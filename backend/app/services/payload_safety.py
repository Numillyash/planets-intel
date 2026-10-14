from typing import Any


SENSITIVE_OBSERVATION_KEYS = frozenset(
    {
        "apikey",
        "password",
        "savekey",
        "gamepassword",
        "email",
    }
)

# Planets.nu private ship rows use a generic ``ammo`` count for carried combat
# ammunition. For the observing player's own ships this is factual. Foreign
# ship rows can contain zero placeholders for loadout fields that were never
# disclosed. Raw observations stay untouched; these rules apply to read models.
ENEMY_PRIVATE_AMMO_KEYS = frozenset(
    {
        "ammo",
        "fighters",
        "torpedoes",
        "transferammo",
    }
)

# Foreign private ship rows can also carry tactical zero placeholders for
# undisclosed installed equipment. A zero from the ship owner remains a known
# factual zero, and a positive foreign value remains usable disclosure; only an
# ambiguous non-owner zero is removed from the factual read model. Hull catalog
# capacity is a separate capability layer and is never inferred from these
# fields.
ENEMY_PRIVATE_ZERO_LOADOUT_KEYS = frozenset(
    {
        "beams",
        "beamcount",
        "beam_count",
        "beamid",
        "beam_id",
        "tubes",
        "torpedotubes",
        "tube_count",
        "launchercount",
        "launcher_count",
        "torpedoid",
        "torpedo_id",
        "bays",
        "fighterbays",
        "baycount",
        "bay_count",
    }
)

# A partial foreign ship row normally exposes positional/mass information while
# keeping tactical internals at the Nu sentinel value -1. Seeing any of these
# sentinels is enough to reject generic ammo zeroes from a context-free factual
# view. The owner-aware sanitizer below is the stronger rule used where the
# observer slot is available.
SHIP_DISCLOSURE_SENTINEL_KEYS = frozenset(
    {
        "crew",
        "damage",
        "beamid",
        "engineid",
        "torpedoid",
    }
)


def _is_undisclosed_sentinel(value: Any) -> bool:
    """Return True for Planets.nu placeholders that are not factual values."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int) and value == -1:
        return True
    if isinstance(value, float) and value == -1.0:
        return True
    if isinstance(value, str) and value.strip() in {"???", "-1"}:
        return True
    return False


def _is_zero_placeholder(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            return float(text) == 0
        except ValueError:
            return False
    return False


def _looks_like_partially_hidden_ship(payload: dict[str, Any]) -> bool:
    for key, item in payload.items():
        if (
            str(key).lower() in SHIP_DISCLOSURE_SENTINEL_KEYS
            and _is_undisclosed_sentinel(item)
        ):
            return True
    return False


def sanitize_observation_payload(value: Any) -> Any:
    if isinstance(value, dict):
        hidden_ship = _looks_like_partially_hidden_ship(value)
        return {
            key: sanitize_observation_payload(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_OBSERVATION_KEYS
            and not _is_undisclosed_sentinel(item)
            and not (
                hidden_ship
                and str(key).lower() in ENEMY_PRIVATE_AMMO_KEYS
            )
        }

    if isinstance(value, list):
        return [sanitize_observation_payload(item) for item in value]

    return value


def sanitize_ship_observation_payload(
    value: Any,
    *,
    observer_slot_id: int | None,
    owner_id: int | None,
) -> Any:
    """Sanitize one ship payload while preserving disclosure semantics.

    Generic/private ammo is trustworthy when the observing player owns the
    ship. For another owner, omit private ammo and ambiguous tactical zero
    placeholders. Positive equipment disclosures remain available, while VCR
    evidence can independently supply combat-revealed equipment.
    """
    sanitized = sanitize_observation_payload(value)
    if not isinstance(sanitized, dict):
        return sanitized

    if (
        observer_slot_id is not None
        and owner_id is not None
        and observer_slot_id == owner_id
    ):
        return sanitized

    return {
        key: item
        for key, item in sanitized.items()
        if str(key).lower() not in ENEMY_PRIVATE_AMMO_KEYS
        and not (
            str(key).lower() in ENEMY_PRIVATE_ZERO_LOADOUT_KEYS
            and _is_zero_placeholder(item)
        )
    }

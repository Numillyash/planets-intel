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

# Planets.nu private ship rows use a generic ``ammo`` count for the ship's
# carried combat ammunition.  For the observing player's own ships this is a
# factual value.  Enemy rows can contain zero placeholders for loadout fields
# that are not actually disclosed, so those values must not enter the combined
# factual read model.  Combat/VCR evidence is stored and exposed separately.
ENEMY_PRIVATE_AMMO_KEYS = frozenset(
    {
        "ammo",
        "fighters",
        "torpedoes",
        "transferammo",
    }
)


def _is_undisclosed_sentinel(value: Any) -> bool:
    """Return True for Planets.nu placeholders that are not factual values.

    Private turn objects can contain ``-1`` or ``???`` for fields the current
    observer is not allowed to know. Keeping those values in a combined
    freshest-field union incorrectly lets a newer partial observation mask an
    older real observation. Stored raw observations remain unchanged; this is
    only the safe/read-model representation returned to clients and mergers.
    """
    if isinstance(value, bool):
        return False

    if isinstance(value, int) and value == -1:
        return True

    if isinstance(value, float) and value == -1.0:
        return True

    if isinstance(value, str) and value.strip() in {"???", "-1"}:
        return True

    return False


def sanitize_observation_payload(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_observation_payload(item)
            for key, item in value.items()
            if str(key).lower()
            not in SENSITIVE_OBSERVATION_KEYS
            and not _is_undisclosed_sentinel(item)
        }

    if isinstance(value, list):
        return [
            sanitize_observation_payload(item)
            for item in value
        ]

    return value


def sanitize_ship_observation_payload(
    value: Any,
    *,
    observer_slot_id: int | None,
    owner_id: int | None,
) -> Any:
    """Sanitize one ship payload while preserving ammo disclosure semantics.

    Raw observations are immutable.  This helper is only for factual read
    models.  Generic/private ammo fields are trustworthy when the observing
    player owns the ship.  For other owners, a zero can be an undisclosed
    placeholder, so omit the field entirely and let VCR/replay evidence carry
    any actually revealed combat ammunition.
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
    }

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

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


def sanitize_observation_payload(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_observation_payload(item)
            for key, item in value.items()
            if str(key).lower()
            not in SENSITIVE_OBSERVATION_KEYS
        }

    if isinstance(value, list):
        return [
            sanitize_observation_payload(item)
            for item in value
        ]

    return value

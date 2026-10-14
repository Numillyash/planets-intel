from typing import Any

from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


COMMON_HEADERS = {
    "Origin": "https://planets.nu",
    "Referer": "https://planets.nu/",
    "User-Agent": "Mozilla/5.0",
}


def _parse_activity(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise PlanetsNuError(f"Planets.nu {label} response is not an object")
    if payload.get("success") is False:
        raise PlanetsNuError(str(payload.get("error", f"Planets.nu {label} failed")))
    activity = payload.get("activity")
    if not isinstance(activity, list):
        raise PlanetsNuError(f"Planets.nu {label} response has no activity list")
    if not all(isinstance(item, dict) for item in activity):
        raise PlanetsNuError(f"Planets.nu {label} contains invalid records")
    return activity


async def load_ingame_activity(
    client: PlanetsNuClient,
    *,
    api_key: str,
    game_id: int,
    player_id: int,
    planets_account_id: int | None,
) -> list[dict[str, Any]]:
    data: dict[str, Any] = {
        "apikey": api_key,
        "gameid": game_id,
        "playerid": player_id,
    }
    if planets_account_id is not None:
        data["accountid"] = planets_account_id

    payload = await client.post_form(
        "account/ingameactivity",
        data=data,
        headers=COMMON_HEADERS,
        use_proxy=True,
    )
    return _parse_activity(payload, "ingameactivity")


async def load_private_activity(
    client: PlanetsNuClient,
    *,
    api_key: str,
    game_id: int,
    player_id: int,
    planets_account_id: int | None,
) -> list[dict[str, Any]]:
    data: dict[str, Any] = {
        "apikey": api_key,
        "gameid": game_id,
        "playerid": player_id,
    }
    if planets_account_id is not None:
        data["accountid"] = planets_account_id

    payload = await client.post_form(
        "account/privateactivity",
        data=data,
        headers=COMMON_HEADERS,
        use_proxy=True,
    )
    return _parse_activity(payload, "privateactivity")

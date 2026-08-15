from typing import Any

from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


COMMON_HEADERS = {
    "Origin": "https://planets.nu",
    "Referer": "https://planets.nu/",
    "User-Agent": "Mozilla/5.0",
}


async def load_ingame_activity(
    client: PlanetsNuClient,
    *,
    api_key: str,
    game_id: int,
    player_id: int,
    planets_account_id: int | None,
) -> list[dict[str, Any]]:
    """Load the observer-visible in-game activity feed from Planets.nu."""

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
    if not isinstance(payload, dict):
        raise PlanetsNuError(
            "Planets.nu ingameactivity response is not an object"
        )
    if payload.get("success") is False:
        raise PlanetsNuError(
            str(payload.get("error", "Planets.nu ingameactivity failed"))
        )

    activity = payload.get("activity")
    if not isinstance(activity, list):
        raise PlanetsNuError(
            "Planets.nu ingameactivity response has no activity list"
        )
    if not all(isinstance(item, dict) for item in activity):
        raise PlanetsNuError(
            "Planets.nu ingameactivity contains invalid records"
        )

    return activity

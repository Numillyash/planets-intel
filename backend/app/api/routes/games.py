from typing import Any

from fastapi import APIRouter, HTTPException, Path

from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.schemas.games import (
    GameDetailsResponse,
    GameInfo,
    GameSettingsInfo,
    PlayerInfo,
    RelationInfo,
)


router = APIRouter(
    prefix="/games",
)


def build_game_info(raw: dict[str, Any]) -> GameInfo:
    return GameInfo(
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        short_description=raw["shortdescription"],
        status_id=raw["status"],
        status_name=raw["statusname"],
        turn=raw["turn"],
        slots=raw["slots"],
        next_host=raw["nexthost"],
        turns_per_week=raw["turnsperweek"],
        is_private=raw["isprivate"],
        is_custom=raw["iscustom"],
        win_condition_id=raw["wincondition"],
    )


def build_settings_info(
    raw: dict[str, Any],
) -> GameSettingsInfo:
    return GameSettingsInfo(
        turn=raw["turn"],
        map_width=raw["mapwidth"],
        map_height=raw["mapheight"],
        map_shape=raw["mapshape"],
        num_planets=raw["numplanets"],
        ship_limit=raw["shiplimit"],
        planet_scan_range=raw["planetscanrange"],
        ship_scan_range=raw["shipscanrange"],
        max_allies=raw["maxallies"],
        max_share_intel=raw["maxshareintel"],
        max_safe_passage=raw["maxsafepassage"],
        all_visible=raw["allvisible"],
        all_planets_visible=raw["allplanetsvisible"],
        planet_ownership_visible=raw["planetownershipvisible"],
        starbases_visible=raw["starbasesvisible"],
        ships_at_planets_visible=raw["shipsatplanetsvisible"],
        minefields_visible=raw["minefieldsvisible"],
        all_wormholes_visible=raw["allwormholesvisible"],
        unlimited_fuel=raw["unlimitedfuel"],
        unlimited_ammo=raw["unlimitedammo"],
        no_supplies=raw["nosupplies"],
        military_score_percent=raw["militaryscorepercent"],
        production_queue=raw["productionqueue"],
        planetary_production_queue=raw[
            "planetaryproductionqueue"
        ],
        fight_or_fail=raw["fightorfail"],
        fof_active_turn=raw["fofactiveturn"],
        fof_increment=raw["fofincrement"],
        nebulas=raw["nebulas"],
        stars=raw["stars"],
        max_wormholes=raw["maxwormholes"],
        wormhole_scan_range=raw["wormholescanrange"],
    )


def build_player_info(
    raw: dict[str, Any],
) -> PlayerInfo:
    return PlayerInfo(
        slot_id=raw["id"],
        account_id=raw["accountid"],
        username=raw["username"],
        race_id=raw["raceid"],
        status=raw["status"],
        turn_status=raw["turnstatus"],
        planets=raw["planets"],
        ships=raw["ships"],
        starbases=raw["starbases"],
        turn_ready=raw["turnready"],
    )


def build_relation_info(
    raw: dict[str, Any],
) -> RelationInfo:
    return RelationInfo(
        id=raw["id"],
        player_id=raw["playerid"],
        player_to_id=raw["playertoid"],
        relation_to=raw["relationto"],
        relation_from=raw["relationfrom"],
        conflict_level=raw["conflictlevel"],
        color=raw["color"],
    )


@router.get(
    "/{game_id}",
    response_model=GameDetailsResponse,
)
async def get_game(
    game_id: int = Path(gt=0),
) -> GameDetailsResponse:
    try:
        payload = await PlanetsNuClient().load_info(game_id)
    except PlanetsNuError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    game_raw = payload.get("game")
    settings_raw = payload.get("settings")
    players_raw = payload.get("players")
    relations_raw = payload.get("relations")

    if not isinstance(game_raw, dict):
        raise HTTPException(
            status_code=502,
            detail="Invalid game object from Planets.nu",
        )

    if game_raw.get("id") != game_id:
        raise HTTPException(
            status_code=502,
            detail="Planets.nu returned a different game id",
        )

    if not isinstance(settings_raw, dict):
        raise HTTPException(
            status_code=502,
            detail="Invalid settings object from Planets.nu",
        )

    if not isinstance(players_raw, list):
        raise HTTPException(
            status_code=502,
            detail="Invalid players list from Planets.nu",
        )

    if not isinstance(relations_raw, list):
        raise HTTPException(
            status_code=502,
            detail="Invalid relations list from Planets.nu",
        )

    try:
        return GameDetailsResponse(
            game=build_game_info(game_raw),
            settings=build_settings_info(settings_raw),
            players=[
                build_player_info(player)
                for player in players_raw
            ],
            relations=[
                build_relation_info(relation)
                for relation in relations_raw
            ],
            schedule=str(payload.get("schedule", "")),
            time_to_host=str(payload.get("timetohost", "")),
            year_from=str(payload.get("yearfrom", "")),
            year_to=str(payload.get("yearto", "")),
            win_condition=str(payload.get("wincondition", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Planets.nu loadinfo response does not match "
                "the expected schema"
            ),
        ) from exc

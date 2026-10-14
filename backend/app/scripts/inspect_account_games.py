import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


INTERESTING_PLAYER_FIELD_TOKENS = (
    "turn",
    "miss",
    "drop",
    "status",
    "ready",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect games belonging to a linked Planets.nu account and, "
            "optionally, compare games/list with loadinfo turn-state sources."
        )
    )

    parser.add_argument(
        "account_id",
        type=int,
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Print a slot-by-slot public turn-state diagnostic for this game.",
    )

    return parser.parse_args()


def _marker(turnstatus: object, slot_id: int) -> str | None:
    if not isinstance(turnstatus, str):
        return None
    if slot_id <= 0 or slot_id > len(turnstatus):
        return None
    return turnstatus[slot_id - 1]


def _interesting_player_fields(player: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(player.items())
        if any(token in key.casefold() for token in INTERESTING_PLAYER_FIELD_TOKENS)
    }


def _print_turn_state_diagnostic(
    *,
    game_list_record: dict[str, Any],
    load_info: dict[str, Any],
) -> None:
    game = load_info.get("game")
    players = load_info.get("players")
    if not isinstance(game, dict) or not isinstance(players, list):
        print("loadinfo diagnostic unavailable: invalid game/players payload")
        return

    list_turnstatus = game_list_record.get("turnstatus")
    info_turnstatus = game.get("turnstatus")
    print()
    print("===== TURN STATE DIAGNOSTIC =====")
    print(f"games/list turn: {game_list_record.get('turn')!r}")
    print(f"loadinfo turn:   {game.get('turn')!r}")
    print(f"games/list game.turnstatus: {list_turnstatus!r}")
    print(f"loadinfo game.turnstatus:   {info_turnstatus!r}")
    print()

    for raw in sorted(
        (item for item in players if isinstance(item, dict)),
        key=lambda item: item.get("id", 0),
    ):
        slot_id = raw.get("id")
        if isinstance(slot_id, bool) or not isinstance(slot_id, int) or slot_id <= 0:
            continue
        print(
            "slot={slot} list_marker={list_marker!r} info_marker={info_marker!r} "
            "username={username!r} race={race!r} status={status!r} "
            "turnready={turnready!r} player_turnstatus={player_turnstatus!r}".format(
                slot=slot_id,
                list_marker=_marker(list_turnstatus, slot_id),
                info_marker=_marker(info_turnstatus, slot_id),
                username=raw.get("username"),
                race=raw.get("raceid"),
                status=raw.get("status"),
                turnready=raw.get("turnready"),
                player_turnstatus=raw.get("turnstatus"),
            )
        )
        interesting = _interesting_player_fields(raw)
        print("  relevant_raw_fields=" + json.dumps(
            interesting,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ))


def _print_game_record(game: dict[str, Any]) -> None:
    print(
        "game_id={id} "
        "turn={turn} "
        "status={status} "
        "status_name={statusname!r} "
        "turnstatus={turnstatus!r} "
        "name={name!r}".format(
            id=game.get("id"),
            turn=game.get("turn"),
            status=game.get("status"),
            statusname=game.get("statusname"),
            turnstatus=game.get("turnstatus"),
            name=game.get("name"),
        )
    )


async def run() -> None:
    args = parse_args()

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == args.account_id
            )
        ).scalar_one_or_none()

        if account is None:
            raise SystemExit("linked Planets.nu account not found")

        username = account.planets_username

    client = PlanetsNuClient()
    games = await client.games_for_username(username)

    print(f"account_id: {args.account_id}")
    print(f"username: {username}")
    print(f"games: {len(games)}")
    print()

    for game in sorted(
        games,
        key=lambda item: (
            item.get("status", -1),
            item.get("id", 0),
        ),
        reverse=True,
    ):
        _print_game_record(game)

    if args.game_id is None:
        return

    selected = next(
        (
            game
            for game in games
            if isinstance(game, dict) and game.get("id") == args.game_id
        ),
        None,
    )
    if selected is None:
        raise SystemExit(
            f"game {args.game_id} is not present in games/list for {username!r}"
        )

    load_info = await client.load_info(args.game_id)
    _print_turn_state_diagnostic(
        game_list_record=selected,
        load_info=load_info,
    )


if __name__ == "__main__":
    asyncio.run(run())

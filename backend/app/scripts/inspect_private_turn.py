import argparse
import asyncio
from typing import Any

from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import (
    PlanetsNuClient,
    PlanetsNuError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the structure of a private Planets.nu turn "
            "using a linked account."
        )
    )

    parser.add_argument(
        "account_id",
        type=int,
        help="Local linked planets_accounts.id",
    )

    parser.add_argument(
        "game_id",
        type=int,
    )

    return parser.parse_args()


def describe(
    name: str,
    value: Any,
) -> None:
    if isinstance(value, list):
        print(
            f"{name}: list[{len(value)}]"
        )

        if value and isinstance(
            value[0],
            dict,
        ):
            keys = sorted(
                value[0].keys()
            )

            print(
                f"  first-item keys: "
                f"{', '.join(keys)}"
            )

        return

    if isinstance(value, dict):
        print(
            f"{name}: dict[{len(value)}]"
        )

        print(
            "  keys: "
            + ", ".join(
                sorted(value.keys())
            )
        )

        return

    print(
        f"{name}: {type(value).__name__}"
    )


async def run() -> None:
    args = parse_args()

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id
                == args.account_id,
                PlanetsAccount.is_active.is_(
                    True
                ),
            )
        ).scalar_one_or_none()

        if account is None:
            raise SystemExit(
                "linked Planets.nu account not found"
            )

        username = account.planets_username

        encrypted_api_key = (
            account.api_key_encrypted
        )

    client = PlanetsNuClient()

    info = await client.load_info(
        args.game_id
    )

    players = info.get("players")

    if not isinstance(players, list):
        raise PlanetsNuError(
            "loadinfo has no players list"
        )

    normalized_username = (
        username.strip().casefold()
    )

    matches = [
        player
        for player in players
        if isinstance(player, dict)
        and isinstance(
            player.get("username"),
            str,
        )
        and player["username"]
        .strip()
        .casefold()
        == normalized_username
    ]

    if len(matches) != 1:
        raise SystemExit(
            "could not uniquely resolve "
            f"{username!r} in game "
            f"{args.game_id}: "
            f"matches={len(matches)}"
        )

    player = matches[0]

    player_id = player.get("id")
    planets_account_id = (
        player.get("accountid")
    )

    if not isinstance(player_id, int):
        raise SystemExit(
            "resolved player has no valid slot id"
        )

    api_key = decrypt_credential(
        encrypted_api_key
    )

    try:
        payload = await client.load_turn(
            game_id=args.game_id,
            api_key=api_key,
        )

    finally:
        del api_key

    rst = payload["rst"]

    print(
        f"linked_account_id: {args.account_id}"
    )

    print(
        f"username: {username}"
    )

    print(
        f"game_id: {args.game_id}"
    )

    print(
        f"player_id: {player_id}"
    )

    print(
        f"planets_account_id: {planets_account_id}"
    )

    print(
        f"success: {payload.get('success')}"
    )

    print()
    print("===== TOP LEVEL =====")

    for key in sorted(
        payload.keys()
    ):
        if key in {
            "savekey",
            "rst",
        }:
            continue

        describe(
            key,
            payload[key],
        )

    print()
    print("===== RST =====")

    for key in sorted(
        rst.keys()
    ):
        describe(
            key,
            rst[key],
        )


if __name__ == "__main__":
    asyncio.run(run())

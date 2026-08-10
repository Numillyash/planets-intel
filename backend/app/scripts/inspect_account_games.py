import argparse
import asyncio

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect games belonging to a linked "
            "Planets.nu account."
        )
    )

    parser.add_argument(
        "account_id",
        type=int,
    )

    return parser.parse_args()


async def run() -> None:
    args = parse_args()

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id
                == args.account_id
            )
        ).scalar_one_or_none()

        if account is None:
            raise SystemExit(
                "linked Planets.nu account not found"
            )

        username = account.planets_username

    client = PlanetsNuClient()

    games = await client.games_for_username(
        username
    )

    print(
        f"account_id: {args.account_id}"
    )
    print(
        f"username: {username}"
    )
    print(
        f"games: {len(games)}"
    )
    print()

    for game in sorted(
        games,
        key=lambda item: (
            item.get("status", -1),
            item.get("id", 0),
        ),
        reverse=True,
    ):
        print(
            "game_id={id} "
            "turn={turn} "
            "status={status} "
            "status_name={statusname!r} "
            "name={name!r}".format(
                id=game.get("id"),
                turn=game.get("turn"),
                status=game.get("status"),
                statusname=game.get(
                    "statusname"
                ),
                name=game.get("name"),
            )
        )


if __name__ == "__main__":
    asyncio.run(run())

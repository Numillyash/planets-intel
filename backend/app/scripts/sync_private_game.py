import argparse
import asyncio
import json

from app.services.private_sync import (
    sync_private_game,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync one private Planets.nu game turn "
            "through a linked account."
        )
    )

    parser.add_argument(
        "linked_account_id",
        type=int,
    )

    parser.add_argument(
        "game_id",
        type=int,
    )

    return parser.parse_args()


async def run() -> None:
    args = parse_args()

    result = await sync_private_game(
        linked_account_id=(
            args.linked_account_id
        ),
        game_id=args.game_id,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(run())

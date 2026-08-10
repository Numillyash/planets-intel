import argparse
import asyncio
import json

from app.services.public_sync import sync_public_game


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize public Planets.nu game metadata "
            "and score history."
        )
    )

    parser.add_argument(
        "game_id",
        type=int,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.game_id <= 0:
        raise SystemExit("game_id must be positive")

    result = asyncio.run(
        sync_public_game(args.game_id)
    )

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

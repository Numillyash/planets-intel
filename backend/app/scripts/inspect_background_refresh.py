import argparse
import asyncio
import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.services.background_private_refresh import (
    deduplicate_private_refresh_targets,
    refresh_all_running_private_intel_once,
    running_private_refresh_targets,
)
from app.services.private_refresh import accessible_refresh_account_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect backend-owned private-refresh targets and dedup signatures. "
            "Use --run to execute one normal scheduler iteration."
        )
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute one refresh iteration after printing the target plan.",
    )
    return parser.parse_args()


def _game_metadata(game_ids: set[int]) -> dict[int, dict[str, object]]:
    if not game_ids:
        return {}
    with SessionLocal() as session:
        rows = session.execute(
            select(Game).where(Game.id.in_(sorted(game_ids)))
        ).scalars().all()
    return {
        int(game.id): {
            "name": game.name,
            "turn": game.current_turn,
            "status_id": game.status_id,
            "status_name": game.status_name,
        }
        for game in rows
    }


def print_plan() -> None:
    raw = running_private_refresh_targets()
    deduplicated = deduplicate_private_refresh_targets(raw)
    games = _game_metadata({game_id for _, game_id in raw})

    print("===== BACKGROUND PRIVATE REFRESH PLAN =====")
    print(f"raw_targets={len(raw)} deduplicated_targets={len(deduplicated)}")
    print()

    retained = set(deduplicated)
    for user_id, game_id in raw:
        game = games.get(game_id, {})
        observer_ids = accessible_refresh_account_ids(user_id)
        state = "RUN" if (user_id, game_id) in retained else "DEDUP"
        print(
            f"{state} user={user_id} game={game_id} "
            f"status={game.get('status_name')!r} turn={game.get('turn')!r} "
            f"observers={observer_ids} name={game.get('name')!r}"
        )


async def run() -> None:
    args = parse_args()
    print_plan()
    if not args.run:
        return

    print()
    print("===== EXECUTING ONE NORMAL ITERATION =====")
    result = await refresh_all_running_private_intel_once()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(run())

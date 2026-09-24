import argparse
import asyncio
import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.private_observation_batch import PrivateObservationBatch
from app.planetsnu.client import PlanetsNuClient
from app.services.background_private_refresh import (
    deduplicate_private_refresh_targets,
    running_private_refresh_targets,
)
from app.services.private_refresh import (
    accessible_refresh_account_ids,
    refresh_accessible_private_intel,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def latest_turn(game_id, account_id):
    with SessionLocal() as session:
        return session.execute(
            select(PrivateObservationBatch.turn)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id == account_id,
            )
            .order_by(
                PrivateObservationBatch.turn.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()


def game_turn(game_id):
    with SessionLocal() as session:
        row = session.execute(
            select(Game.current_turn, Game.name).where(Game.id == game_id)
        ).one_or_none()
    if row is None:
        return None, None
    return row[0], row[1]


def build_targets():
    raw = running_private_refresh_targets()
    targets = deduplicate_private_refresh_targets(raw)
    result = []
    for user_id, game_id in targets:
        turn, name = game_turn(game_id)
        observer_ids = accessible_refresh_account_ids(user_id)
        latest = {
            account_id: latest_turn(game_id, account_id)
            for account_id in observer_ids
        }
        stale = [
            account_id
            for account_id, observed_turn in latest.items()
            if turn is not None and (observed_turn is None or observed_turn < turn)
        ]
        result.append(
            {
                "user_id": user_id,
                "game_id": game_id,
                "game_name": name,
                "canonical_turn": turn,
                "observer_latest_turns": latest,
                "stale_observers": stale,
            }
        )
    return result


async def main():
    args = parse_args()
    targets = build_targets()

    print("===== STALE PRIVATE TARGETS =====", flush=True)
    stale_targets = [item for item in targets if item["stale_observers"]]
    for item in stale_targets:
        print(json.dumps(item, ensure_ascii=False, sort_keys=True), flush=True)

    selected = None
    if args.game_id is not None:
        selected = next(
            (item for item in targets if item["game_id"] == args.game_id),
            None,
        )
        if selected is None:
            print("DIAGNOSIS=requested_game_not_in_refresh_targets", flush=True)
            raise SystemExit(2)
    elif stale_targets:
        selected = sorted(
            stale_targets,
            key=lambda item: (
                -(item["canonical_turn"] or 0),
                item["game_id"],
                item["user_id"],
            ),
        )[0]

    if selected is None:
        print("DIAGNOSIS=no_stale_private_targets", flush=True)
        return

    print("", flush=True)
    print("===== SELECTED TARGET =====", flush=True)
    print(json.dumps(selected, ensure_ascii=False, sort_keys=True), flush=True)

    print("", flush=True)
    print("===== BACKEND PROXY PROBE =====", flush=True)
    try:
        probe = await asyncio.wait_for(
            PlanetsNuClient().get("time", params={"version": 1}),
            timeout=min(args.timeout, 30),
        )
        print("backend_proxy_probe=OK", flush=True)
        print(json.dumps(probe, ensure_ascii=False, default=str), flush=True)
    except Exception as exc:
        print(
            "backend_proxy_probe=FAILED "
            + type(exc).__name__
            + ": "
            + str(exc),
            flush=True,
        )
        print("DIAGNOSIS=backend_container_proxy_probe_failed", flush=True)
        raise SystemExit(3)

    print("", flush=True)
    print("===== TARGET PRIVATE REFRESH =====", flush=True)
    print(
        "START user={user_id} game={game_id} timeout={timeout}s".format(
            timeout=args.timeout,
            **selected,
        ),
        flush=True,
    )

    try:
        result = await asyncio.wait_for(
            refresh_accessible_private_intel(
                user_id=selected["user_id"],
                game_id=selected["game_id"],
            ),
            timeout=args.timeout,
        )
    except asyncio.TimeoutError:
        print(
            "TIMEOUT user={user_id} game={game_id}".format(**selected),
            flush=True,
        )
        print("DIAGNOSIS=target_private_refresh_timeout", flush=True)
        raise SystemExit(4)
    except Exception as exc:
        print(
            "FAILED "
            + type(exc).__name__
            + ": "
            + str(exc),
            flush=True,
        )
        print("DIAGNOSIS=target_private_refresh_exception", flush=True)
        raise SystemExit(5)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str), flush=True)

    print("", flush=True)
    print("===== POST-REFRESH STATE =====", flush=True)
    refreshed_targets = build_targets()
    post = next(
        (
            item
            for item in refreshed_targets
            if item["user_id"] == selected["user_id"]
            and item["game_id"] == selected["game_id"]
        ),
        None,
    )
    print(json.dumps(post, ensure_ascii=False, sort_keys=True), flush=True)

    if result.get("failed", 0):
        print("DIAGNOSIS=target_private_refresh_partial_failure", flush=True)
        raise SystemExit(6)
    if post is not None and post["stale_observers"]:
        print("DIAGNOSIS=target_private_refresh_completed_but_stale", flush=True)
        raise SystemExit(7)

    print("DIAGNOSIS=target_private_refresh_success", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

import argparse
import asyncio
import json

import httpx
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
    _accessible_accounts,
    _is_account_in_game,
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


def _membership_label(value):
    if value is True:
        return "in_game"
    if value is False:
        return "not_in_game"
    return "unknown"


def build_targets():
    raw = running_private_refresh_targets()
    targets = deduplicate_private_refresh_targets(raw)
    result = []

    for user_id, game_id in targets:
        turn, name = game_turn(game_id)
        accounts = _accessible_accounts(user_id)

        latest = {}
        membership = {}
        stale = []
        excluded_nonmembers = []

        for account in accounts:
            account_id = int(account["id"])
            observed_turn = latest_turn(game_id, account_id)
            latest[account_id] = observed_turn

            in_game = _is_account_in_game(
                planets_account_id=account["planets_account_id"],
                planets_username=account["planets_username"],
                game_id=game_id,
            )
            membership[account_id] = _membership_label(in_game)

            if in_game is False:
                excluded_nonmembers.append(account_id)
                continue

            if (
                turn is not None
                and (observed_turn is None or observed_turn < turn)
            ):
                stale.append(account_id)

        result.append(
            {
                "user_id": user_id,
                "game_id": game_id,
                "game_name": name,
                "canonical_turn": turn,
                "observer_latest_turns": latest,
                "observer_membership": membership,
                "excluded_nonmember_observers": excluded_nonmembers,
                "stale_observers": stale,
            }
        )

    return result


async def probe_backend_proxy(timeout):
    client = PlanetsNuClient()
    if not client.proxy_url:
        raise RuntimeError("backend has no configured Planets.nu proxy")

    async with httpx.AsyncClient(
        timeout=min(timeout, 30),
        follow_redirects=True,
        proxy=client.proxy_url,
        trust_env=False,
    ) as http:
        response = await http.get(
            client.base_url + "/time",
            params={"version": 1},
        )
        response.raise_for_status()

    return {
        "proxy_url": client.proxy_url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "body_preview": response.text[:240],
    }


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
            probe_backend_proxy(args.timeout),
            timeout=min(args.timeout, 35),
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

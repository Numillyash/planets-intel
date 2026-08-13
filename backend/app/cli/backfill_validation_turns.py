from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx
from sqlalchemy import distinct, func, select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.intel.observations.private_turn import persist_private_turn
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.planetsnu.client import PlanetsNuClient


async def _load_with_retry(client: PlanetsNuClient, *, game_id: int, api_key: str, turn: int) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return await client.load_turn(
                game_id=game_id,
                api_key=api_key,
                turn=turn,
                for_save=False,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < 3:
                await asyncio.sleep(attempt)
    assert last_error is not None
    raise last_error


def _observer_ids(game_id: int) -> list[int]:
    with SessionLocal() as session:
        return list(
            session.execute(
                select(distinct(PrivateObservationBatch.observer_planets_account_id))
                .where(PrivateObservationBatch.game_id == game_id)
                .order_by(PrivateObservationBatch.observer_planets_account_id)
            ).scalars()
        )


def _turn_bounds(game_id: int) -> tuple[int, int]:
    with SessionLocal() as session:
        row = session.execute(
            select(func.min(PrivateObservationBatch.turn), func.max(PrivateObservationBatch.turn))
            .where(PrivateObservationBatch.game_id == game_id)
        ).one()
    if row[0] is None or row[1] is None:
        raise RuntimeError(f"game {game_id} has no private observation batches")
    return int(row[0]), int(row[1])


async def _run(args: argparse.Namespace) -> int:
    observers = _observer_ids(args.game_id)
    if not observers:
        raise RuntimeError(f"game {args.game_id} has no observer accounts")

    min_turn, max_turn = _turn_bounds(args.game_id)
    turn_from = args.turn_from if args.turn_from is not None else min_turn
    turn_to = args.turn_to if args.turn_to is not None else max_turn
    if turn_from > turn_to:
        raise ValueError("turn-from must not exceed turn-to")

    summary = {
        "game_id": args.game_id,
        "observers": len(observers),
        "turn_from": turn_from,
        "turn_to": turn_to,
        "requested": 0,
        "created": 0,
        "existing": 0,
        "ionstorms": 0,
        "failures": 0,
    }

    client = PlanetsNuClient()
    for observer_id in observers:
        with SessionLocal() as session:
            account = session.get(PlanetsAccount, observer_id)
            if account is None:
                raise RuntimeError(f"observer account {observer_id} no longer exists")
            encrypted_api_key = account.api_key_encrypted
            username = account.planets_username

        api_key = decrypt_credential(encrypted_api_key)
        try:
            for turn in range(turn_from, turn_to + 1):
                summary["requested"] += 1
                try:
                    payload = await _load_with_retry(
                        client,
                        game_id=args.game_id,
                        api_key=api_key,
                        turn=turn,
                    )
                    rst = payload.get("rst", {})
                    storms = rst.get("ionstorms", []) if isinstance(rst, dict) else []
                    with SessionLocal() as session:
                        result = persist_private_turn(
                            session,
                            game_id=args.game_id,
                            observer_planets_account_id=observer_id,
                            payload=payload,
                        )
                        session.commit()
                    summary["created" if result["created"] else "existing"] += 1
                    summary["ionstorms"] += int(result.get("ionstorms", len(storms)))
                    print(json.dumps({
                        "observer": observer_id,
                        "username": username,
                        "turn": turn,
                        "created": bool(result["created"]),
                        "ionstorms": int(result.get("ionstorms", len(storms))),
                        "batch_id": int(result["batch_id"]),
                    }, sort_keys=True))
                except Exception as exc:
                    summary["failures"] += 1
                    print(json.dumps({
                        "observer": observer_id,
                        "username": username,
                        "turn": turn,
                        "error": f"{type(exc).__name__}: {exc}",
                    }, sort_keys=True), file=sys.stderr)
        finally:
            del api_key

    print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0 if summary["failures"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-fetch historical private turns and persist extra validation context."
    )
    parser.add_argument("--game-id", type=int, required=True)
    parser.add_argument("--turn-from", type=int)
    parser.add_argument("--turn-to", type=int)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())

import asyncio
import json
from typing import Any

import httpx
from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.game import Game
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.planetsnu.client import PlanetsNuClient
from app.services.background_private_refresh import (
    deduplicate_private_refresh_targets,
    running_private_refresh_targets,
)
from app.services.private_refresh import (
    _accessible_accounts,
    _is_account_in_game,
)


def _latest_turn(game_id: int, account_id: int) -> int | None:
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


def _game(game_id: int) -> tuple[int | None, str | None]:
    with SessionLocal() as session:
        row = session.execute(
            select(Game.current_turn, Game.name).where(Game.id == game_id)
        ).one_or_none()
    if row is None:
        return None, None
    return row[0], row[1]


def _select_stale_member_target() -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    targets = deduplicate_private_refresh_targets(running_private_refresh_targets())

    for user_id, game_id in targets:
        canonical_turn, game_name = _game(game_id)
        if canonical_turn is None:
            continue

        for account in _accessible_accounts(user_id):
            membership = _is_account_in_game(
                planets_account_id=account["planets_account_id"],
                planets_username=account["planets_username"],
                game_id=game_id,
            )
            if membership is False:
                continue

            observed_turn = _latest_turn(game_id, int(account["id"]))
            if observed_turn is not None and observed_turn >= canonical_turn:
                continue

            candidates.append(
                {
                    "user_id": user_id,
                    "game_id": game_id,
                    "game_name": game_name,
                    "canonical_turn": canonical_turn,
                    "linked_account_id": int(account["id"]),
                    "planets_username": account["planets_username"],
                    "observed_turn": observed_turn,
                    "membership": "in_game" if membership is True else "unknown",
                }
            )

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda item: (
            -(item["canonical_turn"] or 0),
            item["game_id"],
            item["linked_account_id"],
        ),
    )[0]


def _account(account_id: int) -> PlanetsAccount:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(PlanetsAccount.id == account_id)
        ).scalar_one_or_none()
        if account is None:
            raise RuntimeError(f"linked account {account_id} not found")
        session.expunge(account)
        return account


def _safe_json_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"payload_type": type(payload).__name__}

    summary: dict[str, Any] = {
        "success": payload.get("success"),
        "error": payload.get("error"),
        "top_level_keys": sorted(str(key) for key in payload.keys()),
    }

    rst = payload.get("rst")
    if isinstance(rst, dict):
        summary["rst_keys"] = sorted(str(key) for key in rst.keys())
        game = rst.get("game")
        if isinstance(game, dict):
            summary["game"] = {
                "id": game.get("id"),
                "turn": game.get("turn"),
                "status": game.get("status"),
                "name": game.get("name"),
            }
        player = rst.get("player")
        if isinstance(player, dict):
            summary["player"] = {
                "id": player.get("id"),
                "accountid": player.get("accountid"),
                "username": player.get("username"),
                "status": player.get("status"),
            }

    return summary


async def main() -> None:
    target = _select_stale_member_target()
    if target is None:
        print("DIAGNOSIS=no_stale_member_target", flush=True)
        return

    print("===== SELECTED STALE MEMBER =====", flush=True)
    print(json.dumps(target, ensure_ascii=False, sort_keys=True), flush=True)

    account = _account(target["linked_account_id"])
    print("", flush=True)
    print("===== LINKED ACCOUNT METADATA =====", flush=True)
    print(
        json.dumps(
            {
                "linked_account_id": account.id,
                "planets_username": account.planets_username,
                "planets_account_id": account.planets_account_id,
                "is_active": account.is_active,
                "last_verified_at": (
                    account.last_verified_at.isoformat()
                    if account.last_verified_at is not None
                    else None
                ),
                "last_error": account.last_error,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    api_key = decrypt_credential(account.api_key_encrypted)
    client = PlanetsNuClient()
    if not client.proxy_url:
        raise RuntimeError("PLANETSNU_PROXY_URL is not configured in backend")

    url = client.base_url + "/game/loadturn"
    data = {
        "gameid": target["game_id"],
        "apikey": api_key,
        "forsave": "true",
        "activity": "true",
    }
    headers = {
        "Origin": "https://planets.nu",
        "Referer": "https://planets.nu/",
        "User-Agent": "Mozilla/5.0",
    }

    print("", flush=True)
    print("===== RAW LOADTURN REQUEST =====", flush=True)
    print(
        json.dumps(
            {
                "url": url,
                "proxy_url": client.proxy_url,
                "game_id": target["game_id"],
                "linked_account_id": target["linked_account_id"],
                "apikey": "<redacted>",
                "forsave": data["forsave"],
                "activity": data["activity"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            proxy=client.proxy_url,
            trust_env=False,
        ) as http:
            response = await http.post(
                url,
                data=data,
                headers=headers,
            )
    finally:
        del api_key
        data["apikey"] = "<redacted>"

    print("", flush=True)
    print("===== RAW LOADTURN RESPONSE =====", flush=True)
    print(
        json.dumps(
            {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    body = response.text
    try:
        payload = response.json()
    except ValueError:
        preview = body[:1000].replace("\r", "\\r").replace("\n", "\\n")
        print("json_parse=FAILED", flush=True)
        print("body_preview=" + preview, flush=True)
        print("DIAGNOSIS=loadturn_invalid_json_response", flush=True)
        raise SystemExit(3)

    print("json_parse=OK", flush=True)
    print(
        json.dumps(
            _safe_json_summary(payload),
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    if response.is_error:
        print("DIAGNOSIS=loadturn_http_error", flush=True)
        raise SystemExit(4)

    if isinstance(payload, dict) and payload.get("success") is False:
        print("DIAGNOSIS=loadturn_api_error", flush=True)
        raise SystemExit(5)

    if not isinstance(payload, dict) or not isinstance(payload.get("rst"), dict):
        print("DIAGNOSIS=loadturn_missing_rst", flush=True)
        raise SystemExit(6)

    print("DIAGNOSIS=loadturn_raw_success", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

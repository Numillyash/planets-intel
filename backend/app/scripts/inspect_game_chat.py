import argparse
import asyncio
import json
from collections import Counter
from typing import Any

from app.core.credentials import decrypt_credential
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.scripts.inspect_private_events import resolve_account, sanitize


COMMON_HEADERS = {
    "Origin": "https://planets.nu",
    "Referer": "https://planets.nu/",
    "User-Agent": "Mozilla/5.0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect read-only Planets.nu in-game message/chat payloads for a "
            "linked account without persisting anything."
        )
    )
    parser.add_argument("game_id", type=int)
    parser.add_argument(
        "--account-id",
        type=int,
        required=True,
        help="Local planets_accounts.id used as the observer.",
    )
    parser.add_argument(
        "--turn",
        type=int,
        help="Optional historical loadturn to inspect in addition to activity.",
    )
    parser.add_argument(
        "--no-activity",
        action="store_true",
        help="Skip activity-feed probes.",
    )
    parser.add_argument(
        "--activity-only",
        action="store_true",
        help=(
            "Skip detailed rst.messages/rst.mymessages output and print only "
            "activity-feed sources."
        ),
    )
    return parser.parse_args()


def _dict_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _value_label(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _api_failed(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("success") is False


def activity_request_candidates(
    *,
    api_key: str,
    planets_account_id: int | None,
    game_id: int,
    player_id: int,
) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    if planets_account_id is not None:
        candidates.append(
            (
                "apikey+accountid+gameid+playerid",
                {
                    "apikey": api_key,
                    "accountid": planets_account_id,
                    "gameid": game_id,
                    "playerid": player_id,
                },
            )
        )
    candidates.append(
        (
            "apikey+gameid+playerid",
            {
                "apikey": api_key,
                "gameid": game_id,
                "playerid": player_id,
            },
        )
    )
    return candidates


def private_activity_request_candidates(
    *,
    api_key: str,
    planets_account_id: int | None,
    game_id: int,
    player_id: int,
) -> list[tuple[str, dict[str, Any]]]:
    candidates = activity_request_candidates(
        api_key=api_key,
        planets_account_id=planets_account_id,
        game_id=game_id,
        player_id=player_id,
    )
    if planets_account_id is not None:
        candidates.append(
            (
                "apikey+accountid",
                {"apikey": api_key, "accountid": planets_account_id},
            )
        )
    candidates.append(("apikey", {"apikey": api_key}))
    return candidates


def print_collection(name: str, records: list[dict[str, Any]]) -> None:
    print(f"\n===== LOADTURN {name.upper()} ({len(records)}) =====")
    type_counts = Counter(
        _value_label(record.get("messagetype"))
        for record in records
    )
    headline_counts = Counter(
        str(record.get("headline") or "")
        for record in records
    )
    print("messagetype counts:")
    for value, count in sorted(type_counts.items()):
        print(f"  {value}: {count}")
    print("headline counts:")
    for value, count in headline_counts.most_common():
        print(f"  {value!r}: {count}")

    for index, record in enumerate(records):
        print(f"\n--- {name}[{index}] ---")
        print(
            json.dumps(
                sanitize(record),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
        )


def print_raw_payload(title: str, payload: Any) -> None:
    print(f"\n===== {title} =====")
    print(f"python_type: {type(payload).__name__}")
    if isinstance(payload, dict):
        print("top_level_keys: " + ", ".join(sorted(str(key) for key in payload)))
    elif isinstance(payload, list):
        print(f"items: {len(payload)}")

    print(
        json.dumps(
            sanitize(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


async def probe_endpoint(
    client: PlanetsNuClient,
    *,
    endpoint: str,
    title: str,
    candidates: list[tuple[str, dict[str, Any]]],
) -> None:
    print(f"\n===== {title} PROBE =====")
    for label, data in candidates:
        print(f"\n--- attempt: {label} ---")
        print("request fields: " + ", ".join(
            "apikey=<redacted>" if key == "apikey" else f"{key}={value}"
            for key, value in data.items()
        ))
        try:
            payload = await client.post_form(
                endpoint,
                data=data,
                headers=COMMON_HEADERS,
                use_proxy=True,
            )
        except PlanetsNuError as exc:
            print(f"transport_or_http_error: {exc}")
            continue

        if _api_failed(payload):
            print("api_error:")
            print(
                json.dumps(
                    sanitize(payload),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
            )
            continue

        print(f"accepted_request_shape: {label}")
        print_raw_payload(f"{title} RAW RESPONSE", payload)
        return

    print("\nNo candidate request shape produced a successful payload.")


async def run() -> None:
    args = parse_args()
    if args.game_id <= 0:
        raise SystemExit("game_id must be positive")
    if args.turn is not None and args.turn <= 0:
        raise SystemExit("--turn must be positive")

    account = resolve_account(args.game_id, args.account_id)
    api_key = decrypt_credential(account.api_key_encrypted)
    client = PlanetsNuClient()

    try:
        loadturn = await client.load_turn(
            game_id=args.game_id,
            api_key=api_key,
            turn=args.turn,
        )

        rst = loadturn.get("rst")
        if not isinstance(rst, dict):
            raise SystemExit("loadturn response has no rst object")

        game = rst.get("game") if isinstance(rst.get("game"), dict) else {}
        player = rst.get("player") if isinstance(rst.get("player"), dict) else {}
        player_id = _positive_int(player.get("id"))

        print(f"linked_account_id: {account.id}")
        print(f"planets_account_id: {account.planets_account_id}")
        print(f"username: {account.planets_username}")
        print(f"game_id: {args.game_id}")
        print(f"requested_turn: {args.turn}")
        print(f"returned_turn: {game.get('turn')}")
        print(f"observer_player_id: {player_id}")

        if not args.activity_only:
            print_collection("messages", _dict_records(rst.get("messages")))
            print_collection("mymessages", _dict_records(rst.get("mymessages")))
        print_raw_payload("LOADTURN TOP-LEVEL ACTIVITY", loadturn.get("activity"))

        if not args.no_activity:
            if player_id is None:
                raise SystemExit(
                    "loadturn response has no valid rst.player.id required by "
                    "activity endpoints"
                )
            await probe_endpoint(
                client,
                endpoint="account/ingameactivity",
                title="/ACCOUNT/INGAMEACTIVITY",
                candidates=activity_request_candidates(
                    api_key=api_key,
                    planets_account_id=account.planets_account_id,
                    game_id=args.game_id,
                    player_id=player_id,
                ),
            )
            await probe_endpoint(
                client,
                endpoint="account/privateactivity",
                title="/ACCOUNT/PRIVATEACTIVITY",
                candidates=private_activity_request_candidates(
                    api_key=api_key,
                    planets_account_id=account.planets_account_id,
                    game_id=args.game_id,
                    player_id=player_id,
                ),
            )
    finally:
        del api_key


if __name__ == "__main__":
    asyncio.run(run())

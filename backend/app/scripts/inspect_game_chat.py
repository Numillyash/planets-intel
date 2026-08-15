import argparse
import asyncio
import json
from collections import Counter
from typing import Any

from app.core.credentials import decrypt_credential
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.scripts.inspect_private_events import resolve_account, sanitize


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
        help="Skip the /account/ingameactivity probe.",
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


def print_activity_payload(payload: Any) -> None:
    print("\n===== /ACCOUNT/INGAMEACTIVITY RAW RESPONSE =====")
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
        print(f"linked_account_id: {account.id}")
        print(f"planets_account_id: {account.planets_account_id}")
        print(f"username: {account.planets_username}")
        print(f"game_id: {args.game_id}")
        print(f"requested_turn: {args.turn}")
        print(f"returned_turn: {game.get('turn')}")

        print_collection("messages", _dict_records(rst.get("messages")))
        print_collection("mymessages", _dict_records(rst.get("mymessages")))

        if args.no_activity:
            return

        print("\n===== /ACCOUNT/INGAMEACTIVITY PROBE =====")
        print(
            "request fields: apikey=<redacted>, "
            f"accountid={account.planets_account_id}, gameid={args.game_id}"
        )
        try:
            activity = await client.post_form(
                "account/ingameactivity",
                data={
                    "apikey": api_key,
                    "accountid": account.planets_account_id,
                    "gameid": args.game_id,
                },
                headers={
                    "Origin": "https://planets.nu",
                    "Referer": "https://planets.nu/",
                    "User-Agent": "Mozilla/5.0",
                },
                use_proxy=True,
            )
        except PlanetsNuError as exc:
            print(f"request_error: {exc}")
        else:
            print_activity_payload(activity)
    finally:
        del api_key


if __name__ == "__main__":
    asyncio.run(run())

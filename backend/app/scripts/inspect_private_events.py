import argparse
import asyncio
import json
import math
from typing import Any

from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


SENSITIVE_KEYS = frozenset({"apikey", "password", "savekey"})
DEFAULT_EVENT_COLLECTIONS = frozenset(
    {
        "messages",
        "mymessages",
        "explosions",
        "events",
        "notifications",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect raw event-like records in a private Planets.nu loadturn "
            "without persisting or mutating game state."
        )
    )
    parser.add_argument("game_id", type=int)
    parser.add_argument(
        "--account-id",
        type=int,
        help=(
            "Local planets_accounts.id. If omitted, resolve the unique active "
            "linked account participating in the game."
        ),
    )
    parser.add_argument(
        "--turn",
        type=int,
        help="Historical turn to request. Omit for the current turn.",
    )
    parser.add_argument(
        "--near",
        nargs=2,
        metavar=("X", "Y"),
        type=float,
        help="Match records located near these map coordinates.",
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=10.0,
        help="Coordinate match radius in light-years (default: 10).",
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        help=(
            "Case-insensitive text to search for in raw records. Repeatable, "
            "for example: --term Explosion --term Scout."
        ),
    )
    parser.add_argument(
        "--collection",
        action="append",
        default=[],
        help=(
            "Restrict scanning to an rst list collection. Repeatable. "
            "Without this option all rst list collections are eligible."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "When no --near/--term filter is supplied, dump every record from "
            "eligible collections instead of only event-like collections."
        ),
    )
    return parser.parse_args()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize(item)
            for key, item in value.items()
            if str(key).casefold() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def numeric(raw: dict[str, Any], key: str) -> float | None:
    value = raw.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def record_text(raw: dict[str, Any]) -> str:
    return json.dumps(
        sanitize(raw),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).casefold()


def match_record(
    raw: dict[str, Any],
    *,
    near: tuple[float, float] | None,
    radius: float,
    terms: list[str],
) -> list[str]:
    reasons: list[str] = []

    if near is not None:
        x = numeric(raw, "x")
        y = numeric(raw, "y")
        if x is not None and y is not None:
            distance = math.hypot(x - near[0], y - near[1])
            if distance <= radius:
                reasons.append(f"near={distance:.2f}ly")

    if terms:
        haystack = record_text(raw)
        for term in terms:
            if term.casefold() in haystack:
                reasons.append(f"term={term!r}")

    return reasons


def resolve_account(game_id: int, account_id: int | None) -> PlanetsAccount:
    with SessionLocal() as session:
        if account_id is not None:
            account = session.execute(
                select(PlanetsAccount).where(
                    PlanetsAccount.id == account_id,
                    PlanetsAccount.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if account is None:
                raise SystemExit("active linked Planets.nu account not found")
            session.expunge(account)
            return account

        accounts = list(
            session.execute(
                select(PlanetsAccount)
                .join(
                    GamePlayerSlot,
                    GamePlayerSlot.account_id == PlanetsAccount.planets_account_id,
                )
                .where(
                    GamePlayerSlot.game_id == game_id,
                    PlanetsAccount.is_active.is_(True),
                )
                .distinct()
                .order_by(PlanetsAccount.id)
            ).scalars().all()
        )
        for account in accounts:
            session.expunge(account)

    if not accounts:
        raise SystemExit(
            "no active linked account can be resolved for this game; "
            "pass --account-id explicitly"
        )
    if len(accounts) > 1:
        rendered = ", ".join(
            f"{account.id}:{account.planets_username}" for account in accounts
        )
        raise SystemExit(
            "multiple active linked accounts participate in this game; "
            f"pass --account-id explicitly ({rendered})"
        )
    return accounts[0]


async def run() -> None:
    args = parse_args()
    if args.turn is not None and args.turn <= 0:
        raise SystemExit("--turn must be positive")
    if args.radius < 0:
        raise SystemExit("--radius must be non-negative")

    account = resolve_account(args.game_id, args.account_id)
    api_key = decrypt_credential(account.api_key_encrypted)
    try:
        payload = await PlanetsNuClient().load_turn(
            game_id=args.game_id,
            api_key=api_key,
            turn=args.turn,
        )
    finally:
        del api_key

    rst = payload.get("rst")
    if not isinstance(rst, dict):
        raise SystemExit("loadturn response has no rst object")

    game = rst.get("game") if isinstance(rst.get("game"), dict) else {}
    returned_turn = game.get("turn")
    near = tuple(args.near) if args.near is not None else None
    selected_collections = {name.casefold() for name in args.collection}
    terms = [term for term in args.term if term.strip()]
    has_filter = near is not None or bool(terms)

    print(f"linked_account_id: {account.id}")
    print(f"username: {account.planets_username}")
    print(f"game_id: {args.game_id}")
    print(f"requested_turn: {args.turn}")
    print(f"returned_turn: {returned_turn}")
    print(f"success: {payload.get('success')}")
    if near is not None:
        print(f"near: {near[0]:g},{near[1]:g} radius={args.radius:g}")
    if terms:
        print("terms: " + ", ".join(repr(term) for term in terms))

    list_collections = {
        key: value
        for key, value in rst.items()
        if isinstance(value, list)
    }

    print("\n===== RST LIST COLLECTIONS =====")
    for name in sorted(list_collections):
        value = list_collections[name]
        first_keys: list[str] = []
        for item in value:
            if isinstance(item, dict):
                first_keys = sorted(str(key) for key in item.keys())
                break
        suffix = f" keys={','.join(first_keys)}" if first_keys else ""
        print(f"{name}: {len(value)}{suffix}")

    print("\n===== MATCHING RAW RECORDS =====")
    matches = 0
    for collection_name in sorted(list_collections):
        if (
            selected_collections
            and collection_name.casefold() not in selected_collections
        ):
            continue

        records = list_collections[collection_name]
        event_like_default = collection_name.casefold() in DEFAULT_EVENT_COLLECTIONS

        for index, item in enumerate(records):
            if not isinstance(item, dict):
                continue

            reasons = match_record(
                item,
                near=near,
                radius=args.radius,
                terms=terms,
            )

            if has_filter:
                if not reasons:
                    continue
            elif not args.all and not event_like_default:
                continue
            else:
                reasons = ["unfiltered"]

            matches += 1
            print(
                f"\n--- {collection_name}[{index}] "
                f"({', '.join(reasons)}) ---"
            )
            print(
                json.dumps(
                    sanitize(item),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
            )

    print(f"\nMATCHES: {matches}")


if __name__ == "__main__":
    asyncio.run(run())

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
        "activity",
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
            "Case-insensitive text to search for in raw record values. Repeatable, "
            "for example: --term Explosion --term Scout."
        ),
    )
    parser.add_argument(
        "--collection",
        action="append",
        default=[],
        help=(
            "Restrict scanning to a named list collection. This includes rst "
            "collections plus the top-level loadturn activity list. Repeatable."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Scan all list collections, including catalogs. By default diagnostics "
            "scan only event-like collections even when filters are supplied."
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


def _searchable_values(value: Any) -> list[str]:
    """Flatten scalar payload values without matching field names themselves."""

    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            if str(key).casefold() in SENSITIVE_KEYS:
                continue
            parts.extend(_searchable_values(item))
        return parts
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(_searchable_values(item))
        return parts
    if value is None:
        return []
    return [str(value)]


def record_text(raw: dict[str, Any]) -> str:
    return "\n".join(_searchable_values(raw)).casefold()


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
    top_level_activity = payload.get("activity")
    if isinstance(top_level_activity, list):
        list_collections["activity"] = top_level_activity

    print("\n===== LOADTURN LIST COLLECTIONS =====")
    for name in sorted(list_collections):
        value = list_collections[name]
        first_keys: list[str] = []
        for item in value:
            if isinstance(item, dict):
                first_keys = sorted(str(key) for key in item.keys())
                break
        suffix = f" keys={','.join(first_keys)}" if first_keys else ""
        origin = "top-level" if name == "activity" else "rst"
        print(f"{name}: {len(value)} origin={origin}{suffix}")

    print("\n===== MATCHING RAW RECORDS =====")
    matches = 0
    for collection_name in sorted(list_collections):
        collection_key = collection_name.casefold()
        if selected_collections and collection_key not in selected_collections:
            continue
        if not selected_collections and not args.all and collection_key not in DEFAULT_EVENT_COLLECTIONS:
            continue

        records = list_collections[collection_name]
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

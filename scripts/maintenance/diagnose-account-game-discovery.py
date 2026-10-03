import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare public games/list discovery with authenticated "
            "account/mygames discovery for linked Planets.nu accounts."
        )
    )
    parser.add_argument("game_id", type=int)
    parser.add_argument("--account-id", type=int, default=None)
    return parser.parse_args()


def active_accounts(account_id: int | None) -> list[PlanetsAccount]:
    with SessionLocal() as session:
        stmt = (
            select(PlanetsAccount)
            .where(PlanetsAccount.is_active.is_(True))
            .order_by(PlanetsAccount.id)
        )
        if account_id is not None:
            stmt = stmt.where(PlanetsAccount.id == account_id)
        rows = list(session.execute(stmt).scalars().all())
        for row in rows:
            session.expunge(row)
        return rows


def game_ids_from_public(records: list[dict[str, Any]]) -> set[int]:
    result: set[int] = set()
    for raw in records:
        value = raw.get("id")
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        result.add(value)
    return result


def game_ids_from_mygames(records: list[dict[str, Any]]) -> set[int]:
    result: set[int] = set()
    for envelope in records:
        raw = envelope.get("game")
        if not isinstance(raw, dict):
            continue
        value = raw.get("id")
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        result.add(value)
    return result


async def main() -> None:
    args = parse_args()
    if args.game_id <= 0:
        raise SystemExit("game_id must be positive")

    accounts = active_accounts(args.account_id)
    if not accounts:
        raise SystemExit("no matching active linked accounts")

    print("===== ACCOUNT GAME DISCOVERY DIAGNOSTIC =====", flush=True)
    print(f"game_id={args.game_id}", flush=True)

    found_public = False
    found_authenticated = False

    for account in accounts:
        client = PlanetsNuClient()
        public_records: list[dict[str, Any]] = []
        authenticated_records: list[dict[str, Any]] = []
        public_error: str | None = None
        authenticated_error: str | None = None

        try:
            public_records = await client.games_for_username(
                account.planets_username
            )
        except PlanetsNuError as exc:
            public_error = f"{type(exc).__name__}: {exc}"

        api_key = decrypt_credential(account.api_key_encrypted)
        try:
            # Call the endpoint directly so this diagnostic also works against a
            # running backend image that predates PlanetsNuClient.my_games().
            payload = await client.post_form(
                "account/mygames?version=2",
                data={"apikey": api_key},
                headers={
                    "Origin": "https://planets.nu",
                    "Referer": "https://planets.nu/",
                    "User-Agent": "Mozilla/5.0",
                },
                use_proxy=True,
            )
        except PlanetsNuError as exc:
            authenticated_error = f"{type(exc).__name__}: {exc}"
        else:
            if (
                isinstance(payload, dict)
                and isinstance(payload.get("games"), list)
            ):
                authenticated_records = [
                    item
                    for item in payload["games"]
                    if isinstance(item, dict)
                ]
            else:
                authenticated_error = "invalid account/mygames response shape"
        finally:
            del api_key

        public_ids = game_ids_from_public(public_records)
        authenticated_ids = game_ids_from_mygames(authenticated_records)
        public_match = args.game_id in public_ids
        authenticated_match = args.game_id in authenticated_ids
        found_public = found_public or public_match
        found_authenticated = found_authenticated or authenticated_match

        print(
            json.dumps(
                {
                    "linked_account_id": account.id,
                    "username": account.planets_username,
                    "public_games": len(public_ids),
                    "authenticated_games": len(authenticated_ids),
                    "target_in_public_games_list": public_match,
                    "target_in_authenticated_mygames": authenticated_match,
                    "public_error": public_error,
                    "authenticated_error": authenticated_error,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )

    print("", flush=True)
    if found_authenticated and not found_public:
        print(
            "DIAGNOSIS=private_game_requires_authenticated_discovery",
            flush=True,
        )
    elif found_authenticated and found_public:
        print("DIAGNOSIS=game_visible_in_both_sources", flush=True)
    elif found_public:
        print("DIAGNOSIS=game_visible_public_only", flush=True)
    else:
        print("DIAGNOSIS=game_not_discovered", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

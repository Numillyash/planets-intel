from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


async def get_account_games(
    *,
    user_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id
                == linked_account_id,
                PlanetsAccount.user_id
                == user_id,
                PlanetsAccount.is_active.is_(
                    True
                ),
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        planets_username = (
            account.planets_username
        )

    raw_games = (
        await PlanetsNuClient()
        .games_for_username(
            planets_username
        )
    )

    games: list[dict[str, Any]] = []

    for raw in raw_games:
        game_id = raw.get("id")

        if not isinstance(game_id, int):
            continue

        games.append(
            {
                "id": game_id,
                "name": str(
                    raw.get("name", "")
                ),
                "short_description": str(
                    raw.get(
                        "shortdescription",
                        "",
                    )
                ),
                "status_id": int(
                    raw.get("status", 0)
                ),
                "status_name": str(
                    raw.get(
                        "statusname",
                        "",
                    )
                ),
                "turn": int(
                    raw.get("turn", 0)
                ),
                "slots": int(
                    raw.get("slots", 0)
                ),
                "next_host": str(
                    raw.get(
                        "nexthost",
                        "",
                    )
                ),
                "time_to_host": str(
                    raw.get(
                        "timetohost",
                        "",
                    )
                ),
                "is_private": bool(
                    raw.get(
                        "isprivate",
                        False,
                    )
                ),
                "is_custom": bool(
                    raw.get(
                        "iscustom",
                        False,
                    )
                ),
            }
        )

    games.sort(
        key=lambda game: (
            game["status_id"] != 2,
            game["name"].casefold(),
            game["id"],
        )
    )

    return {
        "linked_account_id": (
            linked_account_id
        ),
        "planets_username": (
            planets_username
        ),
        "games": games,
    }

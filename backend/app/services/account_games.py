from typing import Any

from sqlalchemy import and_, func, or_, select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


def _game_record_from_remote(raw: dict[str, Any]) -> dict[str, Any] | None:
    game_id = raw.get("id")
    if not isinstance(game_id, int):
        return None

    raw_turn_status = raw.get("turnstatus")

    return {
        "id": game_id,
        "name": str(raw.get("name", "")),
        "short_description": str(raw.get("shortdescription", "")),
        "status_id": int(raw.get("status", 0)),
        "status_name": str(raw.get("statusname", "")),
        "turn": int(raw.get("turn", 0)),
        "slots": int(raw.get("slots", 0)),
        "turn_status": (
            raw_turn_status
            if isinstance(raw_turn_status, str)
            else None
        ),
        "next_host": str(raw.get("nexthost", "")),
        "time_to_host": str(raw.get("timetohost", "")),
        "is_private": bool(raw.get("isprivate", False)),
        "is_custom": bool(raw.get("iscustom", False)),
        "data_source": "planets.nu",
    }


def _game_record_from_cache(game: Game) -> dict[str, Any]:
    return {
        "id": game.id,
        "name": game.name,
        "short_description": "",
        "status_id": game.status_id,
        "status_name": game.status_name,
        "turn": game.current_turn,
        "slots": game.slots,
        # The compact all-player status rail comes from games/list. It is not
        # persisted canonically, so cache fallback must keep it unknown rather
        # than fabricating unopened states.
        "turn_status": None,
        "next_host": "",
        "time_to_host": "",
        "is_private": game.is_private,
        "is_custom": game.is_custom,
        "data_source": "canonical-cache",
    }


def _cached_membership_condition(account: PlanetsAccount):
    """Match a linked account to a cached roster without sentinel-id leakage."""

    normalized_username = account.planets_username.strip().casefold()
    predicates = []

    # Zero/sentinel ids occur in edge/dead identity records. Matching them as
    # real account ids can make unrelated games appear in a cached game list.
    if account.planets_account_id is not None and account.planets_account_id > 0:
        predicates.append(GamePlayerSlot.account_id == account.planets_account_id)
    if normalized_username:
        predicates.append(
            func.lower(func.trim(GamePlayerSlot.username)) == normalized_username
        )

    if not predicates:
        # A linked account with no usable identity proves no cached membership.
        # Upstream games/list can still provide the authoritative live list.
        return False
    return or_(*predicates)


def _cached_games_for_account(account: PlanetsAccount) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        stmt = (
            select(Game)
            .join(
                GamePlayerSlot,
                GamePlayerSlot.game_id == Game.id,
            )
            .where(_cached_membership_condition(account))
            .distinct()
        )
        rows = list(session.execute(stmt).scalars().all())

    return [_game_record_from_cache(game) for game in rows]


def _sort_games(games: list[dict[str, Any]]) -> None:
    games.sort(
        key=lambda game: (
            game["status_id"] != 2,
            game["name"].casefold(),
            game["id"],
        )
    )


async def get_account_games(
    *,
    user_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        # Detach the values needed below before the session closes.  The
        # account itself can still be passed to the cache helper because its
        # scalar columns are already loaded.
        planets_username = account.planets_username
        cached_games = _cached_games_for_account(account)

    upstream_available = True
    upstream_error: str | None = None

    try:
        raw_games = await PlanetsNuClient().games_for_username(
            planets_username
        )
    except PlanetsNuError as exc:
        upstream_available = False
        upstream_error = str(exc)
        raw_games = []

    by_id: dict[int, dict[str, Any]] = {
        game["id"]: game
        for game in cached_games
    }

    for raw in raw_games:
        game = _game_record_from_remote(raw)
        if game is not None:
            # Fresh Planets.nu metadata wins over canonical cache metadata for
            # the same game, while locally known games remain available if the
            # public list is incomplete or temporarily unreachable.
            by_id[game["id"]] = game

    games = list(by_id.values())
    _sort_games(games)

    if not upstream_available and not games:
        # Preserve the old explicit failure when we genuinely have no cached
        # membership to serve.  The resilience path must not turn "unknown"
        # into an empty-but-successful game list.
        raise PlanetsNuError(
            upstream_error or "Planets.nu game list is unavailable"
        )

    return {
        "linked_account_id": linked_account_id,
        "planets_username": planets_username,
        "games": games,
        "upstream_available": upstream_available,
        "upstream_error": upstream_error,
    }

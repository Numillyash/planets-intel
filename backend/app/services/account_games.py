from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
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
        "observer_slot_id": None,
        "observer_status": None,
        "membership_source": "upstream",
    }


def _game_record_from_authenticated_envelope(
    envelope: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize one /account/mygames v2 record.

    The authenticated endpoint returns {"game": {...}, "player": {...}}.
    Preserve the same game-list shape used by the picker while attaching the
    selected account's current slot/status as stronger observer evidence.
    """

    raw_game = envelope.get("game")
    if not isinstance(raw_game, dict):
        return None

    record = _game_record_from_remote(raw_game)
    if record is None:
        return None

    player = envelope.get("player")
    if isinstance(player, dict):
        slot_id = player.get("id")
        status = player.get("status")
        if (
            not isinstance(slot_id, bool)
            and isinstance(slot_id, int)
            and slot_id > 0
        ):
            record["observer_slot_id"] = slot_id
        if not isinstance(status, bool) and isinstance(status, int):
            record["observer_status"] = status
        record["membership_source"] = "authenticated-mygames"

    record["data_source"] = "planets.nu-authenticated"
    return record


def _game_record_from_cache(
    game: Game,
    *,
    observer_slot_id: int | None = None,
    observer_status: int | None = None,
    membership_source: str = "roster",
) -> dict[str, Any]:
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
        # These fields are local membership evidence, not Planets.nu game-list
        # metadata. They let the chooser retain and classify games after a
        # linked observer has died and upstream games/list stops returning them.
        "observer_slot_id": observer_slot_id,
        "observer_status": observer_status,
        "membership_source": membership_source,
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


def _merge_remote_observer_evidence(
    remote: dict[str, Any],
    cached: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep fresh game metadata while retaining locally proven observer identity."""

    if cached is None:
        return remote

    merged = dict(remote)
    for key in ("observer_slot_id", "observer_status", "membership_source"):
        value = cached.get(key)
        if value is not None:
            merged[key] = value
    return merged


def _cached_games_for_account(account: PlanetsAccount) -> list[dict[str, Any]]:
    """Return games proven by current roster or historical private observation.

    A dead player can disappear from Planets.nu games/list and can also lose a
    useful current roster identity. PrivateObservationBatch is durable factual
    evidence that this exact linked account observed the game, including its
    source slot. The current canonical slot at that historical slot supplies
    the observer status when available.
    """

    records_by_id: dict[int, dict[str, Any]] = {}

    with SessionLocal() as session:
        roster_stmt = (
            select(
                Game,
                GamePlayerSlot.slot_id,
                GamePlayerSlot.status,
            )
            .join(
                GamePlayerSlot,
                GamePlayerSlot.game_id == Game.id,
            )
            .where(_cached_membership_condition(account))
            .distinct()
        )
        for game, slot_id, status in session.execute(roster_stmt).all():
            records_by_id[game.id] = _game_record_from_cache(
                game,
                observer_slot_id=slot_id,
                observer_status=status,
                membership_source="roster",
            )

        historical_slot = aliased(GamePlayerSlot)
        historical_stmt = (
            select(
                Game,
                PrivateObservationBatch.source_player_slot_id,
                historical_slot.status,
                PrivateObservationBatch.turn,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.game_id == Game.id,
            )
            .outerjoin(
                historical_slot,
                and_(
                    historical_slot.game_id == Game.id,
                    historical_slot.slot_id
                    == PrivateObservationBatch.source_player_slot_id,
                ),
            )
            .where(
                PrivateObservationBatch.observer_planets_account_id
                == account.id
            )
            .order_by(Game.id, PrivateObservationBatch.turn.desc())
        )
        for game, slot_id, status, _turn in session.execute(historical_stmt).all():
            # Current roster identity is stronger when it still exists. For a
            # dead/missing identity, the first historical row is the latest
            # private observation because of the descending-turn ordering.
            if game.id in records_by_id:
                continue
            records_by_id[game.id] = _game_record_from_cache(
                game,
                observer_slot_id=(slot_id if slot_id > 0 else None),
                observer_status=status,
                membership_source="historical-private-observation",
            )

    return list(records_by_id.values())


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
        encrypted_api_key = account.api_key_encrypted
        cached_games = _cached_games_for_account(account)

    public_error: str | None = None
    authenticated_error: str | None = None
    raw_games: list[dict[str, Any]] = []
    authenticated_games: list[dict[str, Any]] = []
    client = PlanetsNuClient()

    try:
        raw_games = await client.games_for_username(planets_username)
    except PlanetsNuError as exc:
        public_error = str(exc)

    api_key = decrypt_credential(encrypted_api_key)
    try:
        authenticated_games = await client.my_games(api_key)
    except PlanetsNuError as exc:
        authenticated_error = str(exc)
    finally:
        del api_key

    upstream_available = public_error is None or authenticated_error is None
    upstream_errors = [
        label + ": " + detail
        for label, detail in (
            ("public games/list", public_error),
            ("authenticated account/mygames", authenticated_error),
        )
        if detail is not None
    ]
    upstream_error = " · ".join(upstream_errors) if upstream_errors else None

    by_id: dict[int, dict[str, Any]] = {
        game["id"]: game
        for game in cached_games
    }

    # Public username discovery keeps archive/current metadata broad for normal
    # games, but it is not sufficient for private/custom membership.
    for raw in raw_games:
        game = _game_record_from_remote(raw)
        if game is not None:
            by_id[game["id"]] = _merge_remote_observer_evidence(
                game,
                by_id.get(game["id"]),
            )

    # Authenticated current-player discovery is authoritative for active private
    # and custom games belonging to this linked observer. Apply it after the
    # public list so its observer slot/status evidence wins.
    for envelope in authenticated_games:
        game = _game_record_from_authenticated_envelope(envelope)
        if game is not None:
            by_id[game["id"]] = _merge_remote_observer_evidence(
                game,
                by_id.get(game["id"]),
            )

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

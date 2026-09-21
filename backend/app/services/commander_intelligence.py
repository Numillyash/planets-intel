from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.public_game_info_cache import PublicGameInfoCache
from app.models.public_player_history_cache import PublicPlayerHistoryCache
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


PLAYER_HISTORY_SOURCE = "planets.nu/games/list"
GAME_INFO_SOURCE = "planets.nu/game/loadinfo"
PLAYER_HISTORY_STATUS_FILTER = "2,3"
PLAYER_HISTORY_TTL = timedelta(hours=12)
RUNNING_GAME_INFO_TTL = timedelta(hours=1)
FINISHED_GAME_INFO_TTL = timedelta(days=30)
FETCH_CONCURRENCY = 6
METHOD_VERSION = "commander_overlap_v1"

_RESERVED_USERNAMES = {
    "",
    "dead",
    "open",
    "ready",
    "ready marker",
    "ready_marker",
    "unopened",
    "computer",
    "unknown",
    "empty",
}

_EVENT_RE = re.compile(
    r"^\s*(?P<username>.+?)\s+has\s+"
    r"(?P<action>joined|been dropped)\b(?P<rest>.*)$",
    re.IGNORECASE,
)
_RACE_RE = re.compile(r"\bas\s+(?P<race>.+?)\s*$", re.IGNORECASE)


def canonical_username(value: str) -> str:
    return " ".join(value.casefold().split())


def _usable_username(value: Any) -> bool:
    return (
        isinstance(value, str)
        and canonical_username(value) not in _RESERVED_USERNAMES
    )


def _int(value: Any, *, positive: bool = False) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if positive and value <= 0:
        return None
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_fresh(fetched_at: datetime, ttl: timedelta) -> bool:
    return datetime.now(timezone.utc) - _aware(fetched_at) <= ttl


def _history_game(raw: dict[str, Any]) -> dict[str, Any] | None:
    game_id = _int(raw.get("id"), positive=True)
    status = _int(raw.get("status"))
    if game_id is None or status not in {2, 3}:
        return None
    return {
        "game_id": game_id,
        "name": str(raw.get("name") or f"Game {game_id}"),
        "status_id": status,
        "status_name": str(raw.get("statusname") or ""),
        "turn": _int(raw.get("turn")),
        "date_created": (
            raw.get("datecreated")
            if isinstance(raw.get("datecreated"), str)
            else None
        ),
        "date_ended": (
            raw.get("dateended")
            if isinstance(raw.get("dateended"), str)
            else None
        ),
    }


def _event_identity(event: dict[str, Any]) -> tuple[str, str, str | None] | None:
    description = event.get("description")
    if not isinstance(description, str):
        return None
    match = _EVENT_RE.match(description)
    if match is None:
        return None
    username = match.group("username").strip()
    if not _usable_username(username):
        return None
    action = match.group("action").casefold()
    race_match = _RACE_RE.search(match.group("rest") or "")
    race_name = race_match.group("race").strip() if race_match else None
    return username, action, race_name


def _event_sort_key(event: dict[str, Any]) -> tuple[int, int]:
    return (
        _int(event.get("turn")) or 0,
        _int(event.get("id")) or _int(event.get("eventid")) or 0,
    )


def _source_event_id(event: dict[str, Any]) -> int | None:
    return (
        _int(event.get("id"), positive=True)
        or _int(event.get("eventid"), positive=True)
    )


def _matching_player_rows(
    payload: dict[str, Any],
    username: str,
) -> list[dict[str, Any]]:
    wanted = canonical_username(username)
    players = payload.get("players")
    if not isinstance(players, list):
        return []
    return [
        player
        for player in players
        if (
            isinstance(player, dict)
            and _usable_username(player.get("username"))
            and canonical_username(str(player["username"])) == wanted
        )
    ]


def _matching_roster_row(
    rows: list[dict[str, Any]],
    *,
    slot_id: int | None,
) -> dict[str, Any] | None:
    if slot_id is not None:
        for row in rows:
            if _int(row.get("id"), positive=True) == slot_id:
                return row
    if len(rows) == 1:
        return rows[0]
    return None


def _period(
    *,
    username: str,
    game_id: int,
    slot_id: int | None,
    turn_from: int | None,
    turn_to: int | None,
    race_id: int | None,
    race_name: str | None,
    source_event_ids: Iterable[int | None],
    quality: str,
    basis: str,
) -> dict[str, Any]:
    return {
        "username": username,
        "game_id": game_id,
        "slot_id": slot_id,
        "turn_from": turn_from,
        "turn_to": turn_to,
        "race_id": race_id,
        "race_name": race_name,
        "source": GAME_INFO_SOURCE,
        "source_event_ids": sorted(
            {event_id for event_id in source_event_ids if event_id is not None}
        ),
        "reconstruction_quality": quality,
        "bounds_known": turn_from is not None and turn_to is not None,
        "basis": basis,
    }


def reconstruct_participation_intervals(
    payload: dict[str, Any],
    username: str,
) -> list[dict[str, Any]]:
    """Reconstruct public participation without inventing unknown interval bounds.

    Join/drop event pairs are the strongest evidence. Current roster fields are
    used only to close a still-active join or as a fallback when no attributable
    event interval exists. A one-sided event remains one-sided and therefore
    cannot contribute to an exact turn-overlap count.
    """

    game_raw = payload.get("game")
    game_id = (
        _int(game_raw.get("id"), positive=True)
        if isinstance(game_raw, dict)
        else None
    )
    if game_id is None:
        return []

    game_turn = _int(game_raw.get("turn")) if isinstance(game_raw, dict) else None
    roster_rows = _matching_player_rows(payload, username)
    wanted = canonical_username(username)

    events_raw = payload.get("events")
    events = [
        event
        for event in events_raw
        if isinstance(event, dict)
    ] if isinstance(events_raw, list) else []
    events.sort(key=_event_sort_key)

    by_slot: dict[int | None, list[tuple[dict[str, Any], str, str | None]]] = (
        defaultdict(list)
    )
    for event in events:
        event_type = _int(event.get("eventtype"))
        if event_type not in {3, 10}:
            continue
        identity = _event_identity(event)
        if identity is None:
            continue
        event_username, action, race_name = identity
        if canonical_username(event_username) != wanted:
            continue
        slot_id = _int(event.get("playerid"), positive=True)
        by_slot[slot_id].append((event, action, race_name))

    result: list[dict[str, Any]] = []
    for slot_id, slot_events in by_slot.items():
        open_join: tuple[dict[str, Any], str | None] | None = None
        for event, action, race_name in slot_events:
            turn = _int(event.get("turn"), positive=True)
            if turn is None:
                continue

            if action == "joined":
                if open_join is not None:
                    prior, prior_race = open_join
                    prior_turn = _int(prior.get("turn"), positive=True)
                    roster = _matching_roster_row(roster_rows, slot_id=slot_id)
                    result.append(
                        _period(
                            username=username,
                            game_id=game_id,
                            slot_id=slot_id,
                            turn_from=prior_turn,
                            turn_to=None,
                            race_id=(
                                _int(roster.get("raceid"))
                                if roster is not None
                                else None
                            ),
                            race_name=prior_race,
                            source_event_ids=[_source_event_id(prior)],
                            quality="event_open_unknown",
                            basis=(
                                "A later join was observed before an attributable "
                                "drop for this participation; the earlier end turn "
                                "is intentionally unknown."
                            ),
                        )
                    )
                open_join = (event, race_name)
                continue

            if open_join is not None:
                join_event, join_race = open_join
                start = _int(join_event.get("turn"), positive=True)
                roster = _matching_roster_row(roster_rows, slot_id=slot_id)
                result.append(
                    _period(
                        username=username,
                        game_id=game_id,
                        slot_id=slot_id,
                        turn_from=start,
                        turn_to=turn,
                        race_id=(
                            _int(roster.get("raceid"))
                            if roster is not None
                            else None
                        ),
                        race_name=join_race,
                        source_event_ids=[
                            _source_event_id(join_event),
                            _source_event_id(event),
                        ],
                        quality="event_bounded",
                        basis="Public join and drop events bound the interval.",
                    )
                )
                open_join = None
            else:
                roster = _matching_roster_row(roster_rows, slot_id=slot_id)
                result.append(
                    _period(
                        username=username,
                        game_id=game_id,
                        slot_id=slot_id,
                        turn_from=None,
                        turn_to=turn,
                        race_id=(
                            _int(roster.get("raceid"))
                            if roster is not None
                            else None
                        ),
                        race_name=race_name,
                        source_event_ids=[_source_event_id(event)],
                        quality="event_start_unknown",
                        basis=(
                            "A public drop event is attributable, but no matching "
                            "join/start event was available."
                        ),
                    )
                )

        if open_join is not None:
            join_event, join_race = open_join
            start = _int(join_event.get("turn"), positive=True)
            roster = _matching_roster_row(roster_rows, slot_id=slot_id)
            active_same_slot = (
                roster is not None
                and _int(roster.get("status")) == 1
                and game_turn is not None
            )
            result.append(
                _period(
                    username=username,
                    game_id=game_id,
                    slot_id=slot_id,
                    turn_from=start,
                    turn_to=game_turn if active_same_slot else None,
                    race_id=(
                        _int(roster.get("raceid"))
                        if roster is not None
                        else None
                    ),
                    race_name=join_race,
                    source_event_ids=[_source_event_id(join_event)],
                    quality=(
                        "event_open_roster"
                        if active_same_slot
                        else "event_open_unknown"
                    ),
                    basis=(
                        "Public join event plus the current active roster bounds "
                        "the interval through the observed game turn."
                        if active_same_slot
                        else (
                            "A public join event is attributable, but no factual "
                            "end turn is available."
                        )
                    ),
                )
            )

    # Roster fallback is only added for identities that did not get a bounded
    # or open interval on that same slot from event evidence.
    covered_slots = {
        item["slot_id"]
        for item in result
        if item["slot_id"] is not None and item["turn_from"] is not None
    }
    for row in roster_rows:
        slot_id = _int(row.get("id"), positive=True)
        if slot_id in covered_slots:
            continue
        start = _int(row.get("turnjoined"), positive=True) or 1
        status = _int(row.get("status"))
        end = (
            game_turn
            if status == 1
            else _int(row.get("statusturn"), positive=True)
        )
        result.append(
            _period(
                username=username,
                game_id=game_id,
                slot_id=slot_id,
                turn_from=start,
                turn_to=end,
                race_id=_int(row.get("raceid")),
                race_name=None,
                source_event_ids=[],
                quality="roster_fallback",
                basis=(
                    "Public loadinfo player turnjoined/status/statusturn fields "
                    "bound the interval because no stronger event interval was "
                    "available for this slot."
                ),
            )
        )

    # Preserve multiple periods; only remove exact duplicate evidence rows.
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in result:
        key = (
            item["slot_id"],
            item["turn_from"],
            item["turn_to"],
            item["race_id"],
            item["race_name"],
            item["reconstruction_quality"],
        )
        current = deduped.get(key)
        if current is None:
            deduped[key] = item
        else:
            current["source_event_ids"] = sorted(
                set(current["source_event_ids"]) | set(item["source_event_ids"])
            )

    return sorted(
        deduped.values(),
        key=lambda item: (
            item["turn_from"] is None,
            item["turn_from"] or 0,
            item["turn_to"] is None,
            item["turn_to"] or 0,
            item["slot_id"] or 0,
        ),
    )


def exact_overlap_intervals(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, int]]:
    raw: list[tuple[int, int]] = []
    for a in left:
        a_from = a.get("turn_from")
        a_to = a.get("turn_to")
        if not isinstance(a_from, int) or not isinstance(a_to, int):
            continue
        for b in right:
            b_from = b.get("turn_from")
            b_to = b.get("turn_to")
            if not isinstance(b_from, int) or not isinstance(b_to, int):
                continue
            start = max(a_from, b_from)
            end = min(a_to, b_to)
            if start <= end:
                raw.append((start, end))

    raw.sort()
    merged: list[list[int]] = []
    for start, end in raw:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    return [
        {
            "turn_from": start,
            "turn_to": end,
            "turn_count": end - start + 1,
        }
        for start, end in merged
    ]


def _history_date(game: dict[str, Any]) -> datetime | None:
    value = game.get("date_created")
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _aware(parsed)
    except ValueError:
        pass
    for pattern in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _history_sort_key(game: dict[str, Any]) -> tuple[float, int]:
    parsed = _history_date(game)
    return (
        parsed.timestamp() if parsed is not None else float(game["game_id"]),
        int(game["game_id"]),
    )


def _shared_occurrence_bounds(
    games: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not games:
        return None, None
    dated = [
        (parsed, game)
        for game in games
        for parsed in [_history_date(game)]
        if parsed is not None
    ]
    # Do not call a game first/last when another shared game lacks a date.
    if len(dated) != len(games):
        return None, None
    dated.sort(key=lambda item: (item[0], int(item[1]["game_id"])))
    return dated[0][1], dated[-1][1]


def _current_commanders(
    game: Game,
    slots: list[GamePlayerSlot],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[GamePlayerSlot]] = defaultdict(list)
    for slot in slots:
        if slot.status != 1 or slot.race_id >= 100 or not _usable_username(slot.username):
            continue
        grouped[canonical_username(slot.username)].append(slot)

    commanders: list[dict[str, Any]] = []
    for normalized, candidates in grouped.items():
        # Duplicate active mapping is identity ambiguity, not evidence that two
        # slots are the same commander.
        if len(candidates) != 1:
            continue
        slot = candidates[0]
        commanders.append(
            {
                "username": slot.username,
                "username_normalized": normalized,
                "slot_id": int(slot.slot_id),
                "account_id": (
                    int(slot.account_id)
                    if slot.account_id is not None and slot.account_id > 0
                    else None
                ),
                "race_id": int(slot.race_id),
                "status": int(slot.status),
                "source": "canonical game_player_slots",
                "source_game_id": int(game.id),
                "source_turn": int(game.current_turn),
            }
        )
    return sorted(commanders, key=lambda item: item["slot_id"])


async def _player_history(
    client: PlanetsNuClient,
    username: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = canonical_username(username)
    cached_payload: list[dict[str, Any]] | None = None
    cached_at: datetime | None = None

    with SessionLocal() as session:
        cached = session.execute(
            select(PublicPlayerHistoryCache).where(
                PublicPlayerHistoryCache.username_normalized == normalized,
                PublicPlayerHistoryCache.status_filter
                == PLAYER_HISTORY_STATUS_FILTER,
            )
        ).scalar_one_or_none()
        if cached is not None:
            cached_payload = [
                dict(item)
                for item in cached.payload
                if isinstance(item, dict)
            ]
            cached_at = cached.fetched_at

    if cached_payload is not None and cached_at is not None and _is_fresh(
        cached_at,
        PLAYER_HISTORY_TTL,
    ):
        payload = cached_payload
        cache_state = "fresh"
        fetched_at = cached_at
    else:
        try:
            payload = await client.games_for_username(
                username,
                statuses=(2, 3),
            )
            fetched_at = datetime.now(timezone.utc)
            cache_state = "refreshed"
            with SessionLocal() as session:
                stmt = insert(PublicPlayerHistoryCache).values(
                    username_normalized=normalized,
                    status_filter=PLAYER_HISTORY_STATUS_FILTER,
                    username=username,
                    source=PLAYER_HISTORY_SOURCE,
                    payload=payload,
                    fetched_at=fetched_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        PublicPlayerHistoryCache.username_normalized,
                        PublicPlayerHistoryCache.status_filter,
                    ],
                    set_={
                        "username": stmt.excluded.username,
                        "source": stmt.excluded.source,
                        "payload": stmt.excluded.payload,
                        "fetched_at": stmt.excluded.fetched_at,
                    },
                )
                session.execute(stmt)
                session.commit()
        except PlanetsNuError:
            if cached_payload is None or cached_at is None:
                raise
            payload = cached_payload
            fetched_at = cached_at
            cache_state = "stale_fallback"

    games = [
        game
        for raw in payload
        if isinstance(raw, dict)
        for game in [_history_game(raw)]
        if game is not None
    ]
    by_id = {game["game_id"]: game for game in games}
    normalized_games = sorted(by_id.values(), key=_history_sort_key, reverse=True)
    return normalized_games, {
        "source": PLAYER_HISTORY_SOURCE,
        "fetched_at": _aware(fetched_at).isoformat(),
        "cache_state": cache_state,
        "status_filter": [2, 3],
    }


def _game_info_ttl(payload: dict[str, Any]) -> timedelta:
    game = payload.get("game")
    if isinstance(game, dict) and _int(game.get("status")) == 3:
        return FINISHED_GAME_INFO_TTL
    return RUNNING_GAME_INFO_TTL


async def _game_info(
    client: PlanetsNuClient,
    game_id: int,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    cached_payload: dict[str, Any] | None = None
    cached_at: datetime | None = None

    with SessionLocal() as session:
        cached = session.execute(
            select(PublicGameInfoCache).where(
                PublicGameInfoCache.game_id == game_id
            )
        ).scalar_one_or_none()
        if cached is not None:
            cached_payload = (
                dict(cached.payload)
                if isinstance(cached.payload, dict)
                else None
            )
            cached_at = cached.fetched_at

    if (
        cached_payload is not None
        and cached_at is not None
        and _is_fresh(cached_at, _game_info_ttl(cached_payload))
    ):
        return cached_payload, {
            "source": GAME_INFO_SOURCE,
            "fetched_at": _aware(cached_at).isoformat(),
            "cache_state": "fresh",
        }

    try:
        async with semaphore:
            payload = await client.load_info(game_id)
        fetched_at = datetime.now(timezone.utc)
        with SessionLocal() as session:
            stmt = insert(PublicGameInfoCache).values(
                game_id=game_id,
                source=GAME_INFO_SOURCE,
                payload=payload,
                fetched_at=fetched_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[PublicGameInfoCache.game_id],
                set_={
                    "source": stmt.excluded.source,
                    "payload": stmt.excluded.payload,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            session.execute(stmt)
            session.commit()
        return payload, {
            "source": GAME_INFO_SOURCE,
            "fetched_at": fetched_at.isoformat(),
            "cache_state": "refreshed",
        }
    except PlanetsNuError as exc:
        if cached_payload is not None and cached_at is not None:
            return cached_payload, {
                "source": GAME_INFO_SOURCE,
                "fetched_at": _aware(cached_at).isoformat(),
                "cache_state": "stale_fallback",
                "warning": str(exc),
            }
        return None, {
            "source": GAME_INFO_SOURCE,
            "fetched_at": None,
            "cache_state": "unavailable",
            "warning": str(exc),
        }


def _interval_race_records(
    game: dict[str, Any],
    intervals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[int | None, str | None]] = set()
    for interval in intervals:
        race_id = interval.get("race_id")
        race_name = interval.get("race_name")
        if race_id is None and race_name is None:
            continue
        key = (race_id, race_name)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "game_id": game["game_id"],
                "game_name": game["name"],
                "race_id": race_id,
                "race_name": race_name,
                "reconstruction_quality": interval["reconstruction_quality"],
                "source": interval["source"],
            }
        )
    return result


async def get_commander_intelligence(
    *,
    game_id: int,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        game = session.get(Game, game_id)
        if game is None:
            return None
        slots = list(
            session.execute(
                select(GamePlayerSlot)
                .where(GamePlayerSlot.game_id == game_id)
                .order_by(GamePlayerSlot.slot_id)
            ).scalars().all()
        )
        # Copy scalar game state before the session closes.
        game_record = {
            "game_id": int(game.id),
            "game_name": game.name,
            "turn": int(game.current_turn),
            "status_id": int(game.status_id),
            "status_name": game.status_name,
        }
        commanders = _current_commanders(game, slots)

    client = PlanetsNuClient()
    histories_raw = await asyncio.gather(
        *(_player_history(client, item["username"]) for item in commanders),
        return_exceptions=True,
    )

    histories: dict[str, list[dict[str, Any]] | None] = {}
    history_provenance: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for commander, raw_result in zip(commanders, histories_raw):
        key = commander["username_normalized"]
        if isinstance(raw_result, BaseException):
            histories[key] = None
            history_provenance[key] = {
                "source": PLAYER_HISTORY_SOURCE,
                "fetched_at": None,
                "cache_state": "unavailable",
                "status_filter": [2, 3],
            }
            warnings.append(
                f"{commander['username']}: public game history unavailable "
                f"({type(raw_result).__name__}: {raw_result})"
            )
        else:
            games, provenance = raw_result
            histories[key] = games
            history_provenance[key] = provenance

    history_by_user_id: dict[str, dict[int, dict[str, Any]]] = {}
    for commander in commanders:
        key = commander["username_normalized"]
        history = histories.get(key)
        history_by_user_id[key] = (
            {item["game_id"]: item for item in history}
            if history is not None
            else {}
        )

    shared_game_ids: set[int] = set()
    for left, right in combinations(commanders, 2):
        left_history = histories.get(left["username_normalized"])
        right_history = histories.get(right["username_normalized"])
        if left_history is None or right_history is None:
            continue
        left_ids = {item["game_id"] for item in left_history}
        right_ids = {item["game_id"] for item in right_history}
        shared_game_ids.update(
            (left_ids & right_ids) - {game_id}
        )

    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    game_info_rows = await asyncio.gather(
        *(
            _game_info(client, shared_id, semaphore)
            for shared_id in sorted(shared_game_ids)
        )
    )
    game_info_by_id = {
        shared_id: row
        for shared_id, row in zip(sorted(shared_game_ids), game_info_rows)
    }

    pairwise: list[dict[str, Any]] = []
    peer_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    race_records_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for left, right in combinations(commanders, 2):
        left_key = left["username_normalized"]
        right_key = right["username_normalized"]
        left_history = histories.get(left_key)
        right_history = histories.get(right_key)

        if left_history is None or right_history is None:
            pair = {
                "player_a": left["username"],
                "player_b": right["username"],
                "shared_games": None,
                "games_with_actual_turn_overlap": None,
                "overlapping_turn_count": None,
                "known_overlapping_turn_count": 0,
                "overlap_reconstruction_complete": False,
                "first_shared_occurrence": None,
                "last_shared_occurrence": None,
                "games": [],
                "status": "history_unavailable",
            }
            pairwise.append(pair)
            continue

        left_by_id = history_by_user_id[left_key]
        right_by_id = history_by_user_id[right_key]
        shared_ids = sorted((set(left_by_id) & set(right_by_id)) - {game_id})
        game_rows: list[dict[str, Any]] = []
        known_overlap_turns = 0
        known_overlap_games = 0
        reconstruction_complete = True

        for shared_id in shared_ids:
            history_game = left_by_id.get(shared_id) or right_by_id[shared_id]
            payload, provenance = game_info_by_id.get(
                shared_id,
                (
                    None,
                    {
                        "source": GAME_INFO_SOURCE,
                        "fetched_at": None,
                        "cache_state": "unavailable",
                    },
                ),
            )

            if payload is None:
                reconstruction_complete = False
                game_rows.append(
                    {
                        **history_game,
                        "player_a_intervals": [],
                        "player_b_intervals": [],
                        "overlap_intervals": [],
                        "overlapping_turn_count": None,
                        "overlap_status": "source_unavailable",
                        "provenance": provenance,
                    }
                )
                continue

            left_intervals = reconstruct_participation_intervals(
                payload,
                left["username"],
            )
            right_intervals = reconstruct_participation_intervals(
                payload,
                right["username"],
            )
            overlaps = exact_overlap_intervals(left_intervals, right_intervals)
            overlap_turns = sum(item["turn_count"] for item in overlaps)
            all_bounds_known = (
                bool(left_intervals)
                and bool(right_intervals)
                and all(item["bounds_known"] for item in left_intervals)
                and all(item["bounds_known"] for item in right_intervals)
            )

            # Exact intersections between bounded intervals remain factual
            # lower-bound evidence even when another interval has an unknown
            # edge. The pair-level exact total stays null until every shared
            # game is fully reconstructed.
            known_overlap_turns += overlap_turns
            if overlaps:
                known_overlap_games += 1

            if not all_bounds_known:
                reconstruction_complete = False
                overlap_status = "interval_bounds_incomplete"
                exact_turns: int | None = None
            else:
                overlap_status = "complete"
                exact_turns = overlap_turns

            game_rows.append(
                {
                    **history_game,
                    "player_a_intervals": left_intervals,
                    "player_b_intervals": right_intervals,
                    "overlap_intervals": overlaps,
                    "overlapping_turn_count": exact_turns,
                    "overlap_status": overlap_status,
                    "provenance": provenance,
                }
            )

            race_records_by_user[left_key].extend(
                _interval_race_records(history_game, left_intervals)
            )
            race_records_by_user[right_key].extend(
                _interval_race_records(history_game, right_intervals)
            )

        shared_history_games = [left_by_id[item] for item in shared_ids]
        first_shared, last_shared = _shared_occurrence_bounds(
            shared_history_games
        )
        exact_overlap_turns = (
            known_overlap_turns if reconstruction_complete else None
        )
        exact_overlap_games = (
            known_overlap_games if reconstruction_complete else None
        )

        pair = {
            "player_a": left["username"],
            "player_b": right["username"],
            "shared_games": len(shared_ids),
            "games_with_actual_turn_overlap": exact_overlap_games,
            "overlapping_turn_count": exact_overlap_turns,
            "known_overlapping_turn_count": known_overlap_turns,
            "overlap_reconstruction_complete": reconstruction_complete,
            "first_shared_occurrence": first_shared,
            "last_shared_occurrence": last_shared,
            "games": game_rows,
            "status": "complete" if reconstruction_complete else "partial",
        }
        pairwise.append(pair)

        peer_by_user[left_key].append(
            {
                "username": right["username"],
                "shared_games": len(shared_ids),
                "games_with_actual_turn_overlap": exact_overlap_games,
                "overlapping_turn_count": exact_overlap_turns,
                "known_overlapping_turn_count": known_overlap_turns,
                "overlap_reconstruction_complete": reconstruction_complete,
            }
        )
        peer_by_user[right_key].append(
            {
                "username": left["username"],
                "shared_games": len(shared_ids),
                "games_with_actual_turn_overlap": exact_overlap_games,
                "overlapping_turn_count": exact_overlap_turns,
                "known_overlapping_turn_count": known_overlap_turns,
                "overlap_reconstruction_complete": reconstruction_complete,
            }
        )

    dossier_rows: list[dict[str, Any]] = []
    for commander in commanders:
        key = commander["username_normalized"]
        history = histories.get(key)
        race_rows = race_records_by_user[key]

        current_race = {
            "game_id": game_id,
            "game_name": game_record["game_name"],
            "race_id": commander["race_id"],
            "race_name": None,
            "reconstruction_quality": "current_canonical_slot",
            "source": "canonical game_player_slots",
        }
        race_rows = [current_race, *race_rows]
        race_dedupe: dict[tuple[int, int | None, str | None], dict[str, Any]] = {}
        for row in race_rows:
            race_dedupe[
                (row["game_id"], row["race_id"], row["race_name"])
            ] = row

        race_frequency = Counter(
            (
                f"id:{row['race_id']}"
                if row["race_id"] is not None
                else f"name:{row['race_name']}"
            )
            for row in race_dedupe.values()
        )
        peers = sorted(
            peer_by_user[key],
            key=lambda item: (
                -(item["shared_games"] or 0),
                -item["known_overlapping_turn_count"],
                item["username"].casefold(),
            ),
        )
        dossier_rows.append(
            {
                **commander,
                "history_status": (
                    "available" if history is not None else "unavailable"
                ),
                "public_history_games": history or [],
                "public_history_game_count": (
                    len(history) if history is not None else None
                ),
                "history_provenance": history_provenance[key],
                "prior_current_game_peers": peers,
                "race_history": sorted(
                    race_dedupe.values(),
                    key=lambda item: item["game_id"],
                    reverse=True,
                ),
                "race_frequency": dict(sorted(race_frequency.items())),
                "race_history_coverage": {
                    "games_with_attributable_race": len(
                        {
                            row["game_id"]
                            for row in race_dedupe.values()
                        }
                    ),
                    "public_history_games": (
                        len(history) if history is not None else None
                    ),
                    "complete": False,
                    "basis": (
                        "Race attribution is limited to the current canonical "
                        "slot and historical shared games whose loadinfo payload "
                        "was reconstructed in this bounded slice."
                    ),
                },
            }
        )

    return {
        **game_record,
        "analysis_kind": "derived_historical_summary",
        "method_version": METHOD_VERSION,
        "behavioral_inference": False,
        "commanders": dossier_rows,
        "pairwise": sorted(
            pairwise,
            key=lambda item: (
                item["player_a"].casefold(),
                item["player_b"].casefold(),
            ),
        ),
        "provenance": {
            "current_roster_source": "canonical game_player_slots",
            "player_history_source": PLAYER_HISTORY_SOURCE,
            "participation_source": GAME_INFO_SOURCE,
            "public_history_status_filter": [2, 3],
            "facts_unchanged": True,
        },
        "warnings": warnings,
    }

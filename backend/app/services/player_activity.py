from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.models.player_turn_activity_observation import PlayerTurnActivityObservation


PUBLIC_ACTIVITY_SOURCE = "planets.nu/loadinfo"
PRIVATE_ACTIVITY_SOURCE = "planets.nu/loadturn"
PLANETS_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"
RESERVED_ACTIVITY_IDENTITIES = {
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


def _parse_planets_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.startswith("1/1/0001"):
        return None
    try:
        return datetime.strptime(text, PLANETS_DATE_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _marker_for_slot(game: dict[str, Any], slot_id: int) -> str | None:
    raw = game.get("turnstatus")
    if not isinstance(raw, str) or slot_id <= 0 or slot_id > len(raw):
        return None
    return raw[slot_id - 1]


def _player_turn_status(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _activity_state(
    *,
    marker: str | None,
    turn_ready: bool,
    player_turn_status: int | None,
    player_status: int | None,
) -> str:
    if player_status is not None and player_status != 1:
        return "dead"
    if turn_ready:
        return "ready"

    normalized_marker = marker.casefold() if isinstance(marker, str) else None
    if normalized_marker == "x":
        return "dead"
    if normalized_marker == "c":
        return "computer"

    # Any remaining non-empty compact marker is Planets.nu's completed-turn
    # race marker. It is stronger than the less-specific per-player numeric
    # turnstatus field.
    if marker and normalized_marker not in {"_", "o", "x", "c"}:
        return "ready_marker"

    # games/list/loadinfo compact markers and loadinfo.players[].turnstatus can
    # be refreshed at slightly different moments. Opening/submitting a turn is
    # monotonic within a single turn, so an OPEN indication from either factual
    # source must not be hidden by a stale '_' from the other source.
    if normalized_marker == "o" or (
        player_turn_status is not None and player_turn_status > 0
    ):
        return "open"
    if normalized_marker == "_" or player_turn_status == 0:
        return "unopened"
    return "unknown"


def _same_state(
    latest: PlayerTurnActivityObservation | None,
    *,
    state: str,
    marker: str | None,
    turn_ready: bool,
    turn_ready_at: datetime | None,
) -> bool:
    if latest is None:
        return False
    return (
        latest.state == state
        and latest.status_marker == marker
        and latest.turn_ready == turn_ready
        and latest.turn_ready_at == turn_ready_at
    )


def persist_public_player_activity(
    session: Session,
    *,
    game_id: int,
    game: dict[str, Any],
    settings: dict[str, Any],
    players: list[dict[str, Any]],
) -> int:
    turn = game.get("turn")
    if isinstance(turn, bool) or not isinstance(turn, int) or turn <= 0:
        return 0

    host_completed_at = _parse_planets_date(settings.get("hostcompleted"))
    inserted = 0

    for raw in players:
        slot_id = raw.get("id")
        if isinstance(slot_id, bool) or not isinstance(slot_id, int) or slot_id <= 0:
            continue
        marker = _marker_for_slot(game, slot_id)
        turn_ready = bool(raw.get("turnready"))
        player_turn_status = _player_turn_status(raw.get("turnstatus"))
        player_status = raw.get("status")
        if isinstance(player_status, bool) or not isinstance(player_status, int):
            player_status = None
        state = _activity_state(
            marker=marker,
            turn_ready=turn_ready,
            player_turn_status=player_turn_status,
            player_status=player_status,
        )
        turn_ready_at = _parse_planets_date(raw.get("turnreadydate"))

        latest = session.execute(
            select(PlayerTurnActivityObservation)
            .where(
                PlayerTurnActivityObservation.game_id == game_id,
                PlayerTurnActivityObservation.turn == turn,
                PlayerTurnActivityObservation.slot_id == slot_id,
            )
            .order_by(
                PlayerTurnActivityObservation.observed_at.desc(),
                PlayerTurnActivityObservation.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

        if _same_state(
            latest,
            state=state,
            marker=marker,
            turn_ready=turn_ready,
            turn_ready_at=turn_ready_at,
        ):
            continue

        session.add(
            PlayerTurnActivityObservation(
                game_id=game_id,
                turn=turn,
                slot_id=slot_id,
                source=PUBLIC_ACTIVITY_SOURCE,
                state=state,
                status_marker=marker,
                turn_ready=turn_ready,
                turn_ready_at=turn_ready_at,
                host_completed_at=host_completed_at,
            )
        )
        inserted += 1

    return inserted


def persist_private_ready_activity(
    session: Session,
    *,
    game_id: int,
    turn: int,
    players: list[dict[str, Any]],
) -> int:
    """Backfill exact Ready timestamps exposed in historical loadturn players."""

    inserted = 0
    for raw in players:
        slot_id = raw.get("id")
        if isinstance(slot_id, bool) or not isinstance(slot_id, int) or slot_id <= 0:
            continue
        if raw.get("turnready") is not True:
            continue
        turn_ready_at = _parse_planets_date(raw.get("turnreadydate"))
        if turn_ready_at is None:
            continue

        exists = session.execute(
            select(PlayerTurnActivityObservation.id)
            .where(
                PlayerTurnActivityObservation.game_id == game_id,
                PlayerTurnActivityObservation.turn == turn,
                PlayerTurnActivityObservation.slot_id == slot_id,
                PlayerTurnActivityObservation.turn_ready_at == turn_ready_at,
            )
            .limit(1)
        ).scalar_one_or_none()
        if exists is not None:
            continue

        session.add(
            PlayerTurnActivityObservation(
                game_id=game_id,
                turn=turn,
                slot_id=slot_id,
                source=PRIVATE_ACTIVITY_SOURCE,
                state="ready",
                status_marker=None,
                turn_ready=True,
                turn_ready_at=turn_ready_at,
                host_completed_at=None,
            )
        )
        inserted += 1

    return inserted


def _minute_of_day(value: datetime) -> float:
    utc = value.astimezone(timezone.utc)
    return utc.hour * 60 + utc.minute + utc.second / 60


def _minute_samples(values: list[datetime]) -> list[int]:
    """Return per-turn UTC minute-of-day samples without collapsing modes."""

    return [int(_minute_of_day(value)) % 1440 for value in values]


def _circular_center_minutes(values: list[datetime]) -> int | None:
    if not values:
        return None
    angles = [2 * math.pi * _minute_of_day(value) / 1440 for value in values]
    x = sum(math.cos(angle) for angle in angles) / len(angles)
    y = sum(math.sin(angle) for angle in angles) / len(angles)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return int(round(median(_minute_of_day(value) for value in values))) % 1440
    angle = math.atan2(y, x)
    if angle < 0:
        angle += 2 * math.pi
    return int(round(angle * 1440 / (2 * math.pi))) % 1440


def _confidence(samples: int) -> str:
    if samples >= 5:
        return "high"
    if samples >= 3:
        return "medium"
    if samples >= 1:
        return "low"
    return "none"


def _canonical_activity_username(value: str) -> str:
    return " ".join(value.casefold().split())


def _usable_activity_username(value: str) -> bool:
    normalized = _canonical_activity_username(value)
    return bool(normalized) and normalized not in RESERVED_ACTIVITY_IDENTITIES


def _group_unambiguous_human_slot_keys(
    rows: Iterable[tuple[int, int, str, int]],
) -> dict[str, list[tuple[int, int]]]:
    """Group canonical usernames across games, excluding ambiguous identities.

    A canonical username is accepted from a game only when it maps to exactly
    one human slot in that game. This prevents corrupted/state-placeholder rows
    from turning into cross-game identity evidence.
    """

    by_game_user: dict[tuple[int, str], list[tuple[int, int]]] = defaultdict(list)
    for game_id, slot_id, username, race_id in rows:
        if race_id >= 100 or not _usable_activity_username(username):
            continue
        key = _canonical_activity_username(username)
        by_game_user[(game_id, key)].append((game_id, slot_id))

    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (_game_id, username), slot_keys in by_game_user.items():
        if len(slot_keys) == 1:
            grouped[username].append(slot_keys[0])
    return dict(grouped)


def _current_accessible_game_ids(session: Session, user_id: int) -> set[int]:
    membership = or_(
        and_(
            PlanetsAccount.planets_account_id.is_not(None),
            PlanetsAccount.planets_account_id > 0,
            GamePlayerSlot.account_id == PlanetsAccount.planets_account_id,
        ),
        and_(
            func.length(func.trim(PlanetsAccount.planets_username)) > 0,
            func.lower(func.trim(GamePlayerSlot.username))
            == func.lower(func.trim(PlanetsAccount.planets_username)),
        ),
    )
    rows = session.execute(
        select(GamePlayerSlot.game_id)
        .select_from(PlanetsAccount)
        .join(GamePlayerSlot, membership)
        .join(Game, Game.id == GamePlayerSlot.game_id)
        .where(
            PlanetsAccount.user_id == user_id,
            PlanetsAccount.is_active.is_(True),
            or_(
                Game.status_id == 2,
                Game.status_name.ilike("running"),
                Game.status_name.ilike("joining"),
            ),
        )
    ).all()
    return {int(game_id) for (game_id,) in rows}


def _activity_times(
    rows: list[PlayerTurnActivityObservation],
) -> tuple[list[datetime], list[datetime], list[float], list[float]]:
    by_turn: dict[int, list[PlayerTurnActivityObservation]] = defaultdict(list)
    for row in rows:
        by_turn[row.turn].append(row)

    open_times: list[datetime] = []
    ready_times: list[datetime] = []
    open_delays: list[float] = []
    ready_delays: list[float] = []

    for turn_rows in by_turn.values():
        open_rows = [row for row in turn_rows if row.state == "open"]
        opened = min(open_rows, key=lambda row: (row.observed_at, row.id)) if open_rows else None
        ready_dates = [row.turn_ready_at for row in turn_rows if row.turn_ready_at is not None]
        ready_at = min(ready_dates) if ready_dates else None
        host_dates = [row.host_completed_at for row in turn_rows if row.host_completed_at is not None]
        host_at = min(host_dates) if host_dates else None

        if opened is not None:
            open_times.append(opened.observed_at)
            if host_at is not None:
                open_delays.append((opened.observed_at - host_at).total_seconds() / 60)
        if ready_at is not None:
            ready_times.append(ready_at)
            if host_at is not None:
                ready_delays.append((ready_at - host_at).total_seconds() / 60)

    return open_times, ready_times, open_delays, ready_delays


def get_player_activity_analysis(
    *,
    game_id: int,
    through_turn: int | None = None,
    user_id: int | None = None,
) -> dict[str, object]:
    with SessionLocal() as session:
        slots = list(
            session.execute(
                select(GamePlayerSlot)
                .where(GamePlayerSlot.game_id == game_id)
                .order_by(GamePlayerSlot.slot_id)
            ).scalars().all()
        )
        query = select(PlayerTurnActivityObservation).where(
            PlayerTurnActivityObservation.game_id == game_id
        )
        if through_turn is not None:
            query = query.where(PlayerTurnActivityObservation.turn <= through_turn)
        rows = list(
            session.execute(
                query.order_by(
                    PlayerTurnActivityObservation.turn,
                    PlayerTurnActivityObservation.slot_id,
                    PlayerTurnActivityObservation.observed_at,
                    PlayerTurnActivityObservation.id,
                )
            ).scalars().all()
        )

        current_game_ids = (
            _current_accessible_game_ids(session, user_id)
            if user_id is not None
            else {game_id}
        )
        global_slots = list(
            session.execute(
                select(GamePlayerSlot)
                .where(GamePlayerSlot.game_id.in_(current_game_ids))
                .order_by(GamePlayerSlot.game_id, GamePlayerSlot.slot_id)
            ).scalars().all()
        ) if current_game_ids else []
        global_rows = list(
            session.execute(
                select(PlayerTurnActivityObservation)
                .where(PlayerTurnActivityObservation.game_id.in_(current_game_ids))
                .order_by(
                    PlayerTurnActivityObservation.game_id,
                    PlayerTurnActivityObservation.slot_id,
                    PlayerTurnActivityObservation.turn,
                    PlayerTurnActivityObservation.observed_at,
                    PlayerTurnActivityObservation.id,
                )
            ).scalars().all()
        ) if current_game_ids else []

    by_slot: dict[int, list[PlayerTurnActivityObservation]] = defaultdict(list)
    for row in rows:
        by_slot[row.slot_id].append(row)

    global_by_slot: dict[tuple[int, int], list[PlayerTurnActivityObservation]] = defaultdict(list)
    for row in global_rows:
        global_by_slot[(row.game_id, row.slot_id)].append(row)

    grouped_global_slots = _group_unambiguous_human_slot_keys(
        (slot.game_id, slot.slot_id, slot.username, slot.race_id)
        for slot in global_slots
    )

    result: list[dict[str, object]] = []
    for slot in slots:
        observations = by_slot.get(slot.slot_id, [])
        by_turn: dict[int, list[PlayerTurnActivityObservation]] = defaultdict(list)
        for row in observations:
            by_turn[row.turn].append(row)

        open_times, ready_times, open_delays, ready_delays = _activity_times(observations)

        latest = observations[-1] if observations else None
        current_turn = latest.turn if latest is not None else None
        current_turn_rows = by_turn.get(current_turn, []) if current_turn is not None else []
        current_open_rows = [row for row in current_turn_rows if row.state == "open"]
        first_open = min(
            current_open_rows,
            key=lambda row: (row.observed_at, row.id),
        ) if current_open_rows else None
        current_ready_dates = [
            row.turn_ready_at
            for row in current_turn_rows
            if row.turn_ready_at is not None
        ]
        current_ready_at = min(current_ready_dates) if current_ready_dates else None
        typical_open = _circular_center_minutes(open_times)
        typical_ready = _circular_center_minutes(ready_times)
        basis_samples = max(len(open_times), len(ready_times))

        username_key = _canonical_activity_username(slot.username)
        aggregate_slot_keys = (
            grouped_global_slots.get(username_key, [])
            if _usable_activity_username(slot.username) and slot.race_id < 100
            else []
        )
        aggregate_open_times: list[datetime] = []
        aggregate_ready_times: list[datetime] = []
        aggregate_game_ids: set[int] = set()
        for aggregate_key in aggregate_slot_keys:
            aggregate_game_ids.add(aggregate_key[0])
            aggregate_open, aggregate_ready, _open_delay, _ready_delay = _activity_times(
                global_by_slot.get(aggregate_key, [])
            )
            aggregate_open_times.extend(aggregate_open)
            aggregate_ready_times.extend(aggregate_ready)
        aggregate_basis = max(len(aggregate_open_times), len(aggregate_ready_times))

        result.append(
            {
                "slot_id": slot.slot_id,
                "username": slot.username,
                "race_id": slot.race_id,
                "current_turn": current_turn,
                "current_state": latest.state if latest is not None else "unknown",
                "state_observed_at": latest.observed_at.isoformat() if latest is not None else None,
                "first_open_observed_at": first_open.observed_at.isoformat() if first_open is not None else None,
                "ready_at": current_ready_at.isoformat() if current_ready_at is not None else None,
                "open_samples": len(open_times),
                "ready_samples": len(ready_times),
                "open_utc_minutes": _minute_samples(open_times),
                "ready_utc_minutes": _minute_samples(ready_times),
                "typical_open_utc_minute": typical_open,
                "typical_ready_utc_minute": typical_ready,
                "median_open_after_host_minutes": round(median(open_delays), 1) if open_delays else None,
                "median_ready_after_host_minutes": round(median(ready_delays), 1) if ready_delays else None,
                "prediction_confidence": _confidence(basis_samples),
                "all_current_games_count": len(aggregate_game_ids),
                "all_current_games_open_samples": len(aggregate_open_times),
                "all_current_games_ready_samples": len(aggregate_ready_times),
                "all_current_games_open_utc_minutes": _minute_samples(aggregate_open_times),
                "all_current_games_ready_utc_minutes": _minute_samples(aggregate_ready_times),
                "all_current_games_prediction_confidence": _confidence(aggregate_basis),
            }
        )

    return {
        "game_id": game_id,
        "through_turn": through_turn,
        "current_games_considered": len(current_game_ids),
        "polling_note": (
            "Open time is the first observed public 'open' state and is bounded by the polling interval; "
            "Ready time uses Planets.nu turnreadydate when available. Time-of-day samples are returned "
            "per turn so multimodal activity patterns are not collapsed into one average. Cross-game "
            "samples are combined only from Running/Joining games accessible to the authenticated user's "
            "active linked observers, and ambiguous same-game username identities are excluded."
        ),
        "players": result,
    }

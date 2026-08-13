import math
from datetime import datetime, timezone
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game_player_slot import GamePlayerSlot
from app.models.player_turn_activity_observation import PlayerTurnActivityObservation


PUBLIC_ACTIVITY_SOURCE = "planets.nu/loadinfo"
PRIVATE_ACTIVITY_SOURCE = "planets.nu/loadturn"
PLANETS_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"


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


def _activity_state(
    *,
    marker: str | None,
    turn_ready: bool,
    player_status: int | None,
) -> str:
    if player_status is not None and player_status != 1:
        return "dead"
    if turn_ready:
        return "ready"
    if marker == "o":
        return "open"
    if marker == "_":
        return "unopened"
    if marker == "x":
        return "dead"
    if marker == "c":
        return "computer"
    if marker:
        return "ready_marker"
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
        player_status = raw.get("status")
        if isinstance(player_status, bool) or not isinstance(player_status, int):
            player_status = None
        state = _activity_state(
            marker=marker,
            turn_ready=turn_ready,
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


def get_player_activity_analysis(
    *,
    game_id: int,
    through_turn: int | None = None,
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

    by_slot: dict[int, list[PlayerTurnActivityObservation]] = {}
    for row in rows:
        by_slot.setdefault(row.slot_id, []).append(row)

    result: list[dict[str, object]] = []
    for slot in slots:
        observations = by_slot.get(slot.slot_id, [])
        by_turn: dict[int, list[PlayerTurnActivityObservation]] = {}
        for row in observations:
            by_turn.setdefault(row.turn, []).append(row)

        open_times: list[datetime] = []
        ready_times: list[datetime] = []
        open_delays: list[float] = []
        ready_delays: list[float] = []

        for turn_rows in by_turn.values():
            opened = next((row for row in turn_rows if row.state == "open"), None)
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

        latest = observations[-1] if observations else None
        current_turn = latest.turn if latest is not None else None
        current_turn_rows = by_turn.get(current_turn, []) if current_turn is not None else []
        first_open = next((row for row in current_turn_rows if row.state == "open"), None)
        current_ready_dates = [
            row.turn_ready_at
            for row in current_turn_rows
            if row.turn_ready_at is not None
        ]
        current_ready_at = min(current_ready_dates) if current_ready_dates else None
        typical_open = _circular_center_minutes(open_times)
        typical_ready = _circular_center_minutes(ready_times)
        basis_samples = max(len(open_times), len(ready_times))

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
                "typical_open_utc_minute": typical_open,
                "typical_ready_utc_minute": typical_ready,
                "median_open_after_host_minutes": round(median(open_delays), 1) if open_delays else None,
                "median_ready_after_host_minutes": round(median(ready_delays), 1) if ready_delays else None,
                "prediction_confidence": _confidence(basis_samples),
            }
        )

    return {
        "game_id": game_id,
        "through_turn": through_turn,
        "polling_note": (
            "Open time is the first observed public 'open' state and is bounded by the polling interval; "
            "Ready time uses Planets.nu turnreadydate when available."
        ),
        "players": result,
    }

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from typing import Iterable

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.player_turn_activity_observation import PlayerTurnActivityObservation


@dataclass(frozen=True)
class SlotRef:
    game_id: int
    game_name: str
    slot_id: int
    username: str


@dataclass(frozen=True)
class TimingSample:
    game_id: int
    game_name: str
    slot_id: int
    ready_minutes: tuple[int, ...]
    open_minutes: tuple[int, ...]


def canonical_username(value: str) -> str:
    return " ".join(value.casefold().split())


def parse_utc_offset(value: str) -> int:
    text = value.strip()
    if len(text) != 6 or text[0] not in "+-" or text[3] != ":":
        raise argparse.ArgumentTypeError("UTC offset must look like +03:00 or -05:30")
    try:
        hours = int(text[1:3])
        minutes = int(text[4:6])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("UTC offset contains non-numeric fields") from exc
    if hours > 14 or minutes > 59:
        raise argparse.ArgumentTypeError("UTC offset is outside the supported range")
    total = hours * 60 + minutes
    return total if text[0] == "+" else -total


def minute_of_day(value: datetime, offset_minutes: int) -> int:
    utc = value.astimezone(timezone.utc)
    minute = utc.hour * 60 + utc.minute + offset_minutes
    return minute % 1440


def hourly_histogram(minutes: Iterable[int]) -> tuple[int, ...]:
    counts = [0] * 24
    for minute in minutes:
        counts[(int(minute) % 1440) // 60] += 1
    return tuple(counts)


def histogram_overlap(left: Iterable[int], right: Iterable[int]) -> float | None:
    left_hist = hourly_histogram(left)
    right_hist = hourly_histogram(right)
    left_total = sum(left_hist)
    right_total = sum(right_hist)
    if left_total == 0 or right_total == 0:
        return None
    overlap = sum(
        min(left_count / left_total, right_count / right_total)
        for left_count, right_count in zip(left_hist, right_hist, strict=True)
    )
    return round(overlap * 100, 1)


def format_histogram(minutes: Iterable[int]) -> str:
    hist = hourly_histogram(minutes)
    items = [f"{hour:02d}:{count}" for hour, count in enumerate(hist) if count > 0]
    return " ".join(items) if items else "—"


def _sample_for_slot(
    slot: SlotRef,
    rows: list[PlayerTurnActivityObservation],
    *,
    offset_minutes: int,
) -> TimingSample:
    by_turn: dict[int, list[PlayerTurnActivityObservation]] = defaultdict(list)
    for row in rows:
        by_turn[row.turn].append(row)

    ready: list[int] = []
    opened: list[int] = []
    for turn_rows in by_turn.values():
        ready_dates = [row.turn_ready_at for row in turn_rows if row.turn_ready_at is not None]
        if ready_dates:
            ready.append(minute_of_day(min(ready_dates), offset_minutes))

        open_rows = [row for row in turn_rows if row.state == "open"]
        if open_rows:
            first_open = min(open_rows, key=lambda row: (row.observed_at, row.id))
            opened.append(minute_of_day(first_open.observed_at, offset_minutes))

    return TimingSample(
        game_id=slot.game_id,
        game_name=slot.game_name,
        slot_id=slot.slot_id,
        ready_minutes=tuple(ready),
        open_minutes=tuple(opened),
    )


def load_repeated_player_samples(
    *,
    offset_minutes: int,
    usernames: set[str] | None = None,
) -> dict[str, list[TimingSample]]:
    with SessionLocal() as session:
        slot_rows = list(
            session.execute(
                select(GamePlayerSlot, Game)
                .join(Game, Game.id == GamePlayerSlot.game_id)
                .order_by(GamePlayerSlot.username, GamePlayerSlot.game_id)
            ).all()
        )
        observation_rows = list(
            session.execute(
                select(PlayerTurnActivityObservation).order_by(
                    PlayerTurnActivityObservation.game_id,
                    PlayerTurnActivityObservation.slot_id,
                    PlayerTurnActivityObservation.turn,
                    PlayerTurnActivityObservation.observed_at,
                    PlayerTurnActivityObservation.id,
                )
            ).scalars().all()
        )

    observations_by_slot: dict[tuple[int, int], list[PlayerTurnActivityObservation]] = defaultdict(list)
    for row in observation_rows:
        observations_by_slot[(row.game_id, row.slot_id)].append(row)

    slots_by_user: dict[str, list[SlotRef]] = defaultdict(list)
    for slot, game in slot_rows:
        key = canonical_username(slot.username)
        if usernames is not None and key not in usernames:
            continue
        slots_by_user[key].append(
            SlotRef(
                game_id=slot.game_id,
                game_name=game.name,
                slot_id=slot.slot_id,
                username=slot.username,
            )
        )

    result: dict[str, list[TimingSample]] = {}
    for username, slots in slots_by_user.items():
        unique_games = {slot.game_id for slot in slots}
        if len(unique_games) < 2:
            continue
        samples = [
            _sample_for_slot(
                slot,
                observations_by_slot.get((slot.game_id, slot.slot_id), []),
                offset_minutes=offset_minutes,
            )
            for slot in slots
        ]
        result[username] = sorted(samples, key=lambda item: item.game_id)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the same Planets.nu username across games using observed per-turn "
            "Ready/Open time-of-day distributions. Ready is exact when turnreadydate is present; "
            "Open is polling-bound."
        )
    )
    parser.add_argument(
        "--username",
        action="append",
        default=[],
        help="Limit to one username; may be supplied multiple times.",
    )
    parser.add_argument(
        "--utc-offset",
        type=parse_utc_offset,
        default=0,
        help="Display/comparison timezone offset, for example +03:00. Default: +00:00.",
    )
    parser.add_argument(
        "--min-ready-samples",
        type=int,
        default=1,
        help="Require at least this many Ready samples in each game of a pair. Default: 1.",
    )
    args = parser.parse_args()

    requested = (
        {canonical_username(value) for value in args.username if value.strip()}
        if args.username
        else None
    )
    groups = load_repeated_player_samples(
        offset_minutes=args.utc_offset,
        usernames=requested,
    )

    if not groups:
        print("No usernames with observations in at least two games were found.")
        return

    print("Cross-game player timing comparison")
    print("READY = Planets.nu turnreadydate when available; OPEN = first polling observation.")
    print("Overlap = hourly histogram intersection: 100% identical distribution, 0% disjoint hours.")
    print()

    for username, samples in sorted(groups.items()):
        print(f"===== {username} =====")
        for sample in samples:
            print(
                f"game {sample.game_id} · {sample.game_name} · slot {sample.slot_id} · "
                f"ready n={len(sample.ready_minutes)} [{format_histogram(sample.ready_minutes)}] · "
                f"open n={len(sample.open_minutes)} [{format_histogram(sample.open_minutes)}]"
            )

        eligible_pairs = 0
        ready_overlaps: list[float] = []
        for left, right in combinations(samples, 2):
            if (
                len(left.ready_minutes) < args.min_ready_samples
                or len(right.ready_minutes) < args.min_ready_samples
            ):
                continue
            eligible_pairs += 1
            ready_overlap = histogram_overlap(left.ready_minutes, right.ready_minutes)
            open_overlap = histogram_overlap(left.open_minutes, right.open_minutes)
            if ready_overlap is not None:
                ready_overlaps.append(ready_overlap)
            open_text = "n/a" if open_overlap is None else f"{open_overlap:.1f}%"
            ready_text = "n/a" if ready_overlap is None else f"{ready_overlap:.1f}%"
            print(
                f"PAIR {left.game_id} vs {right.game_id}: "
                f"READY overlap {ready_text} · OPEN overlap {open_text}"
            )

        if eligible_pairs == 0:
            print(
                f"No game pair has >= {args.min_ready_samples} Ready samples on both sides."
            )
        elif ready_overlaps:
            print(
                f"READY mean pairwise overlap: "
                f"{sum(ready_overlaps) / len(ready_overlaps):.1f}% across {len(ready_overlaps)} pairs"
            )
        print()


if __name__ == "__main__":
    main()

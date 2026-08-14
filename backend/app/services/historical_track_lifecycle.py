from typing import Any

from app.services.historical_tracks import (
    get_historical_ship_tracks as _get_raw_historical_ship_tracks,
)


def _tracked_combat_side(
    track: dict[str, Any],
    point: dict[str, Any],
) -> dict[str, Any] | None:
    event = point.get("combat_event")
    if not isinstance(event, dict):
        return None
    sides = event.get("sides")
    if not isinstance(sides, list):
        return None

    ship_id = track.get("ship_id")
    for side in sides:
        if not isinstance(side, dict):
            continue
        if (
            side.get("object_kind") == "ship"
            and side.get("object_id") == ship_id
        ):
            return side
    return None


def _point_hull_id(
    track: dict[str, Any],
    point: dict[str, Any],
) -> int | None:
    # Raw historical points now preserve the factual hull observed on that turn.
    # Prefer it over track-level metadata so an already-proven lifecycle split
    # remains stable after a later turn makes that point no longer `last_turn`.
    hull_id = point.get("hull_id")
    if isinstance(hull_id, int):
        return int(hull_id)

    side = _tracked_combat_side(track, point)
    if side is not None and isinstance(side.get("hull_id"), int):
        return int(side["hull_id"])

    # Compatibility fallback for older/unit-test shaped raw tracks that do not
    # carry per-point identity metadata yet.
    if point.get("turn") == track.get("last_turn"):
        track_hull_id = track.get("hull_id")
        return int(track_hull_id) if isinstance(track_hull_id, int) else None
    return None


def _lifecycle_break(
    track: dict[str, Any],
    previous: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    # A numeric ship_id is reusable in Planets.nu, but a physical ship cannot
    # change its hull. Therefore an observed hull replacement is strong enough
    # to prove a new lifecycle. A generic VCR "defeated" status is deliberately
    # not sufficient because the loser may have been captured rather than
    # destroyed.
    previous_hull_id = _point_hull_id(track, previous)
    current_hull_id = _point_hull_id(track, current)
    return (
        previous_hull_id is not None
        and current_hull_id is not None
        and previous_hull_id != current_hull_id
    )


def _segment_metadata(
    track: dict[str, Any],
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    name = None
    owner_id = None
    hull_id = None

    for point in reversed(points):
        if name is None and isinstance(point.get("name"), str):
            name = point["name"]
        if owner_id is None and isinstance(point.get("owner_id"), int):
            owner_id = int(point["owner_id"])
        if hull_id is None and isinstance(point.get("hull_id"), int):
            hull_id = int(point["hull_id"])

        side = _tracked_combat_side(track, point)
        if side is not None:
            if name is None and isinstance(side.get("name"), str):
                name = side["name"]
            if owner_id is None and isinstance(side.get("owner_id"), int):
                owner_id = int(side["owner_id"])
            if hull_id is None and isinstance(side.get("hull_id"), int):
                hull_id = int(side["hull_id"])

        if name is not None and owner_id is not None and hull_id is not None:
            break

    return {
        "name": name if name is not None else track.get("name"),
        "owner_id": owner_id if owner_id is not None else track.get("owner_id"),
        "hull_id": hull_id if hull_id is not None else track.get("hull_id"),
    }


def _segment_track(track: dict[str, Any]) -> list[dict[str, Any]]:
    raw_points = track.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        return [track]

    points = [point for point in raw_points if isinstance(point, dict)]
    if not points:
        return [track]

    segments: list[list[dict[str, Any]]] = [[points[0]]]
    for point in points[1:]:
        previous = segments[-1][-1]
        if _lifecycle_break(track, previous, point):
            segments.append([point])
        else:
            segments[-1].append(point)

    if len(segments) == 1:
        return [
            {
                **track,
                "lifecycle_index": 0,
                "lifecycle_key": (
                    f"{track.get('ship_id')}:0:{segments[0][0].get('turn')}"
                ),
            }
        ]

    result: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        metadata = _segment_metadata(track, segment)
        result.append(
            {
                **track,
                **metadata,
                "first_turn": segment[0].get("turn"),
                "last_turn": segment[-1].get("turn"),
                "points": segment,
                "lifecycle_index": index,
                "lifecycle_key": (
                    f"{track.get('ship_id')}:{index}:{segment[0].get('turn')}"
                ),
            }
        )
    return result


def get_historical_ship_tracks(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    through_turn: int,
) -> dict[str, Any] | None:
    result = _get_raw_historical_ship_tracks(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        through_turn=through_turn,
    )
    if result is None:
        return None

    raw_tracks = result.get("tracks")
    if not isinstance(raw_tracks, list):
        return result

    tracks: list[dict[str, Any]] = []
    for raw_track in raw_tracks:
        if not isinstance(raw_track, dict):
            continue
        tracks.extend(_segment_track(raw_track))

    return {
        **result,
        "tracks": tracks,
        "track_identity_policy": "split_on_observed_hull_change",
    }

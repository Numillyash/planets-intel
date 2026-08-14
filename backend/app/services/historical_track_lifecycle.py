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
    side = _tracked_combat_side(track, point)
    if side is not None and isinstance(side.get("hull_id"), int):
        return int(side["hull_id"])

    if point.get("turn") == track.get("last_turn"):
        hull_id = track.get("hull_id")
        return int(hull_id) if isinstance(hull_id, int) else None
    return None


def _lifecycle_break(
    track: dict[str, Any],
    previous: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    if bool(current.get("gap_from_previous")):
        return True

    # VCR defeat is the strongest lifecycle boundary we currently have.
    # If a later host report directly confirms survival at the same position,
    # do not close the lifecycle; otherwise a later appearance of the numeric
    # ship ID can be a newly built ship reusing that ID.
    if (
        previous.get("combat_outcome") == "defeated"
        and not bool(previous.get("post_host_confirmed"))
    ):
        return True

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
        side = _tracked_combat_side(track, point)
        if side is None:
            continue
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
        "track_identity_policy": (
            "split_on_gap_defeat_or_observed_hull_change"
        ),
    }

import hashlib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.host_event_observation import HostEventObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts


STARBASE_BUILD_FAILURE_RE = re.compile(
    r"(?:ship\s+(?:has\s+)?not\s+been\s+built|ship\s+was\s+not\s+built|could\s+not\s+build\s+(?:the\s+)?ship)",
    re.IGNORECASE,
)
ENTITY_ID_RE = re.compile(r"(?:starbase|planet)\s*#?\s*(\d+)", re.IGNORECASE)
OWNER_CHANGE_PHRASE = "has been " + "capt" + "ured by the"
PLANET_OWNER_CHANGE_RE = re.compile(
    rf"Planet\s+.+?\s+ID#(?P<planet_id>\d+)\s+{OWNER_CHANGE_PHRASE}\s+"
    r"(?P<ship_name>.+?)\s+ID#(?P<ship_id>\d+)\b",
    re.IGNORECASE | re.DOTALL,
)


def _integer(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    return value if isinstance(value, str) else ""


def _clean_label(value: str, *, limit: int = 255) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    normalized = " ".join(without_tags.split())
    return normalized[:limit]


def _event_key(*parts: object) -> str:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_planet_and_base(
    raw: dict[str, Any],
    *,
    planets: list[dict[str, Any]],
    starbases: list[dict[str, Any]],
) -> tuple[int | None, int | None]:
    planet_ids = {
        item["id"]
        for item in planets
        if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool)
    }
    base_to_planet = {
        item["id"]: item.get("planetid")
        for item in starbases
        if isinstance(item.get("id"), int)
        and not isinstance(item.get("id"), bool)
        and isinstance(item.get("planetid"), int)
        and not isinstance(item.get("planetid"), bool)
    }

    combined = f"{_text(raw, 'headline')} {_text(raw, 'body')}"
    match = ENTITY_ID_RE.search(combined)
    if match is not None:
        entity_id = int(match.group(1))
        if entity_id in planet_ids:
            return entity_id, None
        if entity_id in base_to_planet:
            return base_to_planet[entity_id], entity_id

    target = _integer(raw, "target")
    if target is not None:
        if target in planet_ids:
            return target, None
        if target in base_to_planet:
            return base_to_planet[target], target

    x = _integer(raw, "x")
    y = _integer(raw, "y")
    if x is not None and y is not None:
        for planet in planets:
            if planet.get("x") == x and planet.get("y") == y:
                planet_id = planet.get("id")
                if isinstance(planet_id, int) and not isinstance(planet_id, bool):
                    for base_id, base_planet_id in base_to_planet.items():
                        if base_planet_id == planet_id:
                            return planet_id, base_id
                    return planet_id, None

    return None, None


def persist_safe_host_events(
    session: Session,
    *,
    batch_id: int,
    turn: int,
    messages: list[dict[str, Any]],
    mymessages: list[dict[str, Any]],
    planets: list[dict[str, Any]],
    starbases: list[dict[str, Any]],
) -> int:
    """Persist only recognized host/system facts, never arbitrary message bodies."""

    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for raw in [*messages, *mymessages]:
        headline = _text(raw, "headline")
        body = _text(raw, "body")
        combined = f"{headline} {body}".strip()
        message_id = _integer(raw, "id")
        message_type = _integer(raw, "messagetype")
        x = _integer(raw, "x")
        y = _integer(raw, "y")

        if STARBASE_BUILD_FAILURE_RE.search(combined):
            planet_id, starbase_id = _resolve_planet_and_base(
                raw,
                planets=planets,
                starbases=starbases,
            )
            event_key = _event_key(
                "starbase_ship_not_built",
                turn,
                message_id,
                planet_id,
                starbase_id,
            )
            if event_key not in seen_keys:
                seen_keys.add(event_key)
                location = str(planet_id) if planet_id is not None else "?"
                rows.append(
                    {
                        "batch_id": batch_id,
                        "event_key": event_key,
                        "event_type": "starbase_ship_not_built",
                        "turn": turn,
                        "message_id": message_id,
                        "message_type": message_type,
                        "planet_id": planet_id,
                        "starbase_id": starbase_id,
                        "ship_id": None,
                        "ship_name": None,
                        "x": x,
                        "y": y,
                        "summary": f"Starbase {location} error: the ship has not been built",
                    }
                )

        ownership = PLANET_OWNER_CHANGE_RE.search(body)
        if ownership is not None:
            planet_id = int(ownership.group("planet_id"))
            ship_id = int(ownership.group("ship_id"))
            ship_name = _clean_label(ownership.group("ship_name"))
            event_key = _event_key(
                "planet_owner_change_by_ship",
                turn,
                message_id,
                planet_id,
                ship_id,
            )
            if event_key not in seen_keys:
                seen_keys.add(event_key)
                rows.append(
                    {
                        "batch_id": batch_id,
                        "event_key": event_key,
                        "event_type": "planet_owner_change_by_ship",
                        "turn": turn,
                        "message_id": message_id,
                        "message_type": message_type,
                        "planet_id": planet_id,
                        "starbase_id": None,
                        "ship_id": ship_id,
                        "ship_name": ship_name or None,
                        "x": x,
                        "y": y,
                        "summary": (
                            f"Planet {planet_id} owner changed via ship #{ship_id}"
                            + (f" ({ship_name})" if ship_name else "")
                        ),
                    }
                )

    if not rows:
        return 0

    stmt = (
        pg_insert(HostEventObservation.__table__)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_host_event_observation_batch_key",
        )
        .returning(HostEventObservation.id)
    )
    return len(session.execute(stmt).scalars().all())


def get_accessible_host_events(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, object] | None:
    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return None

    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(HostEventObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == HostEventObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn == turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    HostEventObservation.turn == turn,
                )
                .order_by(HostEventObservation.id)
            ).all()
        )
        account_rows = list(
            session.execute(
                select(PlanetsAccount.id, PlanetsAccount.planets_username)
                .where(PlanetsAccount.id.in_(accessible_ids))
            ).all()
        )

    usernames = {int(row.id): row.planets_username for row in account_rows}
    grouped: dict[tuple[object, ...], dict[str, Any]] = {}

    for event, batch in rows:
        key = (
            event.event_type,
            event.turn,
            event.planet_id,
            event.starbase_id,
            event.ship_id,
            event.ship_name,
            event.summary,
        )
        item = grouped.get(key)
        source = {
            "linked_account_id": batch.observer_planets_account_id,
            "planets_username": usernames.get(
                batch.observer_planets_account_id,
                f"account #{batch.observer_planets_account_id}",
            ),
            "batch_id": batch.id,
        }
        if item is None:
            grouped[key] = {
                "event_type": event.event_type,
                "turn": event.turn,
                "planet_id": event.planet_id,
                "starbase_id": event.starbase_id,
                "ship_id": event.ship_id,
                "ship_name": event.ship_name,
                "x": event.x,
                "y": event.y,
                "summary": event.summary,
                "sources": [source],
            }
        elif not any(
            existing["linked_account_id"] == source["linked_account_id"]
            and existing["batch_id"] == source["batch_id"]
            for existing in item["sources"]
        ):
            item["sources"].append(source)

    events = list(grouped.values())
    events.sort(
        key=lambda item: (
            item["planet_id"] is None,
            item["planet_id"] or 0,
            item["summary"],
        )
    )
    return {
        "game_id": game_id,
        "turn": turn,
        "count": len(events),
        "events": events,
    }

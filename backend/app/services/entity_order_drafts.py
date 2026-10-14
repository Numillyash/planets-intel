from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.planet_observation import PlanetObservation
from app.models.planet_order_draft import PlanetOrderDraft
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.starbase_observation import StarbaseObservation
from app.models.starbase_order_draft import StarbaseOrderDraft
from app.services.order_drafts import (
    OrderDraftAccessError,
    OrderDraftNotFound,
    _account,
)


def _payload_str(payload: dict[str, Any], *keys: str) -> str | None:
    normalized = {key.lower() for key in keys}
    for key, value in payload.items():
        if key.lower() not in normalized:
            continue
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return None


def _latest_batch(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> PrivateObservationBatch:
    _account(session, user_id=user_id, linked_account_id=linked_account_id)
    batch = session.execute(
        select(PrivateObservationBatch)
        .where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.observer_planets_account_id == linked_account_id,
        )
        .order_by(
            PrivateObservationBatch.turn.desc(),
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if batch is None:
        raise OrderDraftNotFound(
            "No factual snapshot is stored for this observer and game"
        )
    if batch.turn != turn:
        raise OrderDraftAccessError(
            "Order drafts are only available for the latest factual turn"
        )
    return batch


def _planet_context(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    planet_id: int,
) -> tuple[PrivateObservationBatch, PlanetObservation]:
    batch = _latest_batch(
        session,
        user_id=user_id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        turn=turn,
    )
    planet = session.execute(
        select(PlanetObservation).where(
            PlanetObservation.batch_id == batch.id,
            PlanetObservation.planet_id == planet_id,
        )
    ).scalar_one_or_none()
    if planet is None:
        raise OrderDraftNotFound("Planet is not present in the factual snapshot")
    if (
        batch.source_player_slot_id is None
        or planet.owner_id != batch.source_player_slot_id
    ):
        raise OrderDraftAccessError(
            "Order drafts are only allowed for planets controlled by the observer"
        )
    return batch, planet


def _starbase_context(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    starbase_id: int,
) -> tuple[PrivateObservationBatch, StarbaseObservation, PlanetObservation]:
    batch = _latest_batch(
        session,
        user_id=user_id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        turn=turn,
    )
    starbase = session.execute(
        select(StarbaseObservation).where(
            StarbaseObservation.batch_id == batch.id,
            StarbaseObservation.starbase_id == starbase_id,
        )
    ).scalar_one_or_none()
    if starbase is None or starbase.planet_id is None:
        raise OrderDraftNotFound("Starbase is not present in the factual snapshot")
    planet = session.execute(
        select(PlanetObservation).where(
            PlanetObservation.batch_id == batch.id,
            PlanetObservation.planet_id == starbase.planet_id,
        )
    ).scalar_one_or_none()
    if planet is None:
        raise OrderDraftNotFound("Starbase planet is missing from factual snapshot")
    if (
        batch.source_player_slot_id is None
        or planet.owner_id != batch.source_player_slot_id
    ):
        raise OrderDraftAccessError(
            "Order drafts are only allowed for starbases controlled by the observer"
        )
    return batch, starbase, planet


def _planet_friendly_code(planet: PlanetObservation) -> str | None:
    return _payload_str(
        planet.payload,
        "friendlycode",
        "friendly_code",
        "fcode",
    )


def _starbase_primary_order(starbase: StarbaseObservation) -> str | None:
    named = _payload_str(
        starbase.payload,
        "missionname",
        "primaryordername",
        "primary_order_name",
        "ordername",
    )
    if named:
        return named
    raw = _payload_str(starbase.payload, "mission", "primaryorder", "primary_order")
    return f"Order #{raw}" if raw is not None else None


def _serialize_planet(
    draft: PlanetOrderDraft,
    *,
    batch: PrivateObservationBatch,
    planet: PlanetObservation,
) -> dict[str, Any]:
    upstream = _planet_friendly_code(planet)
    return {
        "game_id": draft.game_id,
        "linked_account_id": draft.linked_account_id,
        "turn": draft.turn,
        "planet_id": draft.planet_id,
        "base_batch_id": draft.base_batch_id,
        "base_snapshot_hash": draft.base_snapshot_hash,
        "stale": draft.base_snapshot_hash != batch.snapshot_hash,
        "upstream_friendly_code": upstream,
        "friendly_code": draft.friendly_code,
        "changed_friendly_code": (
            draft.friendly_code is not None and draft.friendly_code != upstream
        ),
        "source": "local_order_draft",
    }


def _serialize_starbase(
    draft: StarbaseOrderDraft,
    *,
    batch: PrivateObservationBatch,
    starbase: StarbaseObservation,
) -> dict[str, Any]:
    upstream = _starbase_primary_order(starbase)
    return {
        "game_id": draft.game_id,
        "linked_account_id": draft.linked_account_id,
        "turn": draft.turn,
        "starbase_id": draft.starbase_id,
        "planet_id": draft.planet_id,
        "base_batch_id": draft.base_batch_id,
        "base_snapshot_hash": draft.base_snapshot_hash,
        "stale": draft.base_snapshot_hash != batch.snapshot_hash,
        "upstream_primary_order": upstream,
        "primary_order": draft.primary_order,
        # Nu numeric primary-order mapping is intentionally not guessed here.
        "changed_primary_order": True,
        "source": "local_order_draft",
    }


def get_planet_order_draft(
    *, user_id: int, linked_account_id: int, game_id: int, turn: int, planet_id: int
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        batch, planet = _planet_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            planet_id=planet_id,
        )
        draft = session.execute(
            select(PlanetOrderDraft).where(
                PlanetOrderDraft.user_id == user_id,
                PlanetOrderDraft.linked_account_id == linked_account_id,
                PlanetOrderDraft.game_id == game_id,
                PlanetOrderDraft.turn == turn,
                PlanetOrderDraft.planet_id == planet_id,
            )
        ).scalar_one_or_none()
        return None if draft is None else _serialize_planet(
            draft, batch=batch, planet=planet
        )


def upsert_planet_order_draft(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    planet_id: int,
    friendly_code: str,
) -> dict[str, Any]:
    with SessionLocal() as session:
        batch, planet = _planet_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            planet_id=planet_id,
        )
        draft = session.execute(
            select(PlanetOrderDraft).where(
                PlanetOrderDraft.user_id == user_id,
                PlanetOrderDraft.linked_account_id == linked_account_id,
                PlanetOrderDraft.game_id == game_id,
                PlanetOrderDraft.turn == turn,
                PlanetOrderDraft.planet_id == planet_id,
            )
        ).scalar_one_or_none()
        if draft is None:
            draft = PlanetOrderDraft(
                user_id=user_id,
                linked_account_id=linked_account_id,
                game_id=game_id,
                turn=turn,
                planet_id=planet_id,
                base_batch_id=batch.id,
                base_snapshot_hash=batch.snapshot_hash,
                friendly_code=friendly_code,
            )
            session.add(draft)
        else:
            draft.friendly_code = friendly_code
            draft.base_batch_id = batch.id
            draft.base_snapshot_hash = batch.snapshot_hash
        session.commit()
        session.refresh(draft)
        return _serialize_planet(draft, batch=batch, planet=planet)


def discard_planet_order_draft(
    *, user_id: int, linked_account_id: int, game_id: int, turn: int, planet_id: int
) -> bool:
    with SessionLocal() as session:
        _account(session, user_id=user_id, linked_account_id=linked_account_id)
        result = session.execute(
            delete(PlanetOrderDraft).where(
                PlanetOrderDraft.user_id == user_id,
                PlanetOrderDraft.linked_account_id == linked_account_id,
                PlanetOrderDraft.game_id == game_id,
                PlanetOrderDraft.turn == turn,
                PlanetOrderDraft.planet_id == planet_id,
            )
        )
        session.commit()
        return bool(result.rowcount)


def get_starbase_order_draft(
    *, user_id: int, linked_account_id: int, game_id: int, turn: int, starbase_id: int
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        batch, starbase, _planet = _starbase_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            starbase_id=starbase_id,
        )
        draft = session.execute(
            select(StarbaseOrderDraft).where(
                StarbaseOrderDraft.user_id == user_id,
                StarbaseOrderDraft.linked_account_id == linked_account_id,
                StarbaseOrderDraft.game_id == game_id,
                StarbaseOrderDraft.turn == turn,
                StarbaseOrderDraft.starbase_id == starbase_id,
            )
        ).scalar_one_or_none()
        return None if draft is None else _serialize_starbase(
            draft, batch=batch, starbase=starbase
        )


def upsert_starbase_order_draft(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    starbase_id: int,
    primary_order: str,
) -> dict[str, Any]:
    with SessionLocal() as session:
        batch, starbase, planet = _starbase_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            starbase_id=starbase_id,
        )
        draft = session.execute(
            select(StarbaseOrderDraft).where(
                StarbaseOrderDraft.user_id == user_id,
                StarbaseOrderDraft.linked_account_id == linked_account_id,
                StarbaseOrderDraft.game_id == game_id,
                StarbaseOrderDraft.turn == turn,
                StarbaseOrderDraft.starbase_id == starbase_id,
            )
        ).scalar_one_or_none()
        if draft is None:
            draft = StarbaseOrderDraft(
                user_id=user_id,
                linked_account_id=linked_account_id,
                game_id=game_id,
                turn=turn,
                starbase_id=starbase_id,
                planet_id=planet.planet_id,
                base_batch_id=batch.id,
                base_snapshot_hash=batch.snapshot_hash,
                primary_order=primary_order,
            )
            session.add(draft)
        else:
            draft.primary_order = primary_order
            draft.planet_id = planet.planet_id
            draft.base_batch_id = batch.id
            draft.base_snapshot_hash = batch.snapshot_hash
        session.commit()
        session.refresh(draft)
        return _serialize_starbase(draft, batch=batch, starbase=starbase)


def discard_starbase_order_draft(
    *, user_id: int, linked_account_id: int, game_id: int, turn: int, starbase_id: int
) -> bool:
    with SessionLocal() as session:
        _account(session, user_id=user_id, linked_account_id=linked_account_id)
        result = session.execute(
            delete(StarbaseOrderDraft).where(
                StarbaseOrderDraft.user_id == user_id,
                StarbaseOrderDraft.linked_account_id == linked_account_id,
                StarbaseOrderDraft.game_id == game_id,
                StarbaseOrderDraft.turn == turn,
                StarbaseOrderDraft.starbase_id == starbase_id,
            )
        )
        session.commit()
        return bool(result.rowcount)

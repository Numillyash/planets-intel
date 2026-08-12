import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.intel.observations.private_turn import (
    persist_private_turn,
)
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import PlanetsNuClient


class PrivateSyncError(RuntimeError):
    pass


class PrivateSyncTransportError(PrivateSyncError):
    pass


async def sync_private_game(
    linked_account_id: int,
    game_id: int,
) -> dict[str, Any]:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id
            )
        ).scalar_one_or_none()

        if account is None:
            raise PrivateSyncError(
                "linked Planets.nu account not found"
            )

        if not account.is_active:
            raise PrivateSyncError(
                "linked Planets.nu account is inactive"
            )

        encrypted_api_key = account.api_key_encrypted
        expected_planets_account_id = account.planets_account_id
        planets_username = account.planets_username

    api_key = decrypt_credential(encrypted_api_key)

    try:
        client = PlanetsNuClient()
        payload = None
        last_transport_error: httpx.TransportError | None = None

        for attempt in range(1, 4):
            try:
                payload = await client.load_turn(
                    game_id=game_id,
                    api_key=api_key,
                )
                break
            except httpx.TransportError as exc:
                last_transport_error = exc

                if attempt == 3:
                    break

                await asyncio.sleep(attempt)

        if payload is None:
            error_name = (
                type(last_transport_error).__name__
                if last_transport_error is not None
                else "TransportError"
            )
            raise PrivateSyncTransportError(
                "private Planets.nu request failed after "
                f"3 transport attempts ({error_name})"
            ) from last_transport_error

    finally:
        del api_key

    rst = payload.get("rst")

    if not isinstance(rst, dict):
        raise PrivateSyncError(
            "private turn has no rst object"
        )

    player = rst.get("player")

    if not isinstance(player, dict):
        raise PrivateSyncError(
            "private turn has no player object"
        )

    source_player_slot_id = player.get("id")
    source_account_id = player.get("accountid")
    source_username = player.get("username")

    if (
        isinstance(source_player_slot_id, bool)
        or not isinstance(source_player_slot_id, int)
    ):
        raise PrivateSyncError(
            "private turn has invalid player id"
        )

    if (
        isinstance(source_account_id, bool)
        or not isinstance(source_account_id, int)
        or source_account_id <= 0
    ):
        raise PrivateSyncError(
            "private turn has invalid account id"
        )

    if not isinstance(source_username, str):
        raise PrivateSyncError(
            "private turn has invalid username"
        )

    if (
        source_username.strip().casefold()
        != planets_username.strip().casefold()
    ):
        raise PrivateSyncError(
            "private turn username does not match "
            "linked Planets.nu account"
        )

    if (
        expected_planets_account_id is not None
        and source_account_id != expected_planets_account_id
    ):
        raise PrivateSyncError(
            "private turn belongs to a different "
            "Planets.nu account"
        )

    with SessionLocal() as session:
        game_exists = session.execute(
            select(Game.id).where(Game.id == game_id)
        ).scalar_one_or_none()

        if game_exists is None:
            raise PrivateSyncError(
                "game is not present in canonical database; "
                "run public sync first"
            )

        slot = session.execute(
            select(GamePlayerSlot).where(
                GamePlayerSlot.game_id == game_id,
                GamePlayerSlot.slot_id == source_player_slot_id,
            )
        ).scalar_one_or_none()

        if slot is None:
            raise PrivateSyncError(
                "observer player slot is not present in "
                "canonical database; run public sync first"
            )

        if slot.account_id != source_account_id:
            raise PrivateSyncError(
                "canonical player slot account id does not "
                "match authenticated private turn"
            )

        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id
            )
        ).scalar_one()

        if account.planets_account_id is None:
            account.planets_account_id = source_account_id
        elif account.planets_account_id != source_account_id:
            raise PrivateSyncError(
                "linked account id changed during sync"
            )

        account.last_verified_at = datetime.now(timezone.utc)
        account.last_error = None

        result = persist_private_turn(
            session,
            game_id=game_id,
            observer_planets_account_id=linked_account_id,
            payload=payload,
        )

        session.commit()

    return {
        "linked_account_id": linked_account_id,
        "planets_account_id": source_account_id,
        "planets_username": planets_username,
        **result,
    }

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
from app.planetsnu.activity import load_ingame_activity
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.services.game_activity import persist_game_activity_observations
from app.services.game_rule_catalog import persist_game_rule_catalog
from app.services.private_auxiliary import persist_private_auxiliary_observations


class PrivateSyncError(RuntimeError):
    pass


class PrivateSyncTransportError(PrivateSyncError):
    pass


async def sync_private_game(
    linked_account_id: int,
    game_id: int,
    turn: int | None = None,
) -> dict[str, Any]:
    if turn is not None and turn <= 0:
        raise PrivateSyncError("turn must be positive")

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
    game_activity: list[dict[str, Any]] = []
    game_activity_error: str | None = None

    try:
        client = PlanetsNuClient()
        payload = None
        last_transport_error: httpx.TransportError | None = None

        for attempt in range(1, 4):
            try:
                payload = await client.load_turn(
                    game_id=game_id,
                    api_key=api_key,
                    turn=turn,
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

        if turn is None:
            probe_rst = payload.get("rst")
            probe_player = (
                probe_rst.get("player")
                if isinstance(probe_rst, dict)
                and isinstance(probe_rst.get("player"), dict)
                else None
            )
            probe_player_id = (
                probe_player.get("id")
                if isinstance(probe_player, dict)
                else None
            )
            if (
                isinstance(probe_player_id, int)
                and not isinstance(probe_player_id, bool)
                and probe_player_id > 0
            ):
                try:
                    game_activity = await load_ingame_activity(
                        client,
                        api_key=api_key,
                        game_id=game_id,
                        player_id=probe_player_id,
                        planets_account_id=expected_planets_account_id,
                    )
                except PlanetsNuError as exc:
                    game_activity_error = str(exc)
            else:
                game_activity_error = (
                    "loadturn has no valid player id for ingameactivity"
                )

    finally:
        del api_key

    rst = payload.get("rst")

    if not isinstance(rst, dict):
        raise PrivateSyncError(
            "private turn has no rst object"
        )

    game_payload = rst.get("game")
    if not isinstance(game_payload, dict):
        raise PrivateSyncError(
            "private turn has no game object"
        )

    returned_turn = game_payload.get("turn")
    if isinstance(returned_turn, bool) or not isinstance(returned_turn, int):
        raise PrivateSyncError(
            "private turn has invalid game turn"
        )

    if turn is not None and returned_turn != turn:
        raise PrivateSyncError(
            "Planets.nu returned a different historical turn "
            f"(requested {turn}, got {returned_turn})"
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

        persist_game_rule_catalog(
            session,
            game_id=game_id,
            turn=returned_turn,
            rst=rst,
        )

        result = persist_private_turn(
            session,
            game_id=game_id,
            observer_planets_account_id=linked_account_id,
            payload=payload,
        )

        auxiliary = persist_private_auxiliary_observations(
            session,
            game_id=game_id,
            turn=returned_turn,
            batch_id=int(result["batch_id"]),
            rst=rst,
        )

        activity_result = {
            "game_activity_seen": 0,
            "game_activity_inserted": 0,
        }
        if turn is None and game_activity:
            activity_result = persist_game_activity_observations(
                session,
                observer_planets_account_id=linked_account_id,
                game_id=game_id,
                activity=game_activity,
            )

        session.commit()

    response = {
        "linked_account_id": linked_account_id,
        "planets_account_id": source_account_id,
        "planets_username": planets_username,
        "requested_turn": turn,
        **result,
        **auxiliary,
        **activity_result,
    }
    if game_activity_error is not None:
        response["game_activity_error"] = game_activity_error
    return response

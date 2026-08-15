import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.intel.observations.private_turn import persist_private_turn
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.activity import load_ingame_activity, load_private_activity
from app.planetsnu.client import PlanetsNuClient, PlanetsNuError
from app.services.game_activity import persist_game_activity_observations
from app.services.game_rule_catalog import persist_game_rule_catalog
from app.services.private_auxiliary import persist_private_auxiliary_observations


class PrivateSyncError(RuntimeError):
    pass


class PrivateSyncTransportError(PrivateSyncError):
    pass


@dataclass(frozen=True)
class ResolvedObserverIdentity:
    player_slot_id: int
    planets_account_id: int
    username: str
    source: str


def _record_game_id(raw: dict[str, Any]) -> int | None:
    value = raw.get("gameid")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _is_unknown_player_sentinel(player: dict[str, Any]) -> bool:
    return (
        player.get("id") == 0
        and player.get("accountid") == 0
        and isinstance(player.get("username"), str)
        and player["username"].strip().casefold() == "unknown"
    )


def _resolve_observer_identity(
    *,
    game_id: int,
    player: dict[str, Any],
    expected_planets_account_id: int | None,
    planets_username: str,
) -> ResolvedObserverIdentity:
    """Resolve the authenticated observer without accepting ambiguous payloads.

    Active players normally identify themselves directly in rst.player. A dead
    player can instead receive Planets.nu's all-zero/"unknown" sentinel. In that
    one explicit case we fall back only to an already verified linked account
    and one unique canonical game slot for the same account + username.
    """

    raw_slot_id = _positive_int(player.get("id"))
    raw_account_id = _positive_int(player.get("accountid"))
    raw_username = player.get("username")

    if _is_unknown_player_sentinel(player):
        if expected_planets_account_id is None:
            raise PrivateSyncError(
                "private turn uses unknown player sentinel and linked account "
                "has no verified Planets.nu account id"
            )

        with SessionLocal() as session:
            candidates = list(
                session.execute(
                    select(GamePlayerSlot).where(
                        GamePlayerSlot.game_id == game_id,
                        GamePlayerSlot.account_id == expected_planets_account_id,
                    )
                ).scalars().all()
            )

        username_key = planets_username.strip().casefold()
        candidates = [
            slot
            for slot in candidates
            if slot.username.strip().casefold() == username_key
        ]
        if len(candidates) != 1:
            raise PrivateSyncError(
                "private turn uses unknown player sentinel but canonical "
                "observer slot is not uniquely verified"
            )

        slot = candidates[0]
        return ResolvedObserverIdentity(
            player_slot_id=slot.slot_id,
            planets_account_id=expected_planets_account_id,
            username=planets_username,
            source="canonical_slot_for_unknown_player",
        )

    if raw_slot_id is None:
        raise PrivateSyncError("private turn has invalid player id")
    if raw_account_id is None:
        raise PrivateSyncError("private turn has invalid account id")
    if not isinstance(raw_username, str):
        raise PrivateSyncError("private turn has invalid username")
    if raw_username.strip().casefold() != planets_username.strip().casefold():
        raise PrivateSyncError(
            "private turn username does not match linked Planets.nu account"
        )
    if (
        expected_planets_account_id is not None
        and raw_account_id != expected_planets_account_id
    ):
        raise PrivateSyncError(
            "private turn belongs to a different Planets.nu account"
        )

    with SessionLocal() as session:
        slot = session.execute(
            select(GamePlayerSlot).where(
                GamePlayerSlot.game_id == game_id,
                GamePlayerSlot.slot_id == raw_slot_id,
            )
        ).scalar_one_or_none()

    if slot is None:
        raise PrivateSyncError(
            "observer player slot is not present in canonical database; "
            "run public sync first"
        )
    if slot.account_id != raw_account_id:
        raise PrivateSyncError(
            "canonical player slot account id does not match authenticated private turn"
        )
    if slot.username.strip().casefold() != raw_username.strip().casefold():
        raise PrivateSyncError(
            "canonical player slot username does not match authenticated private turn"
        )

    return ResolvedObserverIdentity(
        player_slot_id=raw_slot_id,
        planets_account_id=raw_account_id,
        username=raw_username,
        source="loadturn_player",
    )


def _payload_with_resolved_player_slot(
    payload: dict[str, Any],
    *,
    player_slot_id: int,
) -> dict[str, Any]:
    """Build a persistence view with canonical batch provenance only.

    persist_private_turn reads rst.player.id solely to stamp the observation
    batch source slot. Entity payloads remain untouched. This avoids recording
    source_player_slot_id=0 when Planets.nu returns its dead-player sentinel.
    """

    rst = payload.get("rst")
    if not isinstance(rst, dict):
        return payload
    player = rst.get("player")
    if not isinstance(player, dict) or player.get("id") == player_slot_id:
        return payload

    normalized_player = dict(player)
    normalized_player["id"] = player_slot_id
    normalized_rst = dict(rst)
    normalized_rst["player"] = normalized_player
    normalized_payload = dict(payload)
    normalized_payload["rst"] = normalized_rst
    return normalized_payload


async def sync_private_game(
    linked_account_id: int,
    game_id: int,
    turn: int | None = None,
) -> dict[str, Any]:
    if turn is not None and turn <= 0:
        raise PrivateSyncError("turn must be positive")

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(PlanetsAccount.id == linked_account_id)
        ).scalar_one_or_none()
        if account is None:
            raise PrivateSyncError("linked Planets.nu account not found")
        if not account.is_active:
            raise PrivateSyncError("linked Planets.nu account is inactive")

        encrypted_api_key = account.api_key_encrypted
        expected_planets_account_id = account.planets_account_id
        planets_username = account.planets_username

    api_key = decrypt_credential(encrypted_api_key)
    game_activity: list[dict[str, Any]] = []
    ingame_activity_seen = 0
    private_activity_seen = 0
    game_activity_error: str | None = None
    private_activity_error: str | None = None

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

        rst = payload.get("rst")
        if not isinstance(rst, dict):
            raise PrivateSyncError("private turn has no rst object")

        game_payload = rst.get("game")
        if not isinstance(game_payload, dict):
            raise PrivateSyncError("private turn has no game object")

        returned_turn = game_payload.get("turn")
        if isinstance(returned_turn, bool) or not isinstance(returned_turn, int):
            raise PrivateSyncError("private turn has invalid game turn")
        if turn is not None and returned_turn != turn:
            raise PrivateSyncError(
                "Planets.nu returned a different historical turn "
                f"(requested {turn}, got {returned_turn})"
            )

        player = rst.get("player")
        if not isinstance(player, dict):
            raise PrivateSyncError("private turn has no player object")

        identity = _resolve_observer_identity(
            game_id=game_id,
            player=player,
            expected_planets_account_id=expected_planets_account_id,
            planets_username=planets_username,
        )

        if turn is None:
            try:
                ingame_activity = await load_ingame_activity(
                    client,
                    api_key=api_key,
                    game_id=game_id,
                    player_id=identity.player_slot_id,
                    planets_account_id=identity.planets_account_id,
                )
                ingame_activity_seen = len(ingame_activity)
                game_activity.extend(ingame_activity)
            except PlanetsNuError as exc:
                game_activity_error = str(exc)

            try:
                private_activity = await load_private_activity(
                    client,
                    api_key=api_key,
                    game_id=game_id,
                    player_id=identity.player_slot_id,
                    planets_account_id=identity.planets_account_id,
                )
                private_for_game = [
                    raw
                    for raw in private_activity
                    if _record_game_id(raw) == game_id
                ]
                private_activity_seen = len(private_for_game)
                game_activity.extend(private_for_game)
            except PlanetsNuError as exc:
                private_activity_error = str(exc)

    finally:
        del api_key

    with SessionLocal() as session:
        game_exists = session.execute(
            select(Game.id).where(Game.id == game_id)
        ).scalar_one_or_none()
        if game_exists is None:
            raise PrivateSyncError(
                "game is not present in canonical database; run public sync first"
            )

        account = session.execute(
            select(PlanetsAccount).where(PlanetsAccount.id == linked_account_id)
        ).scalar_one()
        if account.planets_account_id is None:
            account.planets_account_id = identity.planets_account_id
        elif account.planets_account_id != identity.planets_account_id:
            raise PrivateSyncError("linked account id changed during sync")

        account.last_verified_at = datetime.now(timezone.utc)
        account.last_error = None

        persist_game_rule_catalog(
            session,
            game_id=game_id,
            turn=returned_turn,
            rst=rst,
        )
        persistence_payload = _payload_with_resolved_player_slot(
            payload,
            player_slot_id=identity.player_slot_id,
        )
        result = persist_private_turn(
            session,
            game_id=game_id,
            observer_planets_account_id=linked_account_id,
            payload=persistence_payload,
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
        "planets_account_id": identity.planets_account_id,
        "planets_username": identity.username,
        "observer_identity_source": identity.source,
        "requested_turn": turn,
        "ingame_activity_seen": ingame_activity_seen,
        "private_activity_seen": private_activity_seen,
        **result,
        **auxiliary,
        **activity_result,
    }
    if game_activity_error is not None:
        response["game_activity_error"] = game_activity_error
    if private_activity_error is not None:
        response["private_activity_error"] = private_activity_error
    return response

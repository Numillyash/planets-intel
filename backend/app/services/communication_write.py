from html import unescape
import re
from typing import Any

from sqlalchemy import select

from app.core.credentials import decrypt_credential
from app.db.session import SessionLocal
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount
from app.planetsnu.client import (
    PlanetsNuAmbiguousWriteError,
    PlanetsNuClient,
    PlanetsNuError,
)
from app.services.game_activity import (
    get_owned_game_activity,
    mark_outgoing_private_message,
)
from app.services.private_sync import PrivateSyncError, sync_private_game


class CommunicationWriteError(RuntimeError):
    pass


class CommunicationWriteUpstreamError(CommunicationWriteError):
    """Planets.nu returned a definite error for the requested write."""


class CommunicationWriteAmbiguousError(CommunicationWriteError):
    """The upstream write may have succeeded but IntelBoard received no answer."""


_BR_RE = re.compile(r"<br\s*/?>", flags=re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _explicit_true(value: Any) -> bool:
    return value is True or (isinstance(value, int) and not isinstance(value, bool) and value == 1)


def _message_key(value: str | None) -> str:
    if value is None:
        return ""
    normalized = _BR_RE.sub("\n", value)
    normalized = _TAG_RE.sub("", normalized)
    normalized = unescape(normalized)
    return normalized.replace("\r\n", "\n").replace("\r", "\n").strip()


def _load_owned_account(*, user_id: int, linked_account_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if account is None:
            raise CommunicationWriteError("Linked Planets.nu account not found")
        return {
            "id": account.id,
            "username": account.planets_username,
            "planets_account_id": account.planets_account_id,
            "api_key_encrypted": account.api_key_encrypted,
        }


def _validate_sender(
    *,
    payload: dict[str, Any],
    account: dict[str, Any],
    game_id: int,
) -> tuple[int, int]:
    if not _explicit_true(payload.get("canmessage")):
        raise CommunicationWriteError(
            "Planets.nu did not explicitly allow messaging for this observer"
        )

    rst = payload.get("rst")
    if not isinstance(rst, dict):
        raise CommunicationWriteError("Current private turn has no rst object")
    player = rst.get("player")
    if not isinstance(player, dict):
        raise CommunicationWriteError("Current private turn has no player object")

    player_id = _positive_int(player.get("id"))
    planets_account_id = _positive_int(player.get("accountid"))
    username = player.get("username")
    if player_id is None or planets_account_id is None or not isinstance(username, str):
        raise CommunicationWriteError(
            "Current private turn does not identify a writable player slot"
        )
    if username.strip().casefold() != str(account["username"]).strip().casefold():
        raise CommunicationWriteError(
            "Current private turn belongs to a different username"
        )
    expected_account_id = account.get("planets_account_id")
    if expected_account_id is not None and planets_account_id != expected_account_id:
        raise CommunicationWriteError(
            "Current private turn belongs to a different Planets.nu account"
        )

    with SessionLocal() as session:
        slot = session.execute(
            select(GamePlayerSlot).where(
                GamePlayerSlot.game_id == game_id,
                GamePlayerSlot.slot_id == player_id,
            )
        ).scalar_one_or_none()
    if slot is None:
        raise CommunicationWriteError("Sender slot is not present in canonical game roster")
    if slot.account_id != planets_account_id:
        raise CommunicationWriteError("Sender slot account id does not match current private turn")
    if slot.username.strip().casefold() != username.strip().casefold():
        raise CommunicationWriteError("Sender slot username does not match current private turn")
    if slot.status != 1 or slot.race_id >= 100:
        raise CommunicationWriteError("Sender slot is not an active human player")

    return player_id, planets_account_id


def _validate_recipients(
    *,
    game_id: int,
    sender_player_id: int,
    requested_player_ids: list[int],
) -> tuple[list[int], dict[int, int | None]]:
    recipient_ids = list(dict.fromkeys(requested_player_ids))
    # Verified official-client behavior: no recipients is Public Board mode and
    # sends no `to` field. Sender validation still applies unchanged.
    if not recipient_ids:
        return [], {}
    if sender_player_id in recipient_ids:
        raise CommunicationWriteError("Cannot send an in-game message to the sender slot")

    with SessionLocal() as session:
        slots = list(
            session.execute(
                select(GamePlayerSlot).where(
                    GamePlayerSlot.game_id == game_id,
                    GamePlayerSlot.slot_id.in_(recipient_ids),
                )
            ).scalars().all()
        )

    by_id = {slot.slot_id: slot for slot in slots}
    missing = [slot_id for slot_id in recipient_ids if slot_id not in by_id]
    if missing:
        raise CommunicationWriteError(
            "Recipient slots are not present in canonical game roster: "
            + ", ".join(str(item) for item in missing)
        )

    account_ids: dict[int, int | None] = {}
    for slot_id in recipient_ids:
        slot = by_id[slot_id]
        if slot.status != 1 or slot.race_id >= 100:
            raise CommunicationWriteError(
                f"Recipient slot {slot_id} is not an active human player"
            )
        account_ids[slot_id] = slot.account_id if slot.account_id and slot.account_id > 0 else None

    return recipient_ids, account_ids


def _activity_ids(activity: dict[str, object] | None) -> set[int]:
    if activity is None:
        return set()
    items = activity.get("items")
    if not isinstance(items, list):
        return set()
    result: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("activity_id")
        if isinstance(value, int) and not isinstance(value, bool):
            result.add(value)
    return result


def _reconciled_activity_id(
    *,
    activity: dict[str, object] | None,
    previous_activity_ids: set[int],
    sender_planets_account_id: int,
    recipient_account_ids: dict[int, int | None],
    body: str,
    game_id: int,
) -> int | None:
    if activity is None:
        return None
    items = activity.get("items")
    if not isinstance(items, list):
        return None

    expected_body = _message_key(body)
    concrete_targets = {
        value
        for value in recipient_account_ids.values()
        if value is not None
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        activity_id = item.get("activity_id")
        if not isinstance(activity_id, int) or activity_id in previous_activity_ids:
            continue
        if item.get("source_id") != sender_planets_account_id:
            continue
        raw_message = item.get("message")
        if _message_key(raw_message if isinstance(raw_message, str) else None) != expected_body:
            continue

        if not recipient_account_ids:
            # Runtime capture of an official Public Board post showed this exact
            # activity shape: target=game, targettype=2, scope=2.
            if item.get("target_id") != game_id:
                continue
            if item.get("target_type") != 2 or item.get("scope") != 2:
                continue
            return activity_id

        # For a single private recipient, require the factual target account
        # when Planets.nu supplies one. Multi-recipient roots can omit one
        # target id; the explicit successful write supplies recipient provenance.
        if len(recipient_account_ids) == 1 and concrete_targets:
            target_id = item.get("target_id")
            if isinstance(target_id, int) and target_id not in concrete_targets:
                continue
        return activity_id
    return None


def _reconciled_message(
    *,
    activity: dict[str, object] | None,
    previous_activity_ids: set[int],
    sender_planets_account_id: int,
    recipient_account_ids: dict[int, int | None],
    body: str,
    game_id: int = 0,
) -> bool:
    # Compatibility wrapper retained for focused unit tests.
    return _reconciled_activity_id(
        activity=activity,
        previous_activity_ids=previous_activity_ids,
        sender_planets_account_id=sender_planets_account_id,
        recipient_account_ids=recipient_account_ids,
        body=body,
        game_id=game_id,
    ) is not None


async def send_owned_game_message(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    recipient_player_ids: list[int],
    body: str,
) -> dict[str, object]:
    message_body = body.strip()
    if not message_body:
        raise CommunicationWriteError("Message body must not be blank")

    account = _load_owned_account(
        user_id=user_id,
        linked_account_id=linked_account_id,
    )
    previous_activity = get_owned_game_activity(
        user_id=user_id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        limit=2000,
    )
    previous_activity_ids = _activity_ids(previous_activity)

    api_key = decrypt_credential(str(account["api_key_encrypted"]))
    try:
        client = PlanetsNuClient()
        try:
            current = await client.load_turn(game_id=game_id, api_key=api_key)
        except PlanetsNuError as exc:
            raise CommunicationWriteUpstreamError(str(exc)) from exc
        sender_player_id, sender_planets_account_id = _validate_sender(
            payload=current,
            account=account,
            game_id=game_id,
        )
        recipients, recipient_account_ids = _validate_recipients(
            game_id=game_id,
            sender_player_id=sender_player_id,
            requested_player_ids=recipient_player_ids,
        )

        try:
            upstream = await client.send_message(
                game_id=game_id,
                player_id=sender_player_id,
                api_key=api_key,
                recipient_player_ids=recipients,
                body=message_body,
            )
        except PlanetsNuAmbiguousWriteError as exc:
            raise CommunicationWriteAmbiguousError(
                "Message delivery is unknown because the Planets.nu response was lost. "
                "IntelBoard did not retry the write. Refresh communications before sending again."
            ) from exc
        except PlanetsNuError as exc:
            raise CommunicationWriteUpstreamError(str(exc)) from exc
    finally:
        del api_key

    reconciliation_detail: str | None = None
    reconciled = False
    try:
        await sync_private_game(linked_account_id=linked_account_id, game_id=game_id)
        refreshed = get_owned_game_activity(
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            limit=2000,
        )
        reconciled_activity_id = _reconciled_activity_id(
            activity=refreshed,
            previous_activity_ids=previous_activity_ids,
            sender_planets_account_id=sender_planets_account_id,
            recipient_account_ids=recipient_account_ids,
            body=message_body,
            game_id=game_id,
        )
        reconciled = reconciled_activity_id is not None
        if reconciled_activity_id is not None and recipients:
            mark_outgoing_private_message(
                linked_account_id=linked_account_id,
                game_id=game_id,
                activity_id=reconciled_activity_id,
                recipient_player_ids=recipients,
            )
        if not reconciled:
            reconciliation_detail = (
                "Planets.nu accepted the send request, but the new outgoing activity "
                "was not yet observed in the refreshed communications feed."
            )
    except (PrivateSyncError, PlanetsNuError) as exc:
        reconciliation_detail = (
            "Planets.nu accepted the send request, but post-send communications "
            f"refresh failed: {type(exc).__name__}."
        )

    upstream_html = upstream.get("html")
    return {
        "game_id": game_id,
        "linked_account_id": linked_account_id,
        "sender_player_id": sender_player_id,
        "recipient_player_ids": recipients,
        "upstream_accepted": True,
        "reconciled": reconciled,
        "upstream_html": upstream_html if isinstance(upstream_html, str) else None,
        "reconciliation_detail": reconciliation_detail,
    }

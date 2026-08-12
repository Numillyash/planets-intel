from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.game_player_slot import GamePlayerSlot
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.historical_intel import _owned_primary_account
from app.services.intel_access import accessible_intel_accounts


def historical_intel_status(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
) -> dict[str, Any] | None:
    primary = _owned_primary_account(
        user_id=user_id,
        linked_account_id=linked_account_id,
    )
    if primary is None:
        return None

    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = [account.id for account in accessible]

    with SessionLocal() as session:
        game = session.execute(
            select(Game).where(Game.id == game_id)
        ).scalar_one_or_none()
        if game is None:
            return None

        member_account_ids = set(
            session.execute(
                select(GamePlayerSlot.account_id).where(
                    GamePlayerSlot.game_id == game_id,
                    GamePlayerSlot.account_id.is_not(None),
                )
            ).scalars().all()
        )

        rows = (
            session.execute(
                select(
                    PrivateObservationBatch.observer_planets_account_id,
                    PrivateObservationBatch.turn,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                )
                .distinct()
                .order_by(
                    PrivateObservationBatch.observer_planets_account_id,
                    PrivateObservationBatch.turn,
                )
            ).all()
            if accessible_ids
            else []
        )

    turns_by_account: dict[int, set[int]] = {
        account.id: set()
        for account in accessible
    }
    for account_id, turn in rows:
        turns_by_account.setdefault(account_id, set()).add(turn)

    def participates(account) -> bool:
        # A linked account without a resolved Planets account id may still be
        # a player; treat it as eligible until a private turn resolves it.
        return (
            account.planets_account_id is None
            or account.planets_account_id in member_account_ids
        )

    participating = [
        account
        for account in accessible
        if participates(account)
    ]
    participating_turn_sets = [
        turns_by_account[account.id]
        for account in participating
    ]

    union_turns = sorted(
        set().union(*participating_turn_sets)
        if participating_turn_sets
        else set()
    )
    complete_turns = sorted(
        set.intersection(*participating_turn_sets)
        if participating_turn_sets
        and all(participating_turn_sets)
        else set()
    )

    return {
        "game_id": game_id,
        "current_turn": game.current_turn,
        "primary_linked_account_id": linked_account_id,
        "accounts": [
            {
                "linked_account_id": account.id,
                "planets_username": account.planets_username,
                "is_owned": account.is_owned,
                "participates_in_game": participates(account),
                "turns": sorted(turns_by_account.get(account.id, set())),
            }
            for account in accessible
        ],
        "available_turns": union_turns,
        "complete_turns": complete_turns,
    }

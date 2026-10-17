"""Probe one public finished RST through the exact production archive adapter.

Only metadata/field counts are printed; the RST itself, account keys, messages,
private game identifiers and potentially identifying player names are not logged.
This script uses no linked observer and persists nothing.
"""
from __future__ import annotations

import argparse
import asyncio

from app.services.public_archive_turn import fetch_finished_public_turn


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", required=True, type=int)
    parser.add_argument("--player-id", required=True, type=int)
    parser.add_argument("--turn", required=True, type=int)
    args = parser.parse_args()
    result = await fetch_finished_public_turn(
        args.game_id, args.player_id, args.turn,
    )
    if (
        result["game_id"] != args.game_id
        or result["player_slot_id"] != args.player_id
        or result["turn"] != args.turn
    ):
        raise RuntimeError("Archive identity mismatch")
    print("PUBLIC_ARCHIVE_PROBE_OK")
    print("source:", result["source"])
    print("game/slot/turn:", result["game_id"], result["player_slot_id"], result["turn"])
    print("counts:", result["counts"])
    print("stellar_features:", len(result["stellar_cartography"]))


if __name__ == "__main__":
    asyncio.run(main())

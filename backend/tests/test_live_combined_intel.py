import unittest
from types import SimpleNamespace

from app.services.accessible_combined_intel import _select_live_snapshots
from app.services.combined_intel import _Snapshot, _merge_ships


def _snapshot(
    *,
    account_id: int,
    batch_id: int,
    batch_turn: int,
    ships=None,
):
    account = SimpleNamespace(
        id=account_id,
        planets_username=f"observer-{account_id}",
    )
    batch = SimpleNamespace(
        id=batch_id,
        turn=batch_turn,
        source_player_slot_id=account_id,
        observed_at=f"2026-10-03T00:00:0{account_id}+00:00",
    )
    return _Snapshot(
        account=account,
        batch=batch,
        planets=[],
        ships=list(ships or []),
        starbases=[],
        stellar_cartography=[],
    )


class LiveCombinedIntelSourceTests(unittest.TestCase):
    def test_stale_primary_is_kept_for_identity_but_not_live_entities(self):
        stale_primary = _snapshot(
            account_id=1,
            batch_id=101,
            batch_turn=49,
        )
        current_peer = _snapshot(
            account_id=2,
            batch_id=202,
            batch_turn=52,
        )

        live, primary = _select_live_snapshots(
            [stale_primary, current_peer],
            linked_account_id=1,
            current_turn=52,
        )

        self.assertIs(primary, stale_primary)
        self.assertEqual(live, [current_peer])

    def test_only_exact_current_turn_batches_contribute_to_live_union(self):
        previous_turn = _snapshot(
            account_id=1,
            batch_id=101,
            batch_turn=51,
        )
        current_a = _snapshot(
            account_id=2,
            batch_id=202,
            batch_turn=52,
        )
        current_b = _snapshot(
            account_id=3,
            batch_id=303,
            batch_turn=52,
        )

        live, _ = _select_live_snapshots(
            [previous_turn, current_a, current_b],
            linked_account_id=2,
            current_turn=52,
        )

        self.assertEqual(live, [current_a, current_b])

    def test_current_snapshot_can_still_carry_older_last_seen_entity_info(self):
        ship = SimpleNamespace(
            ship_id=85,
            owner_id=3,
            info_turn=49,
            hull_id=29,
            name="DARK WING CLASS BATTLESHIP",
            x=1636,
            y=1976,
            warp=0,
            payload={},
        )
        current_snapshot = _snapshot(
            account_id=2,
            batch_id=202,
            batch_turn=52,
            ships=[ship],
        )

        live, _ = _select_live_snapshots(
            [current_snapshot],
            linked_account_id=2,
            current_turn=52,
        )
        merged = _merge_ships(live)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["ship_id"], 85)
        self.assertEqual(merged[0]["info_turn"], 49)


if __name__ == "__main__":
    unittest.main()

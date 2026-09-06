import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services.background_private_refresh import (
    _remote_game_is_refresh_candidate,
    discover_live_private_refresh_targets,
    refresh_all_running_private_intel_once,
)


EMPTY_DISCOVERY = {
    "accounts": 0,
    "failures": 0,
    "remote_games_seen": 0,
    "candidate_games_seen": 0,
    "targets": [],
}


class BackgroundPrivateRefreshTests(unittest.TestCase):
    def test_live_discovered_new_game_joins_canonical_refresh_targets(self) -> None:
        async_refresh = AsyncMock(
            side_effect=[
                {"turn": 10, "refreshed": 2, "cached": 0, "skipped": 0, "failed": 0},
                {"turn": 10, "refreshed": 2, "cached": 0, "skipped": 0, "failed": 0},
            ]
        )
        discovery = {
            **EMPTY_DISCOVERY,
            "accounts": 2,
            "remote_games_seen": 5,
            "candidate_games_seen": 2,
            "targets": [(7, 684653)],
        }

        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(7, 1001)],
            ),
            patch(
                "app.services.background_private_refresh.discover_live_private_refresh_targets",
                AsyncMock(return_value=discovery),
            ),
            patch(
                "app.services.background_private_refresh.accessible_refresh_account_ids",
                return_value=(11, 12),
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        self.assertEqual(result["canonical_targets"], 1)
        self.assertEqual(result["discovered_targets"], 1)
        self.assertEqual(result["raw_targets"], 2)
        self.assertEqual(result["targets"], 2)
        self.assertEqual(result["deduplicated"], 0)
        calls = {
            (call.kwargs["user_id"], call.kwargs["game_id"])
            for call in async_refresh.await_args_list
        }
        self.assertEqual(calls, {(7, 1001), (7, 684653)})

    def test_live_and_canonical_copy_of_same_game_refresh_once(self) -> None:
        async_refresh = AsyncMock(
            return_value={
                "turn": 10,
                "refreshed": 2,
                "cached": 0,
                "skipped": 0,
                "failed": 0,
            }
        )
        discovery = {
            **EMPTY_DISCOVERY,
            "accounts": 1,
            "remote_games_seen": 1,
            "candidate_games_seen": 1,
            "targets": [(7, 684653)],
        }

        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(7, 684653)],
            ),
            patch(
                "app.services.background_private_refresh.discover_live_private_refresh_targets",
                AsyncMock(return_value=discovery),
            ),
            patch(
                "app.services.background_private_refresh.accessible_refresh_account_ids",
                return_value=(11, 12),
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        self.assertEqual(result["canonical_targets"], 1)
        self.assertEqual(result["discovered_targets"], 1)
        self.assertEqual(result["raw_targets"], 1)
        self.assertEqual(result["targets"], 1)
        self.assertEqual(async_refresh.await_count, 1)

    def test_identical_shared_observer_sets_are_refreshed_once_per_game(self) -> None:
        async_refresh = AsyncMock(
            return_value={
                "turn": 4,
                "refreshed": 4,
                "cached": 0,
                "skipped": 0,
                "failed": 0,
            }
        )

        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(1, 683335), (2, 683335)],
            ),
            patch(
                "app.services.background_private_refresh.discover_live_private_refresh_targets",
                AsyncMock(return_value=EMPTY_DISCOVERY),
            ),
            patch(
                "app.services.background_private_refresh.accessible_refresh_account_ids",
                side_effect=lambda _user_id: (1, 2, 3, 4),
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        self.assertEqual(result["raw_targets"], 2)
        self.assertEqual(result["targets"], 1)
        self.assertEqual(result["deduplicated"], 1)
        self.assertEqual(async_refresh.await_count, 1)
        self.assertEqual(async_refresh.await_args.kwargs["game_id"], 683335)

    def test_different_shared_observer_sets_are_not_collapsed(self) -> None:
        async_refresh = AsyncMock(
            return_value={
                "turn": 4,
                "refreshed": 1,
                "cached": 0,
                "skipped": 0,
                "failed": 0,
            }
        )

        def access_set(user_id: int) -> tuple[int, ...]:
            return (1, 2, 3, 4) if user_id == 1 else (2, 4)

        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(1, 683335), (2, 683335)],
            ),
            patch(
                "app.services.background_private_refresh.discover_live_private_refresh_targets",
                AsyncMock(return_value=EMPTY_DISCOVERY),
            ),
            patch(
                "app.services.background_private_refresh.accessible_refresh_account_ids",
                side_effect=access_set,
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        self.assertEqual(result["targets"], 2)
        self.assertEqual(result["deduplicated"], 0)
        self.assertEqual(async_refresh.await_count, 2)

    def test_one_failed_game_does_not_abort_other_games(self) -> None:
        async_refresh = AsyncMock(
            side_effect=[
                RuntimeError("upstream failed"),
                {"turn": 9, "refreshed": 1, "cached": 0, "skipped": 0, "failed": 0},
            ]
        )
        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(3, 2001), (3, 2002)],
            ),
            patch(
                "app.services.background_private_refresh.discover_live_private_refresh_targets",
                AsyncMock(return_value=EMPTY_DISCOVERY),
            ),
            patch(
                "app.services.background_private_refresh.accessible_refresh_account_ids",
                return_value=(31,),
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        statuses = sorted(item["status"] for item in result["results"])
        self.assertEqual(statuses, ["failed", "ok"])

    def test_remote_game_candidate_accepts_running_and_joining_only(self) -> None:
        self.assertTrue(
            _remote_game_is_refresh_candidate(
                {"id": 684653, "status": 2, "statusname": "Running"}
            )
        )
        self.assertTrue(
            _remote_game_is_refresh_candidate(
                {"id": "684654", "status": 1, "statusname": "Joining"}
            )
        )
        self.assertFalse(
            _remote_game_is_refresh_candidate(
                {"id": 684655, "status": 3, "statusname": "Finished"}
            )
        )
        self.assertFalse(
            _remote_game_is_refresh_candidate(
                {"id": None, "status": 2, "statusname": "Running"}
            )
        )

    def test_live_discovery_surfaces_new_running_game_without_canonical_membership(self) -> None:
        client = Mock()
        client.games_for_username = AsyncMock(
            return_value=[
                {"id": 684653, "status": 2, "statusname": "Running"},
                {"id": 999001, "status": 3, "statusname": "Finished"},
            ]
        )

        with (
            patch(
                "app.services.background_private_refresh._active_live_discovery_accounts",
                return_value=[(7, "georgul")],
            ),
            patch(
                "app.services.background_private_refresh.PlanetsNuClient",
                return_value=client,
            ),
        ):
            result = asyncio.run(discover_live_private_refresh_targets())

        self.assertEqual(result["accounts"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["remote_games_seen"], 2)
        self.assertEqual(result["candidate_games_seen"], 1)
        self.assertEqual(result["targets"], [(7, 684653)])
        client.games_for_username.assert_awaited_once_with("georgul")

    def test_one_failed_live_discovery_account_does_not_hide_other_accounts(self) -> None:
        failed_client = Mock()
        failed_client.games_for_username = AsyncMock(
            side_effect=RuntimeError("games/list failed")
        )
        working_client = Mock()
        working_client.games_for_username = AsyncMock(
            return_value=[
                {"id": 684653, "status": 2, "statusname": "Running"},
            ]
        )

        with (
            patch(
                "app.services.background_private_refresh._active_live_discovery_accounts",
                return_value=[(7, "georgul"), (8, "helping die")],
            ),
            patch(
                "app.services.background_private_refresh.PlanetsNuClient",
                side_effect=[failed_client, working_client],
            ),
        ):
            result = asyncio.run(discover_live_private_refresh_targets())

        self.assertEqual(result["accounts"], 2)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["targets"], [(8, 684653)])


if __name__ == "__main__":
    unittest.main()

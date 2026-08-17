import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.background_private_refresh import (
    refresh_all_running_private_intel_once,
)


class BackgroundPrivateRefreshTests(unittest.TestCase):
    def test_refreshes_every_running_target_without_browser_context(self) -> None:
        async_refresh = AsyncMock(
            side_effect=[
                {"turn": 10, "refreshed": 2, "cached": 0, "skipped": 0, "failed": 0},
                {"turn": 16, "refreshed": 3, "cached": 1, "skipped": 0, "failed": 0},
            ]
        )
        with (
            patch(
                "app.services.background_private_refresh.running_private_refresh_targets",
                return_value=[(7, 1001), (7, 1002)],
            ),
            patch(
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        self.assertEqual(result["targets"], 2)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(item["status"] == "ok" for item in result["results"]))
        calls = {
            (call.kwargs["user_id"], call.kwargs["game_id"])
            for call in async_refresh.await_args_list
        }
        self.assertEqual(calls, {(7, 1001), (7, 1002)})

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
                "app.services.background_private_refresh.refresh_accessible_private_intel",
                async_refresh,
            ),
        ):
            result = asyncio.run(refresh_all_running_private_intel_once())

        statuses = sorted(item["status"] for item in result["results"])
        self.assertEqual(statuses, ["failed", "ok"])


if __name__ == "__main__":
    unittest.main()

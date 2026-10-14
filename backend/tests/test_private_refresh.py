import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.planetsnu.client import PlanetsNuError
from app.services.private_refresh import (
    _resolve_refresh_turn,
    refresh_accessible_private_intel,
)


class PrivateRefreshTurnResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefers_live_public_turn(self) -> None:
        with patch(
            "app.services.private_refresh.sync_public_game",
            new=AsyncMock(return_value={"turn": 23}),
        ), patch(
            "app.services.private_refresh._canonical_current_turn",
            return_value=22,
        ) as canonical_turn:
            turn, diagnostic = await _resolve_refresh_turn(682909)

        self.assertEqual(turn, 23)
        self.assertEqual(diagnostic["status"], "refreshed")
        self.assertEqual(diagnostic["source"], "planetsnu-public")
        canonical_turn.assert_not_called()

    async def test_public_transport_failure_uses_canonical_turn(self) -> None:
        with patch(
            "app.services.private_refresh.sync_public_game",
            new=AsyncMock(side_effect=httpx.ReadTimeout("public unavailable")),
        ), patch(
            "app.services.private_refresh._canonical_current_turn",
            return_value=12,
        ):
            turn, diagnostic = await _resolve_refresh_turn(682909)

        self.assertEqual(turn, 12)
        self.assertEqual(diagnostic["status"], "canonical-fallback")
        self.assertEqual(diagnostic["source"], "canonical-cache")
        self.assertIn("cached turn 12", diagnostic["detail"])
        self.assertIn("ReadTimeout", diagnostic["detail"])

    async def test_public_failure_without_cache_still_fails_closed(self) -> None:
        with patch(
            "app.services.private_refresh.sync_public_game",
            new=AsyncMock(side_effect=httpx.ConnectError("public unavailable")),
        ), patch(
            "app.services.private_refresh._canonical_current_turn",
            return_value=None,
        ):
            with self.assertRaises(httpx.ConnectError):
                await _resolve_refresh_turn(999999)

    async def test_dead_observer_is_skipped_without_loadturn(self) -> None:
        account = {
            "id": 1,
            "planets_username": "georgul",
            "planets_account_id": 33734,
            "is_owned": True,
        }
        sync_private = AsyncMock()
        with (
            patch(
                "app.services.private_refresh._resolve_refresh_turn",
                new=AsyncMock(
                    return_value=(19, {
                        "status": "refreshed",
                        "source": "planetsnu-public",
                        "detail": None,
                    })
                ),
            ),
            patch(
                "app.services.private_refresh._accessible_accounts",
                return_value=[account],
            ),
            patch(
                "app.services.private_refresh._account_private_refresh_state",
                return_value="inactive",
            ),
            patch(
                "app.services.private_refresh.sync_private_game",
                new=sync_private,
            ),
        ):
            result = await refresh_accessible_private_intel(
                user_id=1,
                game_id=684779,
            )

        sync_private.assert_not_awaited()
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertIn("inactive/dead", result["results"][0]["detail"])

    async def test_private_api_error_detail_is_preserved(self) -> None:
        account = {
            "id": 1,
            "planets_username": "georgul",
            "planets_account_id": 33734,
            "is_owned": True,
        }
        with (
            patch(
                "app.services.private_refresh._resolve_refresh_turn",
                new=AsyncMock(
                    return_value=(19, {
                        "status": "refreshed",
                        "source": "planetsnu-public",
                        "detail": None,
                    })
                ),
            ),
            patch(
                "app.services.private_refresh._accessible_accounts",
                return_value=[account],
            ),
            patch(
                "app.services.private_refresh._account_private_refresh_state",
                return_value="active",
            ),
            patch(
                "app.services.private_refresh._latest_batch",
                return_value=None,
            ),
            patch(
                "app.services.private_refresh.sync_private_game",
                new=AsyncMock(
                    side_effect=PlanetsNuError(
                        "You do not have permission to view this turn."
                    )
                ),
            ),
        ):
            result = await refresh_accessible_private_intel(
                user_id=1,
                game_id=684779,
            )

        self.assertEqual(result["failed"], 1)
        self.assertEqual(
            result["results"][0]["detail"],
            "You do not have permission to view this turn.",
        )


if __name__ == "__main__":
    unittest.main()

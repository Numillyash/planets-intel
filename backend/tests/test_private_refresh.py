import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.private_refresh import _resolve_refresh_turn


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


if __name__ == "__main__":
    unittest.main()

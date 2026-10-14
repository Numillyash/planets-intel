"""Owner-only preview regression tests with fake identities, no private corpus."""
import unittest
from unittest.mock import MagicMock, patch

from app.services.game_intel_grants import GrantNotFound
from app.services.game_intel_preview import preview_game_grant


class GameIntelPreviewSecurityTests(unittest.TestCase):
    @patch("app.services.game_intel_preview.SessionLocal")
    def test_grantee_cannot_preview_grantor_private_data(self, factory):
        context = MagicMock()
        factory.return_value = context
        with patch("app.services.game_intel_preview._owned", return_value=None):
            with self.assertRaises(GrantNotFound):
                preview_game_grant(
                    user_id=9, game_id=8, grant_id=7, linked_account_id=6,
                )

    @patch("app.services.game_intel_preview.SessionLocal")
    def test_wrong_game_or_non_grantor_account_denied(self, factory):
        context = MagicMock()
        context.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
        factory.return_value = context
        with patch("app.services.game_intel_preview._owned") as owned:
            owned.return_value.id = 21
            with self.assertRaises(GrantNotFound):
                preview_game_grant(
                    user_id=9, game_id=11, grant_id=7, linked_account_id=21,
                )
        call = context.__enter__.return_value.execute.call_args
        self.assertIsNotNone(call)
        self.assertIn("game_intel_grants", str(call.args[0]).lower())


if __name__ == "__main__":
    unittest.main()

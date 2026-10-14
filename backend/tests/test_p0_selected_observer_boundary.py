"""P0 containment regressions using only synthetic account IDs."""
import ast
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.intel_access import accessible_intel_accounts
from app.services.intel_sharing import (
    IntelShareForbidden,
    accept_dashboard_intel_share,
    active_dashboard_peer_account_ids,
    request_dashboard_intel_share,
)
from app.services.private_refresh import _accessible_accounts
from app.services.combat_state import (
    combat_state_map,
    latest_ship_combat_state,
    upsert_combat_state,
)


class SelectedObserverBoundaryTests(unittest.TestCase):
    @staticmethod
    def _session_returning(value):
        context = MagicMock()
        context.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = value
        return context

    @patch("app.services.intel_access.SessionLocal")
    def test_owned_primary_is_the_only_private_source_even_with_global_shares(self, local):
        local.return_value = self._session_returning(SimpleNamespace(
            id=12, planets_account_id=902, planets_username="synthetic-owned",
        ))
        for game_id in (71, 72):
            with self.subTest(game_id=game_id):
                accounts = accessible_intel_accounts(
                    user_id=4, game_id=game_id, linked_account_id=12,
                )
                self.assertEqual([a.id for a in accounts], [12])
                self.assertTrue(accounts[0].is_owned)

    @patch("app.services.intel_access.SessionLocal")
    def test_peer_as_primary_is_denied(self, local):
        local.return_value = self._session_returning(None)
        self.assertEqual(accessible_intel_accounts(
            user_id=4, game_id=71, linked_account_id=17,
        ), [])

    @patch("app.services.intel_access.SessionLocal")
    def test_unknown_game_or_primary_fails_closed(self, local):
        for game_id, account_id in ((0, 12), (71, 0), (-1, 12)):
            self.assertEqual(accessible_intel_accounts(
                user_id=4, game_id=game_id, linked_account_id=account_id,
            ), [])
        local.assert_not_called()

    def test_unscoped_authorization_api_cannot_be_called(self):
        with self.assertRaises(TypeError):
            accessible_intel_accounts(user_id=4)

    def test_global_share_creation_acceptance_and_peer_lookup_disabled(self):
        with self.assertRaises(IntelShareForbidden):
            request_dashboard_intel_share(
                user_id=4, source_account_id=12,
                target_planets_username="synthetic-peer",
            )
        with self.assertRaises(IntelShareForbidden):
            accept_dashboard_intel_share(
                user_id=4, share_id=3, account_id=12,
            )
        self.assertEqual(active_dashboard_peer_account_ids(linked_account_id=12), [])

    @patch("app.services.private_refresh.SessionLocal")
    def test_background_refresh_uses_only_owned_rows(self, local):
        account = SimpleNamespace(id=12, planets_username="synthetic-owned",
                                  planets_account_id=902)
        context = MagicMock()
        context.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = [account]
        local.return_value = context
        result = _accessible_accounts(4)
        self.assertEqual([a["id"] for a in result], [12])
        self.assertEqual([a["is_owned"] for a in result], [True])

    def test_unattributed_analyst_annotations_are_quarantined(self):
        self.assertEqual(combat_state_map(user_id=4, game_id=71, turn=9), {})
        self.assertIsNone(latest_ship_combat_state(
            user_id=4, game_id=71, ship_id=7, through_turn=9,
        ))
        self.assertIsNone(upsert_combat_state(
            user_id=4, game_id=71, turn=9, vcr_id=2, ship_id=7,
            post_combat_torpedoes=0, post_combat_fighters=None, note=None,
        ))

    def test_all_private_access_invocations_require_game_and_observer(self):
        services = pathlib.Path(__file__).parents[1] / "app" / "services"
        for path in services.glob("*.py"):
            syntax = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(syntax):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "accessible_intel_accounts":
                    continue
                kwargs = {kw.arg for kw in node.keywords}
                with self.subTest(path=path.name, line=node.lineno):
                    self.assertTrue(
                        {"user_id", "game_id", "linked_account_id"}.issubset(kwargs),
                        f"unscoped authorization in {path.name}:{node.lineno}",
                    )


if __name__ == "__main__":
    unittest.main()

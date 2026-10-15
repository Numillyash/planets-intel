"""Security-negative tests for recipient-scoped, game/turn-bound peer reads."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.game import Game
from app.models.planets_account import PlanetsAccount
from app.services.game_intel_grants import GrantForbidden, GrantNotFound
from app.services.game_intel_read import get_received_game_intel
from app.services.intel_grant_projection import project_current_grant_batch


NOW = datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)


def result(rows=None, first=None):
    response = MagicMock()
    response.scalars.return_value.all.return_value = rows if rows is not None else []
    response.scalars.return_value.first.return_value = first
    return response


def context(grants=None, batch=None):
    fake = MagicMock()
    source = SimpleNamespace(id=33, user_id=8, is_active=True)
    game = SimpleNamespace(id=17, status_id=2, current_turn=43)
    fake.get.side_effect = lambda model, key: game if model is Game else source if model is PlanetsAccount else None
    fake.execute.side_effect = [result(rows=grants or []), result(first=batch)] if grants else [result(rows=[])]
    cm = MagicMock()
    cm.__enter__.return_value = fake
    return cm, fake, source


def grant(**changes):
    fields = dict(
        id=71, game_id=17, grantor_account_id=33, grantee_account_id=22,
        grantor_slot_id=3, grantee_slot_id=4,
        status="consented_pending_policy", sharing_mode="unrestricted",
        requested_scopes=["owned_planet_details", "ship_friendly_codes"],
        consented_at=NOW, expanded_disclosure_confirmed_at=NOW,
        revoked_at=None,
    )
    return SimpleNamespace(**(fields | changes))


class ScopedRecipientReadTests(unittest.TestCase):
    def _run(self, fake_context, *, recipient_id=22, roster=(3, 4, 43)):
        with (
            patch("app.services.game_intel_read.get_settings",
                  return_value=SimpleNamespace(intel_expanded_sharing_enabled=True)),
            patch("app.services.game_intel_read.SessionLocal", return_value=fake_context),
            patch("app.services.game_intel_read._owned",
                  return_value=SimpleNamespace(id=22, user_id=9, is_active=True)),
            patch("app.services.game_intel_read._roster", return_value=roster),
            patch("app.services.game_intel_read.project_current_grant_batch",
                  return_value={"planets": [{"planet_id": 1, "fields": {"temp": 60}}],
                                "ships": [], "starbases": [],
                                "messages": [], "combat_events": [],
                                "third_party_contacts": []}) as projection,
        ):
            output = get_received_game_intel(
                user_id=9, game_id=17, linked_account_id=recipient_id,
            )
            return output, projection

    @patch("app.services.game_intel_read.get_settings")
    @patch("app.services.game_intel_read.SessionLocal")
    def test_default_off_denies_even_perfect_consent(self, session, settings):
        settings.return_value.intel_expanded_sharing_enabled = False
        with self.assertRaises(GrantForbidden):
            get_received_game_intel(user_id=9, game_id=17, linked_account_id=22)
        session.assert_not_called()

    def test_valid_direct_consent_reads_only_projected_fields(self):
        batch = SimpleNamespace(id=101, turn=43, observed_at=NOW + timedelta(minutes=1))
        cm, s, _ = context([grant()], batch)
        output, projection = self._run(cm)
        self.assertEqual(output["mode"], "scoped_partner_intel")
        self.assertEqual(len(output["sources"]), 1)
        self.assertEqual(output["sources"][0]["source_batch_id"], 101)
        self.assertEqual(output["sources"][0]["planets"][0]["fields"], {"temp": 60})
        projection.assert_called_once()
        args = projection.call_args.kwargs
        self.assertEqual((args["grantor_slot"], args["grantee_slot"]), (3, 4))
        self.assertEqual(args["scopes"], frozenset(grant().requested_scopes))
        self.assertEqual(s.execute.call_count, 2)
        sql = str(s.execute.call_args.args[0])
        self.assertIn("private_observation_batches.game_id", sql)
        self.assertIn("private_observation_batches.observed_at >=", sql)

    def test_no_matching_consent_returns_no_sources(self):
        cm, _, _ = context()
        output, projection = self._run(cm)
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()

    def test_stale_roster_denies_even_existing_grant(self):
        cm, _, _ = context([grant()], batch=SimpleNamespace(id=101))
        output, projection = self._run(cm, roster=(3, 9, 43))
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()

    def test_preconsent_or_absent_current_batch_not_shared(self):
        cm, s, _ = context([grant()], batch=None)
        output, projection = self._run(cm)
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()
        query = str(s.execute.call_args.args[0])
        self.assertIn("private_observation_batches.turn", query)
        self.assertIn("private_observation_batches.observed_at >=", query)

    def test_sql_filters_revoked_unconsented_and_wrong_game_grants(self):
        cm, s, _ = context()
        output, projection = self._run(cm)
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()
        sql = str(s.execute.call_args.args[0])
        for predicate in (
            "game_intel_grants.game_id",
            "game_intel_grants.grantee_account_id",
            "game_intel_grants.revoked_at IS NULL",
            "game_intel_grants.consented_at IS NOT NULL",
            "game_intel_grants.expanded_disclosure_confirmed_at IS NOT NULL",
        ):
            self.assertIn(predicate, sql)

    def test_history_without_ship_history_opt_in_is_denied(self):
        cm, _, _ = context([grant()], batch=SimpleNamespace(id=101))
        with (
            patch("app.services.game_intel_read.get_settings",
                  return_value=SimpleNamespace(intel_expanded_sharing_enabled=True)),
            patch("app.services.game_intel_read.SessionLocal", return_value=cm),
            patch("app.services.game_intel_read._owned",
                  return_value=SimpleNamespace(id=22, user_id=9)),
            patch("app.services.game_intel_read.project_current_grant_batch") as project,
        ):
            answer = get_received_game_intel(
                user_id=9, game_id=17, linked_account_id=22,
                requested_turn=42,
            )
        self.assertEqual(answer["sources"], [])
        project.assert_not_called()

    def test_history_before_consent_turn_remains_denied(self):
        cm, _, _ = context([grant(requested_scopes=["ship_history", "ship_orders"],
                                     membership_verified_turn=43)],
                           batch=SimpleNamespace(id=101))
        with (
            patch("app.services.game_intel_read.get_settings",
                  return_value=SimpleNamespace(intel_expanded_sharing_enabled=True)),
            patch("app.services.game_intel_read.SessionLocal", return_value=cm),
            patch("app.services.game_intel_read._owned",
                  return_value=SimpleNamespace(id=22, user_id=9)),
            patch("app.services.game_intel_read.project_current_grant_batch") as project,
        ):
            answer = get_received_game_intel(
                user_id=9, game_id=17, linked_account_id=22,
                requested_turn=42,
            )
        self.assertEqual(answer["sources"], [])
        project.assert_not_called()

    def test_current_turn_history_is_available_with_explicit_opt_in(self):
        cm, s, _ = context(
            [grant(requested_scopes=["ship_history", "owned_planet_details"])],
            batch=SimpleNamespace(id=101, turn=43),
        )
        with (
            patch("app.services.game_intel_read.get_settings",
                  return_value=SimpleNamespace(intel_expanded_sharing_enabled=True)),
            patch("app.services.game_intel_read.SessionLocal", return_value=cm),
            patch("app.services.game_intel_read._owned",
                  return_value=SimpleNamespace(id=22, user_id=9)),
            patch("app.services.game_intel_read._roster", return_value=(3, 4, 43)),
            patch("app.services.game_intel_read.project_current_grant_batch",
                  return_value={"planets": [], "ships": [], "starbases": [],
                                "messages": [], "combat_events": [],
                                "third_party_contacts": []}) as project,
        ):
            answer = get_received_game_intel(
                user_id=9, game_id=17, linked_account_id=22,
                requested_turn=43,
            )
        self.assertEqual(len(answer["sources"]), 1)
        self.assertEqual(answer["turn"], 43)
        project.assert_called_once()
        self.assertIn("private_observation_batches.turn",
                      str(s.execute.call_args.args[0]))

    def test_inactive_source_is_denied(self):
        cm, _, source = context([grant()], batch=SimpleNamespace(id=101))
        source.is_active = False
        output, projection = self._run(cm)
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()

    def test_unauthorized_scope_is_rejected_even_if_database_tampered(self):
        cm, _, _ = context([grant(requested_scopes=["owned_ship_details", "raw_loadturn"])],
                           batch=SimpleNamespace(id=101))
        output, projection = self._run(cm)
        self.assertEqual(output["sources"], [])
        projection.assert_not_called()

    @patch("app.services.game_intel_read.get_settings")
    @patch("app.services.game_intel_read.SessionLocal")
    @patch("app.services.game_intel_read._owned", return_value=None)
    def test_forged_primary_account_denied(self, owned, session, settings):
        settings.return_value.intel_expanded_sharing_enabled = True
        session.return_value, _, _ = context()
        with self.assertRaises(GrantNotFound):
            get_received_game_intel(user_id=9, game_id=17, linked_account_id=999)


class ScopedProjectionMessageTests(unittest.TestCase):
    def test_only_a_message_by_grantor_to_grantee_is_projected(self):
        def message(owner, target):
            return SimpleNamespace(
                message_id=owner * 10 + target, message_turn=43,
                owner_id=owner, target_id=target,
                headline="Fixture", body="Synthetic only",
            )
        fake = MagicMock()
        fake.execute.side_effect = [
            result(rows=[]), result(rows=[]), result(rows=[]),
            result(rows=[
                message(3, 4), message(8, 3), message(3, 8),
                message(4, 3),
            ]),
        ]
        snapshot = project_current_grant_batch(
            fake,
            batch=SimpleNamespace(id=101, turn=43),
            scopes=frozenset({"private_messages"}),
            grantor_slot=3, grantee_slot=4,
        )
        self.assertEqual(len(snapshot["messages"]), 1)
        self.assertEqual(snapshot["messages"][0]["owner_id"], 3)
        self.assertEqual(snapshot["messages"][0]["target_id"], 4)
        self.assertNotIn("Synthetic only", str(snapshot["planets"]))
        self.assertEqual(snapshot["third_party_contacts"], [])


if __name__ == "__main__":
    unittest.main()

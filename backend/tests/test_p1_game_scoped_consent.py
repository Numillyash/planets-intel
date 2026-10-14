"""P1 game-grant authorization regressions with synthetic identities only."""
import inspect
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.game_intel_grant import GameIntelGrant
from app.schemas.game_intel_grants import GameGrantRequest, GameGrantResponse
from app.services.game_intel_grants import (
    GrantConflict, GrantNotFound, _slot, _roster,
    request_game_grant, consent_game_grant, revoke_game_grant,
    has_private_read_authority_from_grant,
)
from app.services.intel_access import accessible_intel_accounts


def fake_session(*rows):
    context = MagicMock()
    session = context.__enter__.return_value
    session.execute.side_effect = [
        SimpleNamespace(
            scalar_one_or_none=lambda row=row: row,
            scalars=lambda row=row: SimpleNamespace(all=lambda: row),
        )
        for row in rows
    ]
    return context


class P1GameGrantTests(unittest.TestCase):
    def test_only_explicit_field_families_are_valid(self):
        for scope in ("private_message", "entire_private_loadturn"):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                GameGrantRequest(
                    grantor_account_id=11,
                    grantee_planets_username="fixture-other",
                    requested_scopes=[scope],
                )

    def test_consented_record_cannot_be_marked_as_authority(self):
        now = datetime.now(timezone.utc)
        fields = dict(
            id=1, game_id=100, grantor_account_id=11,
            grantee_account_id=12, grantor_slot_id=3,
            grantee_slot_id=4, membership_verified_turn=21,
            requested_scopes=["owned_unit_locations"],
            status="consented_pending_policy", authorizes_private_intel=True,
            consented_at=now, revoked_at=None, created_at=now, updated_at=now,
        )
        with self.assertRaises(ValueError):
            GameGrantResponse(**fields)
        fields["authorizes_private_intel"] = False
        self.assertFalse(GameGrantResponse(**fields).authorizes_private_intel)

    def test_game_scoped_consent_never_authorizes_raw_peer_reads(self):
        for game_id in (100, 101):
            self.assertFalse(has_private_read_authority_from_grant(
                user_id=3, game_id=game_id, account_id=12,
            ))
        self.assertNotIn("GameIntelGrant", inspect.getsource(accessible_intel_accounts))

    @patch("app.services.game_intel_grants.SessionLocal")
    def test_invalid_and_duplicate_scopes_fail_without_db(self, factory):
        for values in ([], ["private_message"], ["combat_vcr_evidence", "combat_vcr_evidence"]):
            with self.subTest(scopes=values), self.assertRaises(GrantConflict):
                request_game_grant(
                    user_id=3, game_id=100, grantor_account_id=11,
                    grantee_planets_username="fixture-other", requested_scopes=values,
                )
        factory.assert_not_called()

    @patch("app.services.game_intel_grants.SessionLocal")
    def test_source_must_be_owned(self, factory):
        factory.return_value = fake_session(None)
        with self.assertRaises(GrantNotFound):
            request_game_grant(
                user_id=3, game_id=100, grantor_account_id=11,
                grantee_planets_username="fixture-other",
                requested_scopes=["third_party_contacts"],
            )

    def test_roster_staleness_and_ambiguity_fail_closed(self):
        acct = SimpleNamespace(planets_username="fixture-a", planets_account_id=17)
        game = SimpleNamespace(id=100, current_turn=21)
        with fake_session([]) as s:
            self.assertIsNone(_slot(s, game, acct))
        row = SimpleNamespace(slot_id=3, username="fixture-a", account_id=17)
        with fake_session([row, row]) as s:
            self.assertIsNone(_slot(s, game, acct))

    def test_conflicting_verified_account_id_fails_closed(self):
        acct = SimpleNamespace(planets_username="fixture-a", planets_account_id=17)
        game = SimpleNamespace(id=100, current_turn=21)
        row = SimpleNamespace(slot_id=3, username="fixture-a", account_id=999)
        with fake_session([row]) as s:
            self.assertIsNone(_slot(s, game, acct))

    def test_unknown_game_denies_consent_request(self):
        session = MagicMock()
        session.get.return_value = None
        with self.assertRaises(GrantConflict):
            _roster(session, 100, SimpleNamespace(), SimpleNamespace())

    @patch("app.services.game_intel_grants.SessionLocal")
    def test_consent_requires_target_ownership(self, factory):
        factory.return_value = fake_session(None)
        with self.assertRaises(GrantNotFound):
            consent_game_grant(
                user_id=3, game_id=100, grant_id=7, grantee_account_id=11,
            )

    @patch("app.services.game_intel_grants.SessionLocal")
    def test_third_party_cannot_revoke_someone_elses_game_grant(self, factory):
        outsider = SimpleNamespace(id=50)
        row = SimpleNamespace(id=7, game_id=100,
            grantor_account_id=11, grantee_account_id=12)
        factory.return_value = fake_session(outsider, row)
        with self.assertRaises(GrantNotFound):
            revoke_game_grant(user_id=3, game_id=100, grant_id=7, account_id=50)

    def test_database_boundary_and_revocation_index_exist(self):
        cols = GameIntelGrant.__table__.columns
        for name in ("game_id", "grantor_account_id", "grantee_account_id",
                     "grantor_slot_id", "grantee_slot_id", "requested_scopes",
                     "consented_at", "revoked_at", "membership_verified_turn"):
            self.assertIn(name, cols)
        idx = next(i for i in GameIntelGrant.__table__.indexes
                   if i.name == "uq_game_intel_grant_unrevoked")
        self.assertTrue(idx.unique)
        self.assertIsNotNone(idx.dialect_options["postgresql"]["where"])


if __name__ == "__main__":
    unittest.main()

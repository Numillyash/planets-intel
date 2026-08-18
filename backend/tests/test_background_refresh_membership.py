import unittest

from sqlalchemy.dialects import postgresql

from app.services.background_private_refresh import _membership_join_condition


class BackgroundRefreshMembershipTests(unittest.TestCase):
    def test_external_account_id_match_is_guarded_against_null(self) -> None:
        sql = str(
            _membership_join_condition().compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("planets_accounts.planets_account_id IS NOT NULL", sql)
        self.assertIn("planets_accounts.planets_account_id > 0", sql)
        self.assertIn(
            "game_player_slots.account_id = planets_accounts.planets_account_id",
            sql,
        )

    def test_username_fallback_requires_nonempty_linked_username(self) -> None:
        sql = str(
            _membership_join_condition().compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("length(trim(planets_accounts.planets_username)) > 0", sql)
        self.assertIn(
            "lower(game_player_slots.username) = lower(planets_accounts.planets_username)",
            sql,
        )


if __name__ == "__main__":
    unittest.main()

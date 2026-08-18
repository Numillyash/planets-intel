import unittest
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from app.services.private_refresh import _is_account_in_game


class _ScalarOneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _CaptureSession:
    def __init__(self, result):
        self.result = result
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, statement):
        self.statement = statement
        return _ScalarOneResult(self.result)


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class PrivateRefreshMembershipTests(unittest.TestCase):
    def test_username_fallback_matches_when_external_id_is_missing(self) -> None:
        session = _CaptureSession(3)
        with patch("app.services.private_refresh.SessionLocal", return_value=session):
            result = _is_account_in_game(
                planets_account_id=None,
                planets_username="  GeOrGuL  ",
                game_id=682909,
            )

        self.assertTrue(result)
        sql = _sql(session.statement)
        self.assertIn("game_player_slots.game_id = 682909", sql)
        self.assertIn("lower(game_player_slots.username) = 'georgul'", sql)
        self.assertNotIn("game_player_slots.account_id IS NULL", sql)

    def test_username_fallback_remains_available_for_sentinel_id(self) -> None:
        session = _CaptureSession(7)
        with patch("app.services.private_refresh.SessionLocal", return_value=session):
            result = _is_account_in_game(
                planets_account_id=0,
                planets_username="leno4ka",
                game_id=682909,
            )

        self.assertTrue(result)
        sql = _sql(session.statement)
        self.assertIn("lower(game_player_slots.username) = 'leno4ka'", sql)
        self.assertNotIn("game_player_slots.account_id = 0", sql)

    def test_no_usable_identity_is_unknown_not_false(self) -> None:
        self.assertIsNone(
            _is_account_in_game(
                planets_account_id=None,
                planets_username="   ",
                game_id=682909,
            )
        )

    def test_valid_external_id_and_username_are_both_allowed(self) -> None:
        session = _CaptureSession(5)
        with patch("app.services.private_refresh.SessionLocal", return_value=session):
            result = _is_account_in_game(
                planets_account_id=33734,
                planets_username="georgul",
                game_id=682909,
            )

        self.assertTrue(result)
        sql = _sql(session.statement)
        self.assertIn("game_player_slots.account_id = 33734", sql)
        self.assertIn("lower(game_player_slots.username) = 'georgul'", sql)
        self.assertIn(" OR ", sql)


if __name__ == "__main__":
    unittest.main()

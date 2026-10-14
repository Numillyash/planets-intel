import unittest
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from app.services.cached_game_details import (
    _current_activity,
    _current_scores,
)


class _ScalarResult:
    def all(self):
        return []


class _ExecuteResult:
    def scalars(self):
        return _ScalarResult()


class _CaptureSession:
    def __init__(self) -> None:
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, statement):
        self.statement = statement
        return _ExecuteResult()


def _compiled(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class CachedGameDetailsTurnCompatibilityTests(unittest.TestCase):
    def test_scores_query_exact_current_turn_only(self) -> None:
        session = _CaptureSession()
        with patch(
            "app.services.cached_game_details.SessionLocal",
            return_value=session,
        ):
            self.assertEqual(_current_scores(682932, 11), {})

        sql = _compiled(session.statement)
        self.assertIn("score_observations.game_id = 682932", sql)
        self.assertIn("score_observations.turn = 11", sql)
        self.assertNotIn("score_observations.turn <= 11", sql)

    def test_activity_query_exact_current_turn_only(self) -> None:
        session = _CaptureSession()
        with patch(
            "app.services.cached_game_details.SessionLocal",
            return_value=session,
        ):
            self.assertEqual(_current_activity(682932, 11), {})

        sql = _compiled(session.statement)
        self.assertIn("player_turn_activity_observations.game_id = 682932", sql)
        self.assertIn("player_turn_activity_observations.turn = 11", sql)
        self.assertNotIn("player_turn_activity_observations.turn <= 11", sql)


if __name__ == "__main__":
    unittest.main()

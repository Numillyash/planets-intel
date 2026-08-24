import unittest

from app.models.game_activity_observation import GameActivityObservation
from app.models.game_player_slot import GamePlayerSlot
from app.services.game_activity import (
    _activity_semantics,
    _legacy_private_partner_from_root,
    flatten_activity_records,
)


class GameActivityFlattenTests(unittest.TestCase):
    def test_flattens_nested_replies_and_deduplicates_ids(self) -> None:
        records = [
            {
                "id": 100,
                "message": "root",
                "_replies": [
                    {
                        "id": 101,
                        "message": "reply",
                        "_replies": [
                            {"id": 102, "message": "nested"},
                        ],
                    },
                    {"id": 101, "message": "duplicate reply"},
                ],
            }
        ]

        flattened = flatten_activity_records(records)
        self.assertEqual([item["id"] for item in flattened], [100, 101, 102])

    def test_skips_records_without_positive_activity_id(self) -> None:
        records = [
            {"id": 0, "message": "zero"},
            {"id": -1, "message": "negative"},
            {"message": "missing"},
            {"id": 7, "message": "valid"},
        ]

        self.assertEqual(
            [item["id"] for item in flatten_activity_records(records)],
            [7],
        )


class GameActivitySemanticTests(unittest.TestCase):
    def test_direct_thread_reply_inherits_private_partner(self) -> None:
        root = GameActivityObservation(
            activity_id=100,
            activity_type=1,
            scope=3,
            visibility_source="private_activity",
            outgoing_recipient_player_ids=None,
            parent_id=0,
            source_id=33734,
            source_name="observer",
            target_id=90192,
            target_name="other player",
            target_type=1,
        )
        reply = GameActivityObservation(
            activity_id=101,
            activity_type=1,
            scope=3,
            visibility_source="private_activity",
            outgoing_recipient_player_ids=None,
            parent_id=100,
            source_id=90192,
            source_name="other player",
            target_id=0,
            target_name=None,
            target_type=0,
        )
        rows_by_id = {100: root, 101: reply}

        root_semantics = _activity_semantics(
            root,
            rows_by_id=rows_by_id,
            observer_account_id=33734,
        )
        reply_semantics = _activity_semantics(
            reply,
            rows_by_id=rows_by_id,
            observer_account_id=33734,
        )

        self.assertEqual(root_semantics["kind"], "private_message")
        self.assertEqual(reply_semantics["kind"], "private_message")
        self.assertEqual(reply_semantics["thread_root_id"], 100)
        self.assertEqual(reply_semantics["conversation_with_id"], 90192)
        self.assertEqual(reply_semantics["conversation_with_name"], "other player")
        self.assertEqual(reply_semantics["conversation_player_ids"], [])

    def test_outgoing_group_write_is_private_and_preserves_slot_set(self) -> None:
        root = GameActivityObservation(
            activity_id=130,
            activity_type=1,
            scope=2,
            visibility_source="outgoing_private_write",
            outgoing_recipient_player_ids=[7, 2, 7],
            parent_id=0,
            source_id=33734,
            source_name="observer",
            target_id=683545,
            target_name="Kaye's World Sector",
            target_type=2,
        )
        semantics = _activity_semantics(
            root,
            rows_by_id={130: root},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")
        self.assertEqual(semantics["thread_root_id"], 130)
        self.assertEqual(semantics["conversation_player_ids"], [2, 7])

    def test_reply_inherits_outgoing_group_slot_set_from_root(self) -> None:
        root = GameActivityObservation(
            activity_id=135,
            activity_type=1,
            scope=2,
            visibility_source="outgoing_private_write",
            outgoing_recipient_player_ids=[2, 7],
            parent_id=0,
            source_id=33734,
            target_id=683545,
            target_type=2,
        )
        reply = GameActivityObservation(
            activity_id=136,
            activity_type=1,
            scope=2,
            visibility_source="ingame_activity",
            outgoing_recipient_player_ids=None,
            parent_id=135,
            source_id=90192,
            target_id=0,
            target_type=0,
        )
        semantics = _activity_semantics(
            reply,
            rows_by_id={135: root, 136: reply},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")
        self.assertEqual(semantics["conversation_player_ids"], [2, 7])

    def test_private_feed_provenance_beats_targetless_nonprivate_shape(self) -> None:
        root = GameActivityObservation(
            activity_id=140,
            activity_type=1,
            scope=2,
            visibility_source="private_activity",
            outgoing_recipient_player_ids=None,
            parent_id=0,
            source_id=33734,
            source_name="observer",
            target_id=0,
            target_name=None,
            target_type=0,
        )
        semantics = _activity_semantics(
            root,
            rows_by_id={140: root},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")
        self.assertEqual(semantics["thread_root_id"], 140)
        self.assertIsNone(semantics["conversation_with_id"])

    def test_reply_inherits_private_feed_provenance_from_root(self) -> None:
        root = GameActivityObservation(
            activity_id=145,
            activity_type=1,
            scope=2,
            visibility_source="private_activity",
            outgoing_recipient_player_ids=None,
            parent_id=0,
            source_id=33734,
            target_id=0,
            target_type=0,
        )
        reply = GameActivityObservation(
            activity_id=146,
            activity_type=1,
            scope=2,
            visibility_source="ingame_activity",
            outgoing_recipient_player_ids=None,
            parent_id=145,
            source_id=90192,
            target_id=0,
            target_type=0,
        )
        semantics = _activity_semantics(
            reply,
            rows_by_id={145: root, 146: reply},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")
        self.assertEqual(semantics["thread_root_id"], 145)

    def test_targetless_scope_three_root_stays_private_for_legacy_rows(self) -> None:
        root = GameActivityObservation(
            activity_id=150,
            activity_type=1,
            scope=3,
            visibility_source=None,
            outgoing_recipient_player_ids=None,
            parent_id=0,
            source_id=33734,
            source_name="observer",
            target_id=0,
            target_name=None,
            target_type=0,
        )
        semantics = _activity_semantics(
            root,
            rows_by_id={150: root},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")
        self.assertEqual(semantics["thread_root_id"], 150)
        self.assertIsNone(semantics["conversation_with_id"])
        self.assertIsNone(semantics["conversation_with_name"])

    def test_orphan_scope_three_reply_stays_private_for_legacy_rows(self) -> None:
        reply = GameActivityObservation(
            activity_id=151,
            activity_type=1,
            scope=3,
            visibility_source=None,
            outgoing_recipient_player_ids=None,
            parent_id=150,
            source_id=90192,
            source_name="other player",
            target_id=0,
            target_name=None,
            target_type=0,
        )
        semantics = _activity_semantics(
            reply,
            rows_by_id={151: reply},
            observer_account_id=33734,
        )

        self.assertEqual(semantics["kind"], "private_message")

    def test_unproven_player_visibility_stays_general(self) -> None:
        row = GameActivityObservation(
            activity_id=200,
            activity_type=1,
            scope=2,
            visibility_source="ingame_activity",
            outgoing_recipient_player_ids=None,
            parent_id=0,
            source_id=1,
            target_id=0,
            target_type=0,
        )
        semantics = _activity_semantics(
            row,
            rows_by_id={200: row},
            observer_account_id=33734,
        )
        self.assertEqual(semantics["kind"], "player_message")
        self.assertIsNone(semantics["conversation_with_id"])


class LegacyPrivatePartnerTests(unittest.TestCase):
    @staticmethod
    def _slot(
        slot_id: int,
        account_id: int,
        username: str,
    ) -> GamePlayerSlot:
        return GamePlayerSlot(
            game_id=683545,
            slot_id=slot_id,
            account_id=account_id,
            username=username,
            race_id=1,
            status=1,
            first_seen_turn=1,
            last_seen_turn=17,
        )

    def test_incoming_targetless_private_root_resolves_source_from_roster(self) -> None:
        root = GameActivityObservation(
            activity_id=7634370,
            activity_type=1,
            scope=3,
            visibility_source="private_activity",
            parent_id=0,
            source_id=90192,
            source_name="leno4ka",
            target_id=683545,
            target_name="Kaye's World Sector",
            target_type=2,
        )
        slots = [
            self._slot(3, 33734, "georgul"),
            self._slot(5, 90192, "leno4ka"),
        ]

        self.assertEqual(
            _legacy_private_partner_from_root(
                root,
                slots=slots,
                observer_account_id=33734,
            ),
            (90192, "leno4ka"),
        )

    def test_outgoing_private_root_resolves_target_when_source_is_observer(self) -> None:
        root = GameActivityObservation(
            activity_id=7634380,
            activity_type=1,
            scope=3,
            visibility_source="private_activity",
            parent_id=0,
            source_id=33734,
            source_name="georgul",
            target_id=90192,
            target_name="leno4ka",
            target_type=1,
        )
        slots = [
            self._slot(3, 33734, "georgul"),
            self._slot(5, 90192, "leno4ka"),
        ]

        self.assertEqual(
            _legacy_private_partner_from_root(
                root,
                slots=slots,
                observer_account_id=33734,
            ),
            (90192, "leno4ka"),
        )

    def test_conflicting_nonobserver_identities_fail_closed(self) -> None:
        root = GameActivityObservation(
            activity_id=7634390,
            activity_type=1,
            scope=3,
            visibility_source="private_activity",
            parent_id=0,
            source_id=90192,
            source_name="leno4ka",
            target_id=81234,
            target_name="other player",
            target_type=1,
        )
        slots = [
            self._slot(3, 33734, "georgul"),
            self._slot(5, 90192, "leno4ka"),
            self._slot(6, 81234, "other player"),
        ]

        self.assertEqual(
            _legacy_private_partner_from_root(
                root,
                slots=slots,
                observer_account_id=33734,
            ),
            (None, None),
        )


if __name__ == "__main__":
    unittest.main()

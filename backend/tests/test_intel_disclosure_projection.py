"""Synthetic field-level projection tests for optional disclosure checkboxes."""
import unittest

from app.services.intel_disclosure_projection import (
    project_owned_entity_fields, project_private_message,
)


class GameIntelFieldProjectionTests(unittest.TestCase):
    def setUp(self):
        self.ship = {
            "id": 7, "ownerid": 3, "x": 100, "y": 120,
            "name": "Fixture", "friendlycode": "SYN",
            "mission": 6, "mission1target": 12, "warp": 9,
            "engineid": 6, "beams": 4,
            "neutronium": 85, "megacredits": 600,
            "transfermegacredits": 99,
            "apikey": "NOT_A_REAL_KEY",
            "savekey": "NOT_A_REAL_KEY",
            "private_payload": {"should_never": "leak"},
        }

    def test_basic_ship_details_do_not_leak_order_code_or_finances(self):
        result = project_owned_entity_fields(
            kind="ship", raw=self.ship,
            scopes=frozenset({"owned_ship_details"}),
            owner_slot_id=3, grantor_slot_id=3,
        )
        self.assertEqual(result["engineid"], 6)
        self.assertNotIn("friendlycode", result)
        self.assertNotIn("mission", result)
        self.assertNotIn("warp", result)
        self.assertNotIn("megacredits", result)
        self.assertNotIn("apikey", result)
        self.assertNotIn("private_payload", result)

    def test_ship_code_and_orders_are_independently_controlled(self):
        result = project_owned_entity_fields(
            kind="ship", raw=self.ship,
            scopes=frozenset({"ship_friendly_codes"}),
            owner_slot_id=3, grantor_slot_id=3,
        )
        self.assertEqual(result, {"friendlycode": "SYN"})
        orders = project_owned_entity_fields(
            kind="ship", raw=self.ship,
            scopes=frozenset({"ship_orders"}),
            owner_slot_id=3, grantor_slot_id=3,
        )
        self.assertEqual(orders["mission1target"], 12)
        self.assertNotIn("friendlycode", orders)

    def test_full_opt_in_still_never_discloses_credentials_or_unknown_fields(self):
        all_categories = frozenset({
            "owned_unit_locations", "owned_ship_details",
            "financial_and_cargo", "ship_friendly_codes",
            "ship_orders", "ship_transfers",
        })
        result = project_owned_entity_fields(
            kind="ship", raw=self.ship, scopes=all_categories,
            owner_slot_id=3, grantor_slot_id=3,
        )
        for forbidden in ("apikey", "savekey", "private_payload"):
            self.assertNotIn(forbidden, result)
        self.assertEqual(result["friendlycode"], "SYN")
        self.assertEqual(result["transfermegacredits"], 99)

    def test_unknown_owner_or_foreign_entity_denies_all_fields(self):
        for owner in (None, 2):
            self.assertEqual(project_owned_entity_fields(
                kind="ship", raw=self.ship,
                scopes=frozenset({"ship_friendly_codes", "ship_orders"}),
                owner_slot_id=owner, grantor_slot_id=3,
            ), {})

    def test_unrequested_planet_code_not_smuggled_in_details(self):
        raw = {"id": 81, "ownerid": 3, "friendlycode": "ZZZ",
               "megacredits": 12, "happypoints": 68}
        details = project_owned_entity_fields(
            kind="planet", raw=raw,
            scopes=frozenset({"owned_planet_details"}),
            owner_slot_id=3, grantor_slot_id=3,
        )
        self.assertEqual(details["happypoints"], 68)
        self.assertNotIn("friendlycode", details)
        self.assertEqual(project_owned_entity_fields(
            kind="planet", raw=raw,
            scopes=frozenset({"planet_friendly_codes"}),
            owner_slot_id=3, grantor_slot_id=3,
        ), {"friendlycode": "ZZZ"})

    def test_messages_require_separate_explicit_opt_in(self):
        base = dict(message_id=1, message_turn=10, owner_id=2,
                    target_id=3, headline="Fixture", body="fixture text")
        self.assertIsNone(project_private_message(
            **base, scopes=frozenset({"owned_ship_details", "ship_orders"}),
        ))
        permitted = project_private_message(
            **base, scopes=frozenset({"private_messages"}),
        )
        self.assertEqual(permitted["body"], "fixture text")
        self.assertIsNone(project_private_message(
            **{**base, "message_id": None}, scopes=frozenset({"private_messages"}),
        ))


if __name__ == "__main__":
    unittest.main()

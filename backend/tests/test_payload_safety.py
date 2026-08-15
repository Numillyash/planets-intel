import unittest

from app.services.payload_safety import (
    sanitize_observation_payload,
    sanitize_ship_observation_payload,
)


class PayloadSafetyTests(unittest.TestCase):
    def test_own_ship_ammo_is_preserved(self):
        payload = {
            "ownerid": 5,
            "ammo": 45,
            "crew": 458,
            "damage": 0,
            "engineid": 9,
        }

        result = sanitize_ship_observation_payload(
            payload,
            observer_slot_id=5,
            owner_id=5,
        )

        self.assertEqual(result["ammo"], 45)

    def test_enemy_private_ammo_is_removed_even_when_zero(self):
        payload = {
            "ownerid": 7,
            "ammo": 0,
            "fighters": 0,
            "crew": -1,
            "damage": -1,
            "mass": 2422,
        }

        result = sanitize_ship_observation_payload(
            payload,
            observer_slot_id=5,
            owner_id=7,
        )

        self.assertNotIn("ammo", result)
        self.assertNotIn("fighters", result)
        self.assertNotIn("crew", result)
        self.assertNotIn("damage", result)
        self.assertEqual(result["mass"], 2422)

    def test_context_free_read_model_rejects_ammo_on_hidden_ship_row(self):
        payload = {
            "ammo": 0,
            "crew": -1,
            "damage": -1,
            "mass": 2422,
        }

        result = sanitize_observation_payload(payload)

        self.assertNotIn("ammo", result)
        self.assertEqual(result["mass"], 2422)

    def test_visible_zero_is_not_globally_treated_as_unknown(self):
        payload = {
            "ammo": 0,
            "crew": 458,
            "damage": 0,
            "engineid": 9,
        }

        result = sanitize_observation_payload(payload)

        self.assertEqual(result["ammo"], 0)
        self.assertEqual(result["damage"], 0)


if __name__ == "__main__":
    unittest.main()

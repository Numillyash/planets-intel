import unittest

from app.services.host_events import _parse_long_range_ship_explosion


class LongRangeExplosionParsingTests(unittest.TestCase):
    def test_parses_planets_nu_long_range_explosion(self) -> None:
        raw = {
            "body": (
                "Distress call and explosion detected at ( 1684, 1796 ) "
                "the name of the ship was: Scout"
            ),
            "headline": "Long Range Sensors",
            "id": 464,
            "messagetype": 10,
            "ownerid": 7,
            "target": 0,
            "turn": 8,
            "x": 1684,
            "y": 1796,
        }

        self.assertEqual(
            _parse_long_range_ship_explosion(raw),
            (1684, 1796, "Scout"),
        )

    def test_uses_body_coordinates_and_sanitizes_observed_name(self) -> None:
        raw = {
            "headline": "Long Range Sensors",
            "body": (
                "Distress call and explosion detected at (-12, 34) "
                "the name of the ship was: <b>  False   Flag  </b>"
            ),
            "x": 999,
            "y": 999,
        }

        self.assertEqual(
            _parse_long_range_ship_explosion(raw),
            (-12, 34, "False Flag"),
        )

    def test_rejects_same_text_from_unrecognized_headline(self) -> None:
        raw = {
            "headline": "Private message",
            "body": (
                "Distress call and explosion detected at (1684,1796) "
                "the name of the ship was: Scout"
            ),
        }

        self.assertIsNone(_parse_long_range_ship_explosion(raw))

    def test_does_not_require_or_infer_ship_id_or_owner(self) -> None:
        raw = {
            "headline": "Long Range Sensors",
            "body": (
                "Distress call and explosion detected at (1684,1796) "
                "the name of the ship was: Scout"
            ),
            "ownerid": 7,
            "target": 0,
        }

        self.assertEqual(
            _parse_long_range_ship_explosion(raw),
            (1684, 1796, "Scout"),
        )


if __name__ == "__main__":
    unittest.main()

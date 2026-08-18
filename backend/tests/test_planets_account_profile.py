import unittest
from unittest.mock import AsyncMock, patch

from app.planetsnu.client import PlanetsNuError
from app.services.planets_accounts import load_planets_profile_image_url


class PlanetsAccountProfileImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_relative_profile_image_uses_api_origin(self) -> None:
        with patch(
            "app.services.planets_accounts.PlanetsNuClient.get",
            new=AsyncMock(
                return_value={
                    "success": True,
                    "account": {
                        "id": 33734,
                        "username": "georgul",
                        "imageurl": "/33734",
                    },
                }
            ),
        ):
            result = await load_planets_profile_image_url("georgul")

        self.assertEqual(result, "https://api.planets.nu/33734")

    async def test_absolute_profile_image_is_preserved(self) -> None:
        with patch(
            "app.services.planets_accounts.PlanetsNuClient.get",
            new=AsyncMock(
                return_value={
                    "success": True,
                    "account": {
                        "imageurl": "https://cdn.example.test/profile.png",
                    },
                }
            ),
        ):
            result = await load_planets_profile_image_url("example")

        self.assertEqual(result, "https://cdn.example.test/profile.png")

    async def test_profile_failure_does_not_hide_linked_account(self) -> None:
        with patch(
            "app.services.planets_accounts.PlanetsNuClient.get",
            new=AsyncMock(side_effect=PlanetsNuError("temporary outage")),
        ):
            result = await load_planets_profile_image_url("georgul")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

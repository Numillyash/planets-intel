from typing import Any

import httpx

from app.core.config import get_settings


class PlanetsNuError(RuntimeError):
    pass


class PlanetsNuAuthError(PlanetsNuError):
    pass


class PlanetsNuClient:
    def __init__(self) -> None:
        settings = get_settings()

        self.base_url = settings.planetsnu_api_base_url.rstrip("/")

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                params=params,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PlanetsNuError(
                f"Planets.nu returned HTTP {response.status_code}"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise PlanetsNuError(
                "Planets.nu returned invalid JSON"
            ) from exc

    async def post_form(
        self,
        path: str,
        data: dict[str, Any],
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                url,
                data=data,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PlanetsNuError(
                f"Planets.nu returned HTTP {response.status_code}"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise PlanetsNuError(
                "Planets.nu returned invalid JSON"
            ) from exc

    async def login(
        self,
        username: str,
        password: str,
    ) -> str:
        payload = await self.post_form(
            "account/login",
            data={
                "username": username.strip(),
                "password": password,
            },
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu login response is not an object"
            )

        if payload.get("success") is False:
            raise PlanetsNuAuthError(
                str(
                    payload.get(
                        "error",
                        "Planets.nu authentication failed",
                    )
                )
            )

        api_key = payload.get("apikey")

        if not isinstance(api_key, str) or not api_key:
            raise PlanetsNuError(
                "Planets.nu login returned no API key"
            )

        return api_key

    async def load_info(
        self,
        game_id: int,
    ) -> dict[str, Any]:
        payload = await self.get(
            "game/loadinfo",
            params={
                "gameid": game_id,
            },
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu loadinfo response is not an object"
            )

        game = payload.get("game")

        if not isinstance(game, dict):
            raise PlanetsNuError(
                "Planets.nu loadinfo response has no game object"
            )

        return payload

    async def load_scores(
        self,
        game_id: int,
    ) -> list[dict[str, Any]]:
        payload = await self.get(
            "game/loadscores",
            params={
                "gameid": game_id,
            },
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu loadscores response is not an object"
            )

        scores = payload.get("scores")

        if not isinstance(scores, list):
            raise PlanetsNuError(
                "Planets.nu loadscores response has no scores list"
            )

        if not all(
            isinstance(score, dict)
            for score in scores
        ):
            raise PlanetsNuError(
                "Planets.nu scores list contains invalid records"
            )

        return scores

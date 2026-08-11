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
        self.proxy_url = settings.planetsnu_proxy_url or None

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            trust_env=False,
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
        headers: dict[str, str] | None = None,
        use_proxy: bool = False,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            proxy=self.proxy_url if use_proxy else None,
            trust_env=False,
        ) as client:
            response = await client.post(
                url,
                data=data,
                headers=headers,
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

    async def games_for_username(
        self,
        username: str,
    ) -> list[dict[str, Any]]:
        payload = await self.get(
            "games/list",
            params={
                "username": username.strip(),
            },
        )

        if not isinstance(payload, list):
            raise PlanetsNuError(
                "Planets.nu games/list response is not a list"
            )

        if not all(
            isinstance(game, dict)
            for game in payload
        ):
            raise PlanetsNuError(
                "Planets.nu games/list contains invalid records"
            )

        return payload


    async def load_turn(
        self,
        game_id: int,
        api_key: str,
    ) -> dict[str, Any]:
        payload = await self.post_form(
            "game/loadturn",
            data={
                "gameid": game_id,
                "apikey": api_key,
                "forsave": "true",
                "activity": "true",
            },
            headers={
                "Origin": "https://planets.nu",
                "Referer": "https://planets.nu/",
                "User-Agent": "Mozilla/5.0",
            },
            use_proxy=True,
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu loadturn response is not an object"
            )

        if payload.get("success") is False:
            raise PlanetsNuError(
                str(
                    payload.get(
                        "error",
                        "Planets.nu loadturn failed",
                    )
                )
            )

        rst = payload.get("rst")

        if not isinstance(rst, dict):
            raise PlanetsNuError(
                "Planets.nu loadturn response has no rst object"
            )

        return payload

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

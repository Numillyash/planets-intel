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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        use_proxy: bool = False,
        allow_proxy_fallback: bool = True,
    ) -> httpx.Response:
        """Perform one request path, optionally falling back direct after proxy transport failure.

        The fallback is deliberately limited to transport failures. HTTP status
        errors and API-level errors are handled by the caller and must not be
        retried through another path, because the server already answered.

        Write callers must set ``allow_proxy_fallback=False``. A transport error
        after a write request leaves delivery ambiguous; silently retrying the
        same write through another route could duplicate the user action.
        """

        primary_proxy = self.proxy_url if use_proxy else None
        attempts: list[str | None] = [primary_proxy]
        if primary_proxy is not None and allow_proxy_fallback:
            attempts.append(None)

        failures: list[str] = []
        for proxy in attempts:
            try:
                async with httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True,
                    proxy=proxy,
                    trust_env=False,
                ) as client:
                    return await client.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        headers=headers,
                    )
            except httpx.RequestError as exc:
                route = "proxy" if proxy is not None else "direct"
                failures.append(f"{route} {exc.__class__.__name__}")

        raise PlanetsNuError(
            "Planets.nu request failed: " + "; ".join(failures)
        )

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        response = await self._request(
            "GET",
            url,
            params=params,
            use_proxy=self.proxy_url is not None,
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
        allow_proxy_fallback: bool = True,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        response = await self._request(
            "POST",
            url,
            data=data,
            headers=headers,
            use_proxy=use_proxy,
            allow_proxy_fallback=allow_proxy_fallback,
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
        turn: int | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "gameid": game_id,
            "apikey": api_key,
            "forsave": "false" if turn is not None else "true",
            "activity": "false" if turn is not None else "true",
        }

        if turn is not None:
            if turn <= 0:
                raise ValueError("turn must be positive")
            data["turn"] = turn

        payload = await self.post_form(
            "game/loadturn",
            data=data,
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

    async def send_message(
        self,
        *,
        game_id: int,
        player_id: int,
        api_key: str,
        recipient_player_ids: list[int],
        body: str,
    ) -> dict[str, Any]:
        """Send one explicit in-game message without any transport retry.

        Planets.nu accepts a comma-separated list of recipient player slots on
        ``game/sendmessage``. We use a form POST so ordinary ``&``/``=`` text is
        encoded by the HTTP client rather than applying the old query-string
        substitution convention used by legacy clients.
        """

        payload = await self.post_form(
            "game/sendmessage",
            data={
                "gameid": game_id,
                "playerid": player_id,
                "apikey": api_key,
                "to": ",".join(str(item) for item in recipient_player_ids),
                "body": body,
            },
            headers={
                "Origin": "https://planets.nu",
                "Referer": "https://planets.nu/",
                "User-Agent": "Mozilla/5.0",
            },
            use_proxy=True,
            allow_proxy_fallback=False,
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu sendmessage response is not an object"
            )
        if payload.get("success") is False:
            raise PlanetsNuError(
                str(payload.get("error", "Planets.nu sendmessage failed"))
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

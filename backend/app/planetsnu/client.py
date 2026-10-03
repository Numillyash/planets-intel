from typing import Any

import httpx

from app.core.config import get_settings


class PlanetsNuError(RuntimeError):
    pass


class PlanetsNuAuthError(PlanetsNuError):
    pass


class PlanetsNuTransportError(PlanetsNuError):
    """All attempted read transport paths failed before an HTTP response."""


class PlanetsNuAmbiguousWriteError(PlanetsNuError):
    """The write request may have reached Planets.nu but no response was received."""


def _encode_nonpublic_text(value: str) -> str:
    """Apply the legacy Planets.nu non-public API text escaping convention.

    This is separate from ordinary form/url encoding. Historical client/API
    documentation specifies these substitutions for message text so literal
    ampersands and equals signs are not interpreted as protocol separators.
    """

    return value.replace("&", "|||").replace("=", ":::")


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
        ambiguous_write: bool = False,
    ) -> httpx.Response:
        """Perform one request path, optionally falling back direct after proxy transport failure.

        The fallback is deliberately limited to transport failures. HTTP status
        errors and API-level errors are handled by the caller and must not be
        retried through another path, because the server already answered.

        Write callers must set ``allow_proxy_fallback=False`` and
        ``ambiguous_write=True``. A transport error after a write request leaves
        delivery ambiguous; silently retrying the same write through another
        route could duplicate the user action.
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

        error_type = (
            PlanetsNuAmbiguousWriteError
            if ambiguous_write
            else PlanetsNuTransportError
        )
        raise error_type(
            "Planets.nu request failed: " + "; ".join(failures)
        )

    async def probe_private_transport(
        self,
        *,
        timeout_seconds: float = 12.0,
    ) -> dict[str, Any]:
        """Probe the configured private transport without parsing API payload.

        Planets.nu's /time endpoint returns JavaScript-like text rather than
        JSON. This probe is therefore intentionally transport/HTTP-only.

        When a proxy is configured, the probe uses that proxy exclusively:
        background private collection must know whether its intended bridge is
        alive instead of masking bridge failure behind a slow direct fallback.
        If no proxy is configured, it probes the direct route.
        """

        url = f"{self.base_url}/time"
        proxy = self.proxy_url
        route = "proxy" if proxy is not None else "direct"

        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
                proxy=proxy,
                trust_env=False,
            ) as client:
                response = await client.get(
                    url,
                    params={"version": 1},
                )
                response.raise_for_status()
        except httpx.RequestError as exc:
            raise PlanetsNuTransportError(
                f"Planets.nu {route} probe failed: {exc.__class__.__name__}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise PlanetsNuError(
                f"Planets.nu {route} probe returned HTTP "
                f"{exc.response.status_code}"
            ) from exc

        return {
            "ok": True,
            "route": route,
            "proxy_configured": proxy is not None,
            "status_code": response.status_code,
        }


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
        ambiguous_write: bool = False,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"

        response = await self._request(
            "POST",
            url,
            data=data,
            headers=headers,
            use_proxy=use_proxy,
            allow_proxy_fallback=allow_proxy_fallback,
            ambiguous_write=ambiguous_write,
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
        *,
        statuses: tuple[int, ...] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "username": username.strip(),
        }
        if statuses:
            params["status"] = ",".join(str(status) for status in statuses)

        payload = await self.get(
            "games/list",
            params=params,
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

        if statuses:
            allowed = set(statuses)
            # Planets.nu documents username as a dominant games/list filter;
            # other query fields can be ignored. Enforce the requested status
            # subset locally so Commander Intelligence cannot silently include
            # joining/open games when it asks for running/finished history.
            return [
                game
                for game in payload
                if (
                    not isinstance(game.get("status"), bool)
                    and isinstance(game.get("status"), int)
                    and game["status"] in allowed
                )
            ]

        return payload

    async def my_games(
        self,
        api_key: str,
    ) -> list[dict[str, Any]]:
        """Return the authenticated account's active game envelopes.

        Planets.nu documents /account/mygames as the current player's active
        game list. Unlike public /games/list?username=..., this authenticated
        source can expose private/custom games belonging to the linked account.

        Version 2 returns entries shaped as {"game": {...}, "player": {...}}.
        """

        payload = await self.post_form(
            "account/mygames?version=2",
            data={"apikey": api_key},
            headers={
                "Origin": "https://planets.nu",
                "Referer": "https://planets.nu/",
                "User-Agent": "Mozilla/5.0",
            },
            use_proxy=True,
        )

        if not isinstance(payload, dict):
            raise PlanetsNuError(
                "Planets.nu account/mygames response is not an object"
            )
        if payload.get("success") is False:
            raise PlanetsNuError(
                str(
                    payload.get(
                        "error",
                        "Planets.nu account/mygames failed",
                    )
                )
            )

        games = payload.get("games")
        if not isinstance(games, list):
            raise PlanetsNuError(
                "Planets.nu account/mygames response has no games list"
            )

        if not all(
            isinstance(item, dict)
            and isinstance(item.get("game"), dict)
            for item in games
        ):
            raise PlanetsNuError(
                "Planets.nu account/mygames contains invalid game records"
            )

        return games

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
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        """Send one root message or game-feed reply without transport retry.

        Verified against the official Planets.nu 1.24 client on 2026-08-25:
        - Public Board root: omit ``to`` and ``parentid``.
        - Private root: include ``to=slot[,slot…]``.
        - Reply: use the same ``/game/sendmessage`` endpoint and add
          ``parentid=<thread root activity id>``; private replies retain ``to``.
        """

        if parent_id is not None and (
            isinstance(parent_id, bool)
            or not isinstance(parent_id, int)
            or parent_id <= 0
        ):
            raise ValueError("parent_id must be a positive integer")

        data: dict[str, Any] = {
            "gameid": game_id,
            "playerid": player_id,
            "apikey": api_key,
            "body": _encode_nonpublic_text(body),
        }
        if recipient_player_ids:
            data["to"] = ",".join(str(item) for item in recipient_player_ids)
        if parent_id is not None:
            data["parentid"] = parent_id

        payload = await self.post_form(
            "game/sendmessage",
            data=data,
            headers={
                "Origin": "https://planets.nu",
                "Referer": "https://planets.nu/",
                "User-Agent": "Mozilla/5.0",
            },
            use_proxy=True,
            allow_proxy_fallback=False,
            ambiguous_write=True,
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

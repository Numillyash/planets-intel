import unittest
from unittest.mock import patch

import httpx

from app.planetsnu.client import (
    PlanetsNuAmbiguousWriteError,
    PlanetsNuClient,
    PlanetsNuError,
    _encode_nonpublic_text,
)


class _FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "https://api.planets.nu/game/loadturn")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._payload


class _FallbackAsyncClient:
    attempts = []

    def __init__(self, *, proxy=None, **kwargs):
        self.proxy = proxy
        self.__class__.attempts.append(proxy)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        if self.proxy is not None:
            raise httpx.ConnectError(
                "proxy unavailable",
                request=httpx.Request(method, url),
            )
        return _FakeResponse({"success": True, "rst": {}})


class _HttpErrorAsyncClient:
    attempts = []

    def __init__(self, *, proxy=None, **kwargs):
        self.proxy = proxy
        self.__class__.attempts.append(proxy)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        return _FakeResponse({"error": "forbidden"}, status_code=403)


class _WriteTransportFailureAsyncClient:
    attempts = []

    def __init__(self, *, proxy=None, **kwargs):
        self.proxy = proxy
        self.__class__.attempts.append(proxy)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        raise httpx.ReadError(
            "response lost after write",
            request=httpx.Request(method, url),
        )


class _CaptureWriteAsyncClient:
    attempts = []
    requests = []

    def __init__(self, *, proxy=None, **kwargs):
        self.proxy = proxy
        self.__class__.attempts.append(proxy)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        self.__class__.requests.append((method, url, kwargs))
        return _FakeResponse({"success": True, "html": "ok"})


class PlanetsNuClientTests(unittest.IsolatedAsyncioTestCase):
    def test_nonpublic_message_text_escape_is_explicit(self):
        self.assertEqual(
            _encode_nonpublic_text("status & plans = ready"),
            "status ||| plans ::: ready",
        )

    async def test_load_turn_falls_back_direct_after_proxy_transport_failure(self):
        _FallbackAsyncClient.attempts = []
        client = PlanetsNuClient()
        client.proxy_url = "http://proxy.invalid:8080"
        client.base_url = "https://api.planets.nu"

        with patch("app.planetsnu.client.httpx.AsyncClient", _FallbackAsyncClient):
            payload = await client.load_turn(123, "secret")

        self.assertEqual(payload, {"success": True, "rst": {}})
        self.assertEqual(
            _FallbackAsyncClient.attempts,
            ["http://proxy.invalid:8080", None],
        )

    async def test_http_error_does_not_trigger_direct_retry(self):
        _HttpErrorAsyncClient.attempts = []
        client = PlanetsNuClient()
        client.proxy_url = "http://proxy.invalid:8080"
        client.base_url = "https://api.planets.nu"

        with patch("app.planetsnu.client.httpx.AsyncClient", _HttpErrorAsyncClient):
            with self.assertRaisesRegex(PlanetsNuError, "HTTP 403"):
                await client.load_turn(123, "secret")

        self.assertEqual(
            _HttpErrorAsyncClient.attempts,
            ["http://proxy.invalid:8080"],
        )

    async def test_send_message_never_retries_ambiguous_transport_failure(self):
        _WriteTransportFailureAsyncClient.attempts = []
        client = PlanetsNuClient()
        client.proxy_url = "http://proxy.invalid:8080"
        client.base_url = "https://api.planets.nu"

        with patch(
            "app.planetsnu.client.httpx.AsyncClient",
            _WriteTransportFailureAsyncClient,
        ):
            with self.assertRaisesRegex(
                PlanetsNuAmbiguousWriteError,
                "Planets.nu request failed",
            ):
                await client.send_message(
                    game_id=123,
                    player_id=4,
                    api_key="secret",
                    recipient_player_ids=[2, 7],
                    body="status & plans = ready",
                )

        self.assertEqual(
            _WriteTransportFailureAsyncClient.attempts,
            ["http://proxy.invalid:8080"],
        )

    async def test_send_message_posts_encoded_nonpublic_body_once(self):
        _CaptureWriteAsyncClient.attempts = []
        _CaptureWriteAsyncClient.requests = []
        client = PlanetsNuClient()
        client.proxy_url = "http://proxy.invalid:8080"
        client.base_url = "https://api.planets.nu"

        with patch("app.planetsnu.client.httpx.AsyncClient", _CaptureWriteAsyncClient):
            result = await client.send_message(
                game_id=123,
                player_id=4,
                api_key="secret",
                recipient_player_ids=[2, 7],
                body="status & plans = ready",
            )

        self.assertEqual(result["success"], True)
        self.assertEqual(_CaptureWriteAsyncClient.attempts, ["http://proxy.invalid:8080"])
        self.assertEqual(len(_CaptureWriteAsyncClient.requests), 1)
        method, url, kwargs = _CaptureWriteAsyncClient.requests[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/game/sendmessage"))
        self.assertEqual(
            kwargs["data"],
            {
                "gameid": 123,
                "playerid": 4,
                "apikey": "secret",
                "to": "2,7",
                "body": "status ||| plans ::: ready",
            },
        )


if __name__ == "__main__":
    unittest.main()

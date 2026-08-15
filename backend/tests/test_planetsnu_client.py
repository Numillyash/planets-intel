import unittest
from unittest.mock import patch

import httpx

from app.planetsnu.client import PlanetsNuClient, PlanetsNuError


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


class PlanetsNuClientTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()

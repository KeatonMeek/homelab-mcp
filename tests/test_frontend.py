import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx2
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.jwt_issuer import JWTIssuer
from key_value.aio.stores.memory import MemoryStore
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from app.config import Settings
from app.server import make_app, make_provider, make_storage, owner_check, OwnerMiddleware
from tests.test_config import fixture_environment


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = Settings.from_environment(fixture_environment(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def token(self, owner="12345", scopes=None):
        return AccessToken(token="unit-test", client_id="unit-test", scopes=["read:user"] if scopes is None else scopes,
                           claims={"sub": owner})

    def test_owner_fail_closed(self):
        check = owner_check("12345")
        self.assertTrue(check(SimpleNamespace(token=self.token())))
        for token in (None, self.token("54321"), self.token(12345), self.token(None), self.token(scopes=[])):
            self.assertFalse(check(SimpleNamespace(token=token)))
        for owner in (None, "", "not-numeric", "０", "0"):
            self.assertFalse(owner_check(owner)(SimpleNamespace(token=self.token())))

    async def request_session(self, enabled=False):
        settings = Settings.from_environment(fixture_environment(self.root) | {"HOMELAB_ENABLE_EXECUTION": str(enabled).lower()})
        provider = make_provider(settings, storage=MemoryStore())
        broker = SimpleNamespace(call=AsyncMock(return_value={"output": "unit-test"}))
        app = make_app(settings, provider=provider, broker=broker)
        return provider, broker, app

    async def test_default_tools_and_http_authentication(self):
        provider, broker, app = await self.request_session()
        async with app.app.router.lifespan_context(app.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=self.settings.base_url,
                headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}) as client:
                listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
                self.assertEqual((await client.post("/mcp", json=listing)).status_code, 401)
                self.assertEqual((await client.post("/mcp", json=listing, headers={"Authorization": "Bearer invalid"})).status_code, 401)
                with patch.object(provider, "load_access_token", AsyncMock(return_value=self.token())):
                    response = await client.post("/mcp", json=listing, headers={"Authorization": "Bearer unit-test"})
                    self.assertEqual(response.status_code, 200, response.text)
                    tools = response.json()["result"]["tools"]
                    self.assertEqual({tool["name"] for tool in tools}, {"probe", "health"})
                    for tool in tools:
                        self.assertTrue(tool["annotations"]["readOnlyHint"])
                with patch.object(provider, "load_access_token", AsyncMock(return_value=self.token("54321"))):
                    response = await client.post("/mcp", json=listing, headers={"Authorization": "Bearer unit-test"})
                    self.assertEqual(response.json()["result"]["tools"], [])
                metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
                self.assertIn("S256", metadata["code_challenge_methods_supported"])
                resource = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
                self.assertEqual(resource["resource"], self.settings.base_url + "/mcp")
                self.assertIn("/consent", [route.path for route in app.app.routes])
        broker.call.assert_not_awaited()

    async def test_every_tool_checks_owner_and_execution_requires_opt_in(self):
        provider, broker, app = await self.request_session(enabled=True)
        calls = {
            "probe": {"challenge": "unit-test"}, "health": {}, "command_run": {"command": "true"},
            "command_start": {"command": "true"}, "job_status": {"job_id": "a" * 32},
            "job_output": {"job_id": "a" * 32}, "job_cancel": {"job_id": "a" * 32},
            "file_read": {"path": "/fixture"}, "file_write": {"path": "/fixture", "text": "fixture"},
            "file_move": {"path": "/fixture", "destination": "/other"},
        }
        async with app.app.router.lifespan_context(app.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=self.settings.base_url,
                headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25", "Authorization": "Bearer unit-test"}) as client:
                for owner, scopes, permitted in (("54321", ["read:user"], False), ("12345", [], False), ("12345", ["read:user"], True)):
                    with patch.object(provider, "load_access_token", AsyncMock(return_value=self.token(owner, scopes))):
                        for name, arguments in calls.items():
                            with self.subTest(owner=owner, scopes=scopes, tool=name):
                                broker.call.reset_mock()
                                result = (await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})).json()
                                if permitted:
                                    self.assertFalse(result.get("result", {}).get("isError"), result)
                                    if name not in {"probe", "health"}:
                                        broker.call.assert_awaited_once()
                                else:
                                    self.assertTrue("error" in result or result.get("result", {}).get("isError"), result)
                                    broker.call.assert_not_awaited()
                        if permitted:
                            listing = (await client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})).json()["result"]["tools"]
                            tools = {tool["name"]: tool for tool in listing}
                            self.assertEqual(set(tools), set(calls))
                            self.assertTrue(tools["command_run"]["annotations"]["destructiveHint"])
                            self.assertFalse(tools["file_write"]["annotations"]["readOnlyHint"])

    async def test_http_registration_requires_exact_callback(self):
        provider, broker, app = await self.request_session()
        callback = self.settings.redirect_uris[0]
        async with app.app.router.lifespan_context(app.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=self.settings.base_url) as client:
                for uri, status in ((callback, 201), (callback + "?unexpected=1", 400), ("https://other.example.test/callback", 400)):
                    response = await client.post("/register", json={"client_name": "Unit test", "redirect_uris": [uri],
                        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                        "token_endpoint_auth_method": "none"})
                    self.assertEqual(response.status_code, status, response.text)
        broker.call.assert_not_awaited()

    async def test_exact_redirects_and_invalid_tokens(self):
        provider = make_provider(self.settings, storage=MemoryStore())
        make_app(self.settings, provider=provider)
        self.assertIsNone(await provider.load_access_token("not-a-token"))
        foreign = JWTIssuer(issuer=self.settings.base_url, audience="https://wrong.example.test/mcp", signing_key=self.settings.signing_key.encode())
        token = foreign.issue_access_token(client_id="unit-test", scopes=["read:user"], jti="fixture")
        self.assertIsNone(await provider.load_access_token(token))
        callback = self.settings.redirect_uris[0]
        self.assertTrue(provider._validate_client_redirect_uri(callback))
        for uri in (callback + "?different=1", callback + "#fragment", callback + "/extra", "https://evil.example.test/callback"):
            self.assertFalse(provider._validate_client_redirect_uri(uri))
            with self.assertRaises(Exception):
                await provider.register_client(OAuthClientInformationFull(client_id="unit-test", redirect_uris=[AnyUrl(uri)]))
            with self.assertRaises(Exception):
                await provider.authorize(None, SimpleNamespace(redirect_uri=uri))
        await provider.register_client(OAuthClientInformationFull(client_id="unit-test", redirect_uris=[AnyUrl(callback)]))

    async def test_owner_gate_has_no_stdio_bypass(self):
        middleware = OwnerMiddleware("12345")
        call_next = AsyncMock()
        with patch("app.server.get_access_token", return_value=None):
            self.assertEqual(await middleware.on_list_tools(None, call_next), [])
            with self.assertRaises(Exception):
                await middleware.on_call_tool(None, call_next)
        call_next.assert_not_awaited()

    async def test_persistent_values_are_encrypted_and_reload(self):
        storage = make_storage(self.settings)
        marker = "plaintext-token-unit-test-marker"
        await storage.put(key="test-record", value={"token": marker})
        files = [path for path in self.root.rglob("*") if path.is_file()]
        self.assertTrue(files)
        for path in files:
            self.assertNotIn(marker.encode(), path.read_bytes())
        self.assertEqual((await make_storage(self.settings).get(key="test-record"))["token"], marker)

    async def test_large_escaped_utf8_file_request_reaches_tool(self):
        provider, broker, app = await self.request_session(enabled=True)
        # JSON's six-byte escapes stress the HTTP envelope beyond the old 16 KiB cap.
        text = "\u0001" * 131072
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "file_write", "arguments": {"path": "/fixture", "text": text}}}
        body = json.dumps(payload).encode()
        self.assertGreater(len(body), 700000)
        async with app.app.router.lifespan_context(app.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=self.settings.base_url,
                headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25", "Authorization": "Bearer unit-test", "Content-Type": "application/json"}) as client:
                with patch.object(provider, "load_access_token", AsyncMock(return_value=self.token())):
                    response = await client.post("/mcp", content=body)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertFalse(response.json().get("result", {}).get("isError"), response.text)
                    broker.call.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx2
import jwt
from key_value.aio.stores.memory import MemoryStore
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from app.cimd import TrustedCIMDFetcher
from app.config import Settings
from app.server import make_app, make_provider
from fastmcp.server.auth.cimd import CIMDValidationError
from fastmcp.server.auth.ssrf import SSRFFetchResponse, SSRFFetchError, ValidatedURL
from tests.test_config import fixture_environment

METADATA = "https://chatgpt.com/oauth/client.json"
JWKS = "https://chatgpt.com/oauth/jwks.json"
CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"


class TrustedCIMDTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        env = fixture_environment(Path(self.temp.name)) | {
            "HOMELAB_CLIENT_REDIRECT_URIS": json.dumps([CALLBACK]),
            "HOMELAB_TRUSTED_CLIENT_METADATA_URIS": json.dumps([METADATA]),
            "HOMELAB_TRUSTED_JWKS_URIS": json.dumps([JWKS]),
        }
        self.settings = Settings.from_environment(env)
        # Ephemeral fixture material only. No private key is persisted or sent.
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        public.update({"kid": "unit-test", "alg": "RS256", "use": "sig"})
        self.jwks = {"keys": [public]}
        self.metadata = {
            "client_id": METADATA, "client_name": "ChatGPT fixture",
            "redirect_uris": [CALLBACK], "token_endpoint_auth_method": "private_key_jwt",
            "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
            "jwks_uri": JWKS,
        }

    def tearDown(self):
        self.temp.cleanup()

    async def fixture_fetch(self, uri, **kwargs):
        self.assertIn(uri, {METADATA, JWKS})
        self.assertTrue(kwargs["require_path"])
        self.assertEqual(kwargs["allowed_status_codes"], {200})
        self.assertLessEqual(kwargs["overall_timeout"], 30)
        data = self.metadata if uri == METADATA else self.jwks
        return SSRFFetchResponse(content=json.dumps(data).encode(), status_code=200, headers={"cache-control": "max-age=300"})

    def assertion(self, *, token_endpoint, jti="unit-test-assertion", key=None, **overrides):
        now = int(time.time())
        claims = {"iss": METADATA, "sub": METADATA, "aud": token_endpoint,
                  "iat": now, "exp": now + 120, "jti": jti} | overrides
        return jwt.encode(claims, key or self.key, algorithm="RS256", headers={"kid": "unit-test"})

    async def test_untrusted_ids_never_fetch_and_default_cimd_is_disabled(self):
        provider = make_provider(self.settings, storage=MemoryStore())
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock()) as fetch:
            for uri in ("https://evil.example.test/client.json", METADATA + "?tenant=unapproved", "https://127.0.0.1/private", "http://chatgpt.com/oauth/client.json"):
                self.assertIsNone(await provider.get_client(uri))
            self.assertIsNone(await provider._cimd_manager.get_client("https://evil.example.test/client.json"))
            fetch.assert_not_awaited()
        basic = Settings.from_environment(fixture_environment(Path(self.temp.name)))
        provider = make_provider(basic, storage=MemoryStore())
        self.assertIsNone(provider._cimd_manager)
        self.assertIsNone(await provider.get_client(METADATA))
        with self.assertRaises(Exception):
            await provider.register_client(OAuthClientInformationFull(client_id=METADATA, redirect_uris=[AnyUrl(CALLBACK)]))

    async def test_trusted_metadata_and_jwks_are_bounded_exact_and_inlined(self):
        provider = make_provider(self.settings, storage=MemoryStore())
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=self.fixture_fetch)) as fetch:
            client = await provider.get_client(METADATA)
            self.assertIsNotNone(client)
            self.assertEqual(client.token_endpoint_auth_method, "private_key_jwt")
            self.assertIsNone(client.cimd_document.jwks_uri)
            self.assertEqual(client.cimd_document.jwks, self.jwks)
            self.assertEqual([call.args[0] for call in fetch.await_args_list], [METADATA, JWKS])
            # A second lookup uses the bounded cache; verification never follows
            # a metadata-supplied URL independently.
            self.assertIsNotNone(await provider.get_client(METADATA))
            self.assertEqual(fetch.await_count, 2)
            make_app(self.settings, provider=provider)
            assertion = self.assertion(token_endpoint=provider.token_endpoint_url)
            self.assertTrue(await provider._cimd_manager.validate_private_key_jwt(assertion, client, provider.token_endpoint_url))
            with self.assertRaises(ValueError):
                await provider._cimd_manager.validate_private_key_jwt(assertion, client, provider.token_endpoint_url)
            self.assertEqual(fetch.await_count, 2)

    async def test_bad_metadata_or_unapproved_jwks_cannot_expand_fetches(self):
        for change in (
            {"client_id": METADATA + "/"}, {"redirect_uris": [CALLBACK + "?extra=1"]},
            {"redirect_uris": ["https://chatgpt.com/*"]}, {"jwks_uri": "https://evil.example.test/keys.json"},
            {"jwks_uri": "https://127.0.0.1/keys.json"}, {"jwks_uri": JWKS + "?unapproved=1"},
        ):
            provider = make_provider(self.settings, storage=MemoryStore())
            original = self.metadata
            self.metadata = original | change
            with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=self.fixture_fetch)) as fetch:
                self.assertIsNone(await provider.get_client(METADATA), change)
                self.assertEqual([call.args[0] for call in fetch.await_args_list], [METADATA])
            self.metadata = original

    async def test_bad_signatures_claims_and_replay_rejected(self):
        provider = make_provider(self.settings, storage=MemoryStore())
        make_app(self.settings, provider=provider)
        endpoint = provider.token_endpoint_url
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=self.fixture_fetch)):
            client = await provider.get_client(METADATA)
            for i, changes in enumerate(({"aud": "https://wrong.example.test/token"}, {"sub": "wrong-client"},
                                         {"iss": "wrong-client"}, {"exp": int(time.time()) - 90},
                                         {"exp": int(time.time()) + 1200}, {"jti": ""})):
                assertion = self.assertion(token_endpoint=endpoint, **({"jti": f"invalid-{i}"} | changes))
                with self.assertRaises(ValueError):
                    await provider._cimd_manager.validate_private_key_jwt(assertion, client, endpoint)
            other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with self.assertRaises(ValueError):
                await provider._cimd_manager.validate_private_key_jwt(self.assertion(token_endpoint=endpoint, key=other_key), client, endpoint)

    async def test_private_key_jwt_token_route_retains_client_authentication(self):
        provider = make_provider(self.settings, storage=MemoryStore())
        app = make_app(self.settings, provider=provider)
        assertion = self.assertion(token_endpoint=provider.token_endpoint_url)
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=self.fixture_fetch)) as fetch:
            async with app.app.router.lifespan_context(app.app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=self.settings.base_url) as client:
                    metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
                    self.assertIn("private_key_jwt", metadata["token_endpoint_auth_methods_supported"])
                    self.assertTrue(metadata["client_id_metadata_document_supported"])
                    data = {"grant_type": "authorization_code", "code": "nonexistent-fixture-code", "client_id": METADATA,
                            "redirect_uri": CALLBACK, "code_verifier": "x" * 43,
                            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                            "client_assertion": assertion}
                    result = await client.post("/token", data=data)
                    # invalid_grant proves the signed client authentication
                    # succeeded and reached authorization-code validation.
                    self.assertEqual(result.status_code, 401, result.text)
                    self.assertEqual(result.json()["error"], "invalid_grant", result.text)
                    replay = await client.post("/token", data=data)
                    self.assertEqual(replay.json()["error"], "invalid_client", replay.text)
                    missing = await client.post("/token", data={key: value for key, value in data.items() if key != "client_assertion"})
                    self.assertEqual(missing.json()["error"], "invalid_client", missing.text)
            self.assertEqual([call.args[0] for call in fetch.await_args_list], [METADATA, JWKS])

    async def test_redirect_oversize_failure_and_cache_expiry_fail_closed(self):
        fetcher = TrustedCIMDFetcher((METADATA,), (JWKS,), (CALLBACK,))
        for response in (SSRFFetchResponse(b"{}", 302, {"location": "https://evil.example.test/metadata"}),
                         SSRFFetchResponse(b"x" * 5121, 200, {})):
            with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(return_value=response)) as fetch:
                with self.assertRaises(CIMDValidationError):
                    await fetcher.fetch(METADATA)
                self.assertEqual(fetch.await_count, 1)
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=self.fixture_fetch)):
            await fetcher.fetch(METADATA)
        fetcher._trusted_cache[METADATA] = (0, fetcher._trusted_cache[METADATA][1])
        with patch("app.cimd.ssrf_safe_fetch_response", AsyncMock(side_effect=SSRFFetchError("fixture failure"))):
            with self.assertRaises(CIMDValidationError):
                await fetcher.fetch(METADATA)
            self.assertNotIn(METADATA, fetcher._trusted_cache)

    async def test_upstream_ssrf_blocks_private_dns_before_any_http(self):
        fetcher = TrustedCIMDFetcher((METADATA,), (JWKS,), (CALLBACK,))
        with patch("fastmcp.server.auth.ssrf.resolve_hostname", AsyncMock(return_value=["127.0.0.1"])), \
             patch("fastmcp.server.auth.ssrf.httpx2.AsyncClient") as client:
            with self.assertRaises(CIMDValidationError):
                await fetcher.fetch(METADATA)
            client.assert_not_called()

    async def test_upstream_ssrf_never_follows_redirect(self):
        fetcher = TrustedCIMDFetcher((METADATA,), (JWKS,), (CALLBACK,))
        pinned = ValidatedURL(original_url=METADATA, hostname="chatgpt.com", port=443,
                              path="/oauth/client.json", resolved_ips=["93.184.216.34"])
        class Response:
            status_code = 302
            headers = {"location": "https://evil.example.test/metadata"}
        class Stream:
            async def __aenter__(self): return Response()
            async def __aexit__(self, *args): return None
        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return None
            def stream(self, *args, **kwargs): return Stream()
        with patch("fastmcp.server.auth.ssrf.validate_url", AsyncMock(return_value=pinned)), \
             patch("fastmcp.server.auth.ssrf.httpx2.AsyncClient", return_value=Client()) as client:
            with self.assertRaises(CIMDValidationError):
                await fetcher.fetch(METADATA)
            self.assertFalse(client.call_args.kwargs["follow_redirects"])


if __name__ == "__main__":
    unittest.main()

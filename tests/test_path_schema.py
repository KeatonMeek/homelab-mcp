"""Absolute path schemas must also work with clients that full-match patterns."""
import re
import unittest
from unittest.mock import AsyncMock, patch

import httpx2
from pydantic import TypeAdapter, ValidationError

from app.management_tools import AbsolutePath
from tests import test_frontend


class PathSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_exported_paths_accept_absolute_values_under_fullmatch(self):
        fixture = test_frontend.FrontendTests()
        fixture.setUp()
        try:
            provider, broker, app = await fixture.request_session(enabled=True)
            async with app.app.router.lifespan_context(app.app):
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app), base_url=fixture.settings.base_url,
                    headers={"Accept": "application/json, text/event-stream",
                             "MCP-Protocol-Version": "2025-11-25", "Authorization": "Bearer unit-test"},
                ) as client:
                    with patch.object(provider, "load_access_token", AsyncMock(return_value=fixture.token())):
                        result = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
                        tools = {tool["name"]: tool for tool in result.json()["result"]["tools"]}
                        for tool, fields in {
                            "command_run": ["cwd"], "command_start": ["cwd"],
                            "file_read": ["path"], "file_write": ["path"],
                            "file_move": ["path", "destination"],
                        }.items():
                            for field in fields:
                                schema = tools[tool]["inputSchema"]["properties"][field]
                                self.assertEqual(schema["maxLength"], 4096)
                                for value in ("/", "/tmp", "/tmp/file with spaces", "/tmp/line\nbreak", "/tmp/end\n"):
                                    with self.subTest(tool=tool, field=field, value=value):
                                        self.assertIsNotNone(re.fullmatch(schema["pattern"], value))
                                for value in ("", "tmp/file", "\n/tmp", "C:\\tmp"):
                                    self.assertIsNone(re.fullmatch(schema["pattern"], value))
                        for value in ("/tmp/fixture", "/tmp/line\nbreak"):
                            broker.call.reset_mock()
                            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 2,
                                "method": "tools/call", "params": {"name": "file_read", "arguments": {"path": value}}})
                            self.assertFalse(response.json().get("result", {}).get("isError"), response.text)
                            broker.call.assert_awaited_once()
                            self.assertEqual(broker.call.call_args.kwargs["path"], value)
        finally:
            fixture.tearDown()

    def test_absolute_path_runtime_validation_retains_bounds(self):
        adapter = TypeAdapter(AbsolutePath)
        for value in ("/", "/tmp", "/tmp/line\nbreak", "/" + "a" * 4095):
            self.assertEqual(adapter.validate_python(value), value)
        for value in ("", "relative", "\n/tmp", "/" + "a" * 4096):
            with self.assertRaises(ValidationError):
                adapter.validate_python(value)

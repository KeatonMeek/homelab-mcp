import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.management_tools import BrokerClient, MAX_FRAME
from app.server import LoopbackProxyGuard, MAX_HTTP_BODY


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, *, peer="127.0.0.1", headers=None, chunks=None):
        state = {"called": False, "headers": None, "body": bytearray(), "sent": []}
        async def inner(scope, receive, send):
            state["called"] = True
            state["headers"] = scope["headers"]
            state["scheme"] = scope["scheme"]
            while True:
                message = await receive()
                state["body"].extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})
        guard = LoopbackProxyGuard(inner, base_url="https://mcp.example.test")
        scope = {"type": "http", "method": "POST", "scheme": "http", "path": "/mcp", "query_string": b"",
                 "client": (peer, 1234) if peer is not None else None,
                 "headers": [(b"host", b"mcp.example.test")] if headers is None else headers}
        queue = list(chunks or [{"type": "http.request", "body": b"{}", "more_body": False}])
        async def receive():
            return queue.pop(0) if queue else {"type": "http.disconnect"}
        async def send(message):
            state["sent"].append(message)
        await guard(scope, receive, send)
        state["status"] = next((item["status"] for item in state["sent"] if item["type"] == "http.response.start"), None)
        return state

    async def test_loopback_host_origin_and_forwarding(self):
        self.assertEqual((await self.invoke())["status"], 200)
        self.assertEqual((await self.invoke(peer="::1"))["status"], 200)
        for peer in ("192.0.2.1", None, "invalid"):
            result = await self.invoke(peer=peer)
            self.assertEqual(result["status"], 403)
            self.assertFalse(result["called"])
        for headers in ([], [(b"host", b"evil.example.test")], [(b"host", b"mcp.example.test"), (b"host", b"mcp.example.test")]):
            self.assertEqual((await self.invoke(headers=headers))["status"], 421)
        self.assertEqual((await self.invoke(headers=[(b"host", b"mcp.example.test"), (b"origin", b"https://evil.example.test")]))["status"], 403)
        headers = [(b"host", b"mcp.example.test"), (b"origin", b"https://mcp.example.test"),
                   (b"forwarded", b"for=evil;host=evil.example.test"), (b"x-forwarded-host", b"evil.example.test"),
                   (b"x-forwarded-for", b"203.0.113.1"), (b"cf-connecting-ip", b"203.0.113.1"), (b"cf-visitor", b'{"scheme":"http"}'), (b"x-real-ip", b"203.0.113.1")]
        result = await self.invoke(headers=headers)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["headers"], headers[:2])
        self.assertEqual(result["scheme"], "https")

    async def test_body_limit_content_length_chunked_and_misreported(self):
        host = [(b"host", b"mcp.example.test")]
        self.assertEqual((await self.invoke(headers=host + [(b"content-length", str(MAX_HTTP_BODY + 1).encode())]))["status"], 413)
        for value in (b"-1", b"not-a-number", b"1" * 100):
            self.assertEqual((await self.invoke(headers=host + [(b"content-length", value)]))["status"], 400)
        self.assertEqual((await self.invoke(headers=host + [(b"content-length", b"3")]))["status"], 400)
        self.assertEqual((await self.invoke(headers=host + [(b"content-length", b"2"), (b"content-length", b"2")]))["status"], 400)
        result = await self.invoke(chunks=[{"type": "http.request", "body": b"a" * (MAX_HTTP_BODY // 2), "more_body": True},
                                         {"type": "http.request", "body": b"a" * (MAX_HTTP_BODY // 2 + 1), "more_body": False}])
        self.assertEqual(result["status"], 413)
        self.assertFalse(result["called"])
        exact = await self.invoke(chunks=[{"type": "http.request", "body": b"a" * MAX_HTTP_BODY, "more_body": False}])
        self.assertEqual(exact["status"], 200)
        self.assertEqual(len(exact["body"]), MAX_HTTP_BODY)

    async def test_broker_client_mocked_protocol_and_response_validation(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"output":"fixture"}\n')
        reader.feed_eof()
        writer = MagicMock()
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        with patch("app.management_tools.asyncio.open_unix_connection", AsyncMock(return_value=(reader, writer))) as connect:
            broker = BrokerClient("/fixture/custom.sock")
            self.assertEqual(await broker.call("command_run", command="true", timeout=1), {"output": "fixture"})
            connect.assert_awaited_once_with("/fixture/custom.sock", limit=MAX_FRAME + 1)
            self.assertEqual(json.loads(writer.write.call_args.args[0]), {"method": "command_run", "params": {"command": "true", "timeout": 1}})
            writer.close.assert_called_once()
        for payload in (b'[]\n', b'{"x":1}', b'not-json\n', b'a' * (MAX_FRAME + 1) + b'\n'):
            reader = asyncio.StreamReader(limit=MAX_FRAME + 1)
            reader.feed_data(payload)
            reader.feed_eof()
            with patch("app.management_tools.asyncio.open_unix_connection", AsyncMock(return_value=(reader, writer))):
                self.assertIn("error", await broker.call("job_status", job_id="a" * 32))
        self.assertEqual((await broker.call("file_write", path="/fixture", text="a" * MAX_FRAME))["error"], "broker_request_too_large")

    async def test_broker_client_real_unix_socket_when_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.sock"
            seen = []
            async def client(reader, writer):
                try:
                    line = await reader.readline()
                    seen.append(json.loads(line))
                    writer.write(b'{"output":"fixture"}\n')
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()
            try:
                listener = await asyncio.start_unix_server(client, str(path), limit=MAX_FRAME + 1)
            except PermissionError:
                self.skipTest("This execution environment prohibits Unix socket creation")
            async with listener:
                broker = BrokerClient(path)
                self.assertEqual(await broker.call("command_run", command="true", timeout=1), {"output": "fixture"})
                self.assertEqual(seen, [{"method": "command_run", "params": {"command": "true", "timeout": 1}}])
                self.assertEqual((await broker.call("file_write", path="/fixture", text="a" * MAX_FRAME))["error"], "broker_request_too_large")
            self.assertIn("error", await BrokerClient(Path(directory) / "missing.sock").call("job_status", job_id="a" * 32))


if __name__ == "__main__":
    unittest.main()

import datetime
import json
from pathlib import Path
import tempfile
import unittest

from app.health_tools import MAX_BYTES, read_health


class HealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_valid_stale_malformed_and_symlink_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            self.assertFalse((await read_health(path))["available"])
            data = {"schema_version": 1, "collected_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=240)).isoformat(),
                    "network": {"listeners": []}}
            path.write_text(json.dumps(data))
            result = await read_health(path, "network")
            self.assertTrue(result["available"])
            self.assertTrue(result["stale"])
            self.assertEqual(result["network"], {"listeners": []})
            self.assertTrue((await read_health(path))["available"])
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            self.assertFalse((await read_health(link))["available"])
            for invalid in ([], data | {"schema_version": 2}, data | {"collected_at": "2026-01-01T00:00:00"},
                            data | {"docker": []}, data | {"docker": {"containers": [None]}},
                            data | {"collected_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()}):
                path.write_text(json.dumps(invalid))
                self.assertFalse((await read_health(path))["available"])
            path.write_bytes(b"x" * (MAX_BYTES + 1))
            self.assertFalse((await read_health(path))["available"])


if __name__ == "__main__":
    unittest.main()

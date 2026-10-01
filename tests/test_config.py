import json
from pathlib import Path
import tempfile
import unittest

from cryptography.fernet import Fernet

from app.config import Settings, load_private_file, parse_redirect_uris, validate_https_url


def fixture_environment(root: Path):
    return {
        "HOMELAB_BASE_URL": "https://mcp.example.test",
        "HOMELAB_GITHUB_OWNER_ID": "12345",
        "HOMELAB_CLIENT_REDIRECT_URIS": json.dumps(["https://client.example.test/oauth/callback"]),
        "HOMELAB_GITHUB_CLIENT_ID": "unit-test-client",
        "HOMELAB_GITHUB_CLIENT_SECRET": "unit-test-secret-never-used",
        "HOMELAB_JWT_SIGNING_KEY": "unit-test-signing-material-32-bytes-only",
        "HOMELAB_STORAGE_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "HOMELAB_STATE_DIR": str(root),
        "HOMELAB_BROKER_SOCKET": str(root / "broker.sock"),
    }


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = fixture_environment(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_config_defaults_and_secret_repr(self):
        settings = Settings.from_environment(self.env)
        self.assertFalse(settings.enable_execution)
        self.assertEqual(settings.port, 8080)
        self.assertEqual(settings.health_snapshot, self.root / "health.json")
        for key in ("HOMELAB_GITHUB_CLIENT_SECRET", "HOMELAB_JWT_SIGNING_KEY", "HOMELAB_STORAGE_ENCRYPTION_KEY"):
            self.assertNotIn(self.env[key], repr(settings))
        self.assertTrue(Settings.from_environment(self.env | {"HOMELAB_ENABLE_EXECUTION": "true"}).enable_execution)

    def test_missing_and_invalid_values_fail_closed(self):
        with self.assertRaises(ValueError):
            Settings.from_environment({})
        cases = {
            "HOMELAB_GITHUB_OWNER_ID": ["username", "", "0", "123４", "-1", " 12345"],
            "HOMELAB_ENABLE_EXECUTION": ["1", "TRUE", "yes", ""],
            "HOMELAB_PORT": ["0", "65536", "port", "-1"],
            "HOMELAB_JWT_SIGNING_KEY": ["short"],
            "HOMELAB_STORAGE_ENCRYPTION_KEY": ["not-a-key", "é"],
            "HOMELAB_BROKER_SOCKET": ["relative.sock"],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    Settings.from_environment(self.env | {key: value})

    def test_exact_https_origin_and_generic_callbacks(self):
        self.assertEqual(validate_https_url("https://mcp.example.test:8443", origin_only=True), "https://mcp.example.test:8443")
        for bad in ("http://mcp.example.test", "https://mcp.example.test/", "https://mcp.example.test/path",
                    "https://mcp.example.test?x=1", "https://user@mcp.example.test", "https://*.example.test",
                    "https://mcp.example.test#", "https://mcp.example.test:443", "https://mcp.example.test\n"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_https_url(bad, origin_only=True)
        uris = ["https://alpha.example.test/auth", "https://beta.example.test/callback?tenant=fixture"]
        self.assertEqual(parse_redirect_uris(json.dumps(uris)), tuple(uris))
        for value in ("[]", '"https://client.example.test/auth"', '[1]', '["https://client.example.test/auth*"]',
                      '["https://client.example.test/auth#fragment"]', '["http://localhost/auth"]',
                      '["https://client.example.test/auth/../bad"]', '["https://client.example.test"]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_redirect_uris(value)

    def test_private_config_permissions_symlink_and_overrides(self):
        path = self.root / "private.json"
        path.write_text(json.dumps(self.env))
        path.chmod(0o600)
        self.assertEqual(Settings.from_environment({"HOMELAB_CONFIG_FILE": str(path)}).owner_id, "12345")
        self.assertEqual(Settings.from_environment({"HOMELAB_CONFIG_FILE": str(path), "HOMELAB_GITHUB_OWNER_ID": "98765"}).owner_id, "98765")
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            load_private_file(str(path))
        path.chmod(0o600)
        link = self.root / "link.json"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            load_private_file(str(link))
        for bad in ('{"UNRECOGNIZED": "x"}', '{"HOMELAB_PORT": 8080}', '{"HOMELAB_PORT":"1","HOMELAB_PORT":"2"}'):
            path.write_text(bad)
            with self.assertRaises(ValueError):
                load_private_file(str(path))
        path.write_bytes(b"x" * 65537)
        with self.assertRaises(ValueError):
            load_private_file(str(path))

    def test_private_path_ancestors_cannot_be_symlinked_or_world_writable(self):
        parent = self.root / "private-parent"
        parent.mkdir(mode=0o700)
        private = parent / "settings.json"
        private.write_text(json.dumps(self.env))
        private.chmod(0o600)
        link = self.root / "parent-link"
        link.symlink_to(parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            load_private_file(str(link / "settings.json"))
        parent.chmod(0o777)
        with self.assertRaises(ValueError):
            load_private_file(str(private))

    def test_state_directory_must_be_private_existing_and_not_symlink(self):
        self.root.chmod(0o750)
        with self.assertRaises(ValueError):
            Settings.from_environment(self.env)
        self.root.chmod(0o700)
        link = self.root / "link"
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            Settings.from_environment(self.env | {"HOMELAB_STATE_DIR": str(link)})
        with self.assertRaises(ValueError):
            Settings.from_environment(self.env | {"HOMELAB_STATE_DIR": str(self.root / "missing")})


if __name__ == "__main__":
    unittest.main()

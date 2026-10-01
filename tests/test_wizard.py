import contextlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts.create_config import main


class WizardTests(unittest.TestCase):
    def make(self, client):
        temp = tempfile.TemporaryDirectory(prefix='homelab-wizard-')
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)/'private'
        output = io.StringIO()
        with patch('sys.argv', ['create_config.py', '--directory', str(directory), '--client', client]), patch('builtins.input', side_effect=['https://mcp.example.com', '12345678', 'fixture-client', 'https://client.example.com/callback']), patch('getpass.getpass', return_value='synthetic-fixture-value'), contextlib.redirect_stdout(output):
            main()
        path = directory/'settings.json'
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotIn('synthetic-fixture-value', output.getvalue())
        return json.loads(path.read_text())

    def test_dcr_default_has_no_remote_metadata_trust(self):
        settings = self.make('dcr')
        self.assertEqual(json.loads(settings['HOMELAB_TRUSTED_CLIENT_METADATA_URIS']), [])
        self.assertEqual(json.loads(settings['HOMELAB_TRUSTED_JWKS_URIS']), [])
        self.assertEqual(settings['HOMELAB_ENABLE_EXECUTION'], 'false')

    def test_chatgpt_trust_is_exact_and_explicit(self):
        settings = self.make('chatgpt')
        self.assertEqual(json.loads(settings['HOMELAB_TRUSTED_CLIENT_METADATA_URIS']), ['https://chatgpt.com/oauth/client.json'])
        self.assertEqual(json.loads(settings['HOMELAB_TRUSTED_JWKS_URIS']), ['https://chatgpt.com/oauth/jwks.json'])
        self.assertEqual(json.loads(settings['HOMELAB_CLIENT_REDIRECT_URIS']), ['https://client.example.com/callback'])

import asyncio
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from app.execution_broker import Broker, environment_options, private_directory, redact


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='homelab-unit-')
        self.root = Path(self.temp.name)
        self.broker = Broker(audit=self.root/'audit.jsonl', enabled=True, python=sys.executable)

    async def asyncTearDown(self):
        await self.broker.close()
        self.temp.cleanup()

    async def request(self, method, **params):
        return await self.broker.handle({'method': method, 'params': params})

    async def test_identity_cwd_and_metadata_only_audit(self):
        r = await self.request('command_run', command='id -u; pwd; printf private-test-marker', cwd=str(self.root))
        self.assertEqual(r['returncode'], 0)
        self.assertIn(str(os.getuid()), r['output'])
        self.assertIn(str(self.root), r['output'])
        audit = (self.root/'audit.jsonl').read_text()
        self.assertNotIn('private-test-marker', audit)
        self.assertNotIn(str(self.root), audit)
        self.assertIn('command_sha256', audit)

    async def test_timeout_async_cancel_and_recovery(self):
        r = await self.request('command_run', command='sleep 10', cwd='/', timeout=1)
        self.assertEqual(r['state'], 'timed_out')
        r = await self.request('command_start', command='sleep 10', cwd='/')
        self.assertEqual((await self.request('job_status', job_id=r['id']))['state'], 'running')
        self.assertEqual((await self.request('job_cancel', job_id=r['id']))['state'], 'cancelled')
        r = await self.request('command_run', command='exit 7', cwd='/')
        self.assertEqual(r['returncode'], 7)
        r = await self.request('command_run', command='printf recovered', cwd='/')
        self.assertEqual(r['output'], 'recovered')

    async def test_output_bounds(self):
        r = await self.request('command_run', command="python3 -c 'print(\"x\"*200000)'", cwd='/', output_limit=1024)
        self.assertTrue(r['truncated'])
        self.assertLessEqual(len(r['output']), 1024)

    async def test_file_roundtrip_backup_mode_atomic_move(self):
        path = self.root/'data.txt'
        r = await self.request('file_write', path=str(path), text='first', mode=0o640)
        self.assertEqual(r['returncode'], 0)
        r = await self.request('file_write', path=str(path), text='second')
        details = json.loads(r['output'])
        self.assertTrue(details['atomic'])
        self.assertEqual(Path(details['backup']).read_text(), 'first')
        self.assertEqual(stat.S_IMODE(Path(details['backup']).stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        r = await self.request('file_read', path=str(path), offset=1, limit=3)
        self.assertEqual(json.loads(r['output'])['text'], 'eco')
        destination = self.root/'moved.txt'
        r = await self.request('file_move', path=str(path), destination=str(destination))
        self.assertEqual(r['returncode'], 0)
        self.assertFalse(path.exists())
        self.assertEqual(destination.read_text(), 'second')

    async def test_symlinks_devices_and_overwrite_refused(self):
        path = self.root/'file'
        path.write_text('original')
        link = self.root/'link'
        link.symlink_to(path)
        for method, params in [('file_read', {}), ('file_write', {'text':'no'}), ('file_move', {'destination':str(self.root/'target')})]:
            r = await self.request(method, path=str(link), **params)
            self.assertNotEqual(r['returncode'], 0)
        parent = self.root/'parent-link'
        parent.symlink_to(self.root)
        r = await self.request('file_read', path=str(parent/'file'))
        self.assertNotEqual(r['returncode'], 0)
        r = await self.request('file_read', path='/dev/null')
        self.assertNotEqual(r['returncode'], 0)
        target = self.root/'target'; target.write_text('keep')
        r = await self.request('file_move', path=str(path), destination=str(target))
        self.assertNotEqual(r['returncode'], 0)
        self.assertEqual(target.read_text(), 'keep')

    async def test_validation_is_broker_enforced(self):
        bad = [
            ('command_run', {'command':'pwd','cwd':'relative'}),
            ('command_run', {'command':'pwd','cwd':'/','timeout':True}),
            ('file_read', {'path':'/tmp/a','limit':65537}),
            ('file_read', {'path':'/tmp/a','offset':-1}),
            ('file_write', {'path':'/tmp/a','text':'é'*131072}),
            ('file_write', {'path':'/tmp/a','text':'ok','mode':0o7777}),
            ('file_move', {'path':'/tmp/a','destination':'relative'}),
            ('job_status', {'job_id':'../bad'}),
        ]
        for method, params in bad:
            with self.subTest(method=method, params=params.keys()), self.assertRaises(ValueError):
                await self.request(method, **params)
        self.broker.enabled = False
        with self.assertRaises(PermissionError):
            await self.request('command_run', command='pwd', cwd='/')

    async def test_concurrency_cap(self):
        jobs = await asyncio.gather(*(self.request('command_start', command='sleep 10', cwd='/') for _ in range(8)))
        with self.assertRaises(ValueError):
            await self.request('command_start', command='sleep 10', cwd='/')
        await asyncio.gather(*(self.request('job_cancel', job_id=j['id']) for j in jobs))

    async def test_audit_symlink_refused_before_execution(self):
        path = self.root/'target'; path.write_text('untouched')
        (self.root/'audit.jsonl').symlink_to(path)
        with self.assertRaises(OSError):
            await self.request('command_run', command='printf hello', cwd='/')
        self.assertEqual(path.read_text(), 'untouched')


class ConfigurationTests(unittest.TestCase):
    def test_execution_disabled_by_default(self):
        with self.assertRaises(ValueError):
            environment_options({})

    def test_root_opt_in_and_modes(self):
        with patch('os.getuid', return_value=0):
            with self.assertRaises(ValueError):
                environment_options({'HOMELAB_ENABLE_EXECUTION':'true'})
            prefix, uid, _ = environment_options({'HOMELAB_ENABLE_EXECUTION':'true','HOMELAB_ALLOW_ROOT':'true'})
            self.assertEqual(prefix, [])
            self.assertEqual(uid, 0)
            prefix, _, _ = environment_options({'HOMELAB_ENABLE_EXECUTION':'true','HOMELAB_ALLOW_ROOT':'true','HOMELAB_BROKER_MODE':'host-root'})
            self.assertIn('/usr/bin/nsenter', prefix)
        with patch('os.getuid', return_value=1000):
            with self.assertRaises(ValueError):
                environment_options({'HOMELAB_ENABLE_EXECUTION':'true','HOMELAB_ALLOW_ROOT':'true','HOMELAB_BROKER_MODE':'host-root'})

    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.assertEqual(private_directory(path, os.getuid()), path)
            path.chmod(0o755)
            with self.assertRaises(ValueError):
                private_directory(path, os.getuid())

    def test_redaction_best_effort(self):
        text = 'password=fixture-secret\n' + 'ghp_' + 'A'*25 + '\n-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----'
        result = redact(text)
        self.assertNotIn('fixture-secret', result)
        self.assertNotIn('ghp_', result)
        self.assertNotIn('\nfixture\n', result)
        self.assertNotIn('partial-secret', redact('-----BEGIN PRIVATE KEY-----\npartial-secret'))

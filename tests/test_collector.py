import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).resolve().parents[1]/'host'/'collect_health.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def test_docker_disabled_without_opt_in(self):
        with patch.object(collector, 'INCLUDE_DOCKER', False), patch.object(collector, 'command') as command:
            self.assertFalse(collector.docker()['available'])
            command.assert_not_called()

    def test_storage_configurable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collector, 'MOUNTS', [tmp]):
            result = collector.storage()
            self.assertEqual(result[0]['mount'], tmp)
            self.assertTrue(result[0]['available'])

    def test_collection_failure_is_metadata_only(self):
        def fail():
            raise RuntimeError('private-error-text')
        with patch.object(collector, 'system', fail), patch.object(collector, 'docker', return_value={}), patch.object(collector, 'storage', return_value=[]), patch.object(collector, 'logs', return_value={}), patch.object(collector, 'network', return_value={}):
            data = collector.collect()
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['system']['error'], 'collection_failed')
        self.assertNotIn('private-error-text', str(data))

    def test_log_collection_never_requests_message_field(self):
        with patch.object(collector, 'command', return_value=('{"_SYSTEMD_UNIT":"demo.service"}\n',None)) as command:
            result = collector.logs()
        arguments = command.call_args.args[0]
        self.assertIn('--output-fields=PRIORITY,_SYSTEMD_UNIT,_TRANSPORT', arguments)
        self.assertEqual(result['by_unit'], {'demo.service':1})
        self.assertNotIn('MESSAGE', ' '.join(arguments))

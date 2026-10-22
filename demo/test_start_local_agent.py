"""Offline launcher checks. No model requests, no server startup."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ENTRY = Path(__file__).with_name('start_local_agent.py')
CONFIG = ENTRY.resolve().parents[1].with_name('digital-life-organizer')

class StartupTests(unittest.TestCase):
    def run_entry(self, args):
        output = io.StringIO()
        with patch.object(sys, 'argv', [str(ENTRY), *args]), contextlib.redirect_stdout(output):
            runpy.run_path(str(ENTRY), run_name='__main__')
        return output.getvalue()

    def test_check_imports_correct_checkout_and_loads_key_without_network(self):
        import httpx
        with patch.object(httpx.Client, 'send', side_effect=AssertionError('Network forbidden')):
            output = self.run_entry(['--check'])
        data = json.loads(output.splitlines()[-1])
        self.assertEqual(Path(data['code_root']), ENTRY.resolve().parents[1])
        self.assertEqual(Path(data['venv']), CONFIG / '.venv')
        self.assertTrue(data['api_key_loaded'])
        self.assertEqual(data['model_requests'], 0)
        self.assertEqual(data['base_url'], 'https://api.deepseek.com')
        self.assertEqual(data['model'], 'deepseek-flash')
        import os
        self.assertNotIn(os.environ['FILEFORGE_AGENT_PLANNER_API_KEY'], output)

    def test_wrong_interpreter_fails_closed(self):
        with patch.object(sys, 'prefix', 'not-the-project-venv'), self.assertRaises(SystemExit) as raised:
            self.run_entry(['--check'])
        self.assertEqual(raised.exception.code, 2)

    def test_missing_configuration_fails_without_secret_output(self):
        with patch.object(sys, 'prefix', str(CONFIG / 'missing-config/.venv')), self.assertRaises(SystemExit) as raised:
            self.run_entry(['--check', '--config-root', str(CONFIG / 'missing-config')])
        self.assertEqual(raised.exception.code, 2)

if __name__ == '__main__':
    unittest.main()

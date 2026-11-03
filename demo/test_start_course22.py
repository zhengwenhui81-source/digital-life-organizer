"""Offline tests; all credentials below are synthetic."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from start_course22 import load_settings


class LocalSettingsTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text(text, encoding="utf-8-sig")
            return load_settings(path)

    def test_key_loaded_without_changing_parent_environment(self):
        before = dict(os.environ)
        value = self.load("FILEFORGE_AGENT_PLANNER_API_KEY=synthetic-test-only")
        self.assertEqual(value["FILEFORGE_AGENT_PLANNER_API_KEY"], "synthetic-test-only")
        self.assertEqual(dict(os.environ), before)

    def test_literal_quotes_comments_and_export(self):
        value = self.load('export FILEFORGE_AGENT_PLANNER_API_KEY="synthetic#literal" # comment\n')
        self.assertEqual(value["FILEFORGE_AGENT_PLANNER_API_KEY"], "synthetic#literal")

    def test_missing_and_empty_key_fail(self):
        for text in ("", "FILEFORGE_AGENT_PLANNER_API_KEY=", 'FILEFORGE_AGENT_PLANNER_API_KEY=" "'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.load(text)

    def test_file_settings_override_stale_shell(self):
        with patch.dict(os.environ, {"FILEFORGE_AGENT_PLANNER_MODEL": "stale-model"}):
            value = self.load("FILEFORGE_AGENT_PLANNER_API_KEY=synthetic\nFILEFORGE_AGENT_PLANNER_MODEL=deepseek-chat")
        self.assertEqual(value["FILEFORGE_AGENT_PLANNER_MODEL"], "deepseek-chat")

    def test_invalid_values_fail_without_echoing_credentials(self):
        for suffix in ('FILEFORGE_AGENT_PLANNER_API_KEY="secret-unclosed',
                       'FILEFORGE_AGENT_PLANNER_API_KEY=${SHELL_SECRET}',
                       'FILEFORGE_AGENT_PLANNER_API_KEY=synthetic\nFILEFORGE_AGENT_PLANNER_API_KEY=duplicate'):
            with self.subTest(), self.assertRaises(ValueError) as raised:
                self.load(suffix)
            self.assertNotIn("secret-unclosed", str(raised.exception))
            self.assertNotIn("SHELL_SECRET", str(raised.exception))

    def test_credential_urls_and_demo_mode_rejected(self):
        for setting in ("FILEFORGE_AGENT_PLANNER_BASE_URL=https://user:secret@example.com/v1",
                        "FILEFORGE_AGENT_PLANNER_BASE_URL=https://example.com/v1?key=secret",
                        "FILEFORGE_AGENT_PLANNER_MODE=demo"):
            with self.subTest(), self.assertRaises(ValueError):
                self.load("FILEFORGE_AGENT_PLANNER_API_KEY=synthetic\n" + setting)

    def test_unrelated_environment_not_imported(self):
        value = self.load("FILEFORGE_AGENT_PLANNER_API_KEY=synthetic\nHTTP_PROXY=ignored\nOTHER_KEY=ignored")
        self.assertNotIn("HTTP_PROXY", value)
        self.assertNotIn("OTHER_KEY", value)


if __name__ == "__main__":
    unittest.main()

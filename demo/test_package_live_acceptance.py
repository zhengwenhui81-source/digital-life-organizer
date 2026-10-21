"""Safety checks for B's opt-in acceptance launcher; never run actual Package writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from package_live_acceptance import controlled_planner, prepare


class LauncherSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="b-package-launcher-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "独立验收"

    def test_requires_new_directory_and_preserves_existing_bytes(self):
        self.root.mkdir()
        sentinel = self.root / "keep.txt"
        sentinel.write_bytes(b"untouched")
        with self.assertRaises(FileExistsError):
            prepare(self.root, 18000)
        self.assertEqual(sentinel.read_bytes(), b"untouched")
        self.assertEqual(list(self.root.iterdir()), [sentinel])

    def test_relative_and_missing_parent_are_rejected_without_creation(self):
        for directory in (Path("relative-workspace"), self.parent / "missing" / "child"):
            with self.assertRaises(ValueError):
                prepare(directory, 18000)
        self.assertFalse((self.parent / "missing").exists())

    def test_only_owned_sources_are_created_not_package_outputs(self):
        manifest = prepare(self.root, 18000)
        self.assertEqual(manifest["kind"], "controlled-plan-real-tools-not-LLM")
        self.assertEqual(len(manifest["cases"]), 7)
        for directory in manifest["cases"].values():
            source = Path(directory)
            self.assertEqual(source.parent, self.root)
            self.assertFalse(any(p.name.startswith("package_") for p in source.iterdir()))
        self.assertIn("必须提交报名表", (self.root / "normal" / "通知.txt").read_text(encoding="utf-8"))
        self.assertTrue((self.root / "partial_source_changed" / "附表.txt").is_file())

    def test_controlled_plan_has_no_authorization_or_fabricated_tool_results(self):
        manifest = prepare(self.root, 18000)
        allowed = {Path(p) for p in manifest["cases"].values()}
        plan = controlled_planner(allowed)("task_test", "准备报名材料包", manifest["cases"]["normal"])
        self.assertEqual(plan["steps"][-1]["tool"], "build_package")
        self.assertEqual(plan["steps"][-1]["arguments"], {})
        self.assertNotIn("results", plan)
        self.assertTrue(all(s["risk"] == "low" for s in plan["steps"][:-1]))
        self.assertFalse(any("approved" in s["arguments"] or "preview_id" in s["arguments"] for s in plan["steps"]))

    def test_planner_refuses_other_workspace(self):
        with self.assertRaisesRegex(ValueError, "only accepts"):
            controlled_planner({self.root})("task_test", "goal", str(self.parent))

    def test_reparse_ancestor_is_rejected(self):
        from types import SimpleNamespace
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_file_attributes=0x400, st_mode=0o040755)):
            with self.assertRaisesRegex(ValueError, "Links/reparse"):
                prepare(self.root, 18000)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()

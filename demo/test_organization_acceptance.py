"""Controlled temporary-file tests only, NOT actual organization acceptance."""
import contextlib
import copy
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import organization_acceptance as tool


class AcceptanceToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="b-org-unit-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "独立验收"
        tool.generate(self.root)
        self.workspace = self.root / "workspace"
        self.baseline = tool.load_json(self.root / "evidence/baseline.json")
        self.ready = tool.load_json(self.root / "READY.json")

    def evidence(self, copies=None):
        # These synthetic artifacts exercise observer code; they never prove a real run.
        raw = {"task_id": "unit-test-only", "decisions": [
            {"source": name, "category": row["label"]} for name, row in self.baseline["truth"].items()
        ], "copies": copies or []}
        review = {"dataset_id": self.ready["dataset_id"], "baseline_sha256": self.ready["baseline_sha256"],
                  "raw_sha256": "", "run_kind": "real", "task_id": "unit-test-only", "task_pointer": "/task_id",
                  "category_labels": {label: label for label in tool.LABELS},
                  "classifications": [{"source": row["source"], "source_pointer": f"/decisions/{i}/source", "category_pointer": f"/decisions/{i}/category"} for i, row in enumerate(raw["decisions"])],
                  "execution_status": "completed" if copies else "not_run", "copies": [
                      {"source": row["source"], "target": row["target"], "status": "succeeded" if row["success"] else "failed",
                       "source_pointer": f"/copies/{i}/source", "target_pointer": f"/copies/{i}/target", "success_pointer": f"/copies/{i}/success"}
                      for i, row in enumerate(copies or [])]}
        return raw, review

    def observe(self, raw, review):
        raw_path, review_path = self.parent / "raw.json", self.parent / "review.json"
        data = tool.json_bytes(raw)
        raw_path.write_bytes(data)
        review = {**review, "raw_sha256": tool.digest(data)}
        review_path.write_bytes(tool.json_bytes(review))
        return tool.check(self.root, review_path, raw_path)

    def target(self, name, content):
        path = self.workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)  # Unit observation setup, not an Agent copy.

    def test_dataset_formats_labels_names_and_output_exclusion(self):
        self.assertEqual(len(self.baseline["truth"]), 12)
        self.assertEqual(len(self.baseline["files"]), 14)
        self.assertNotEqual(self.baseline["truth"]["学习/笔记.txt"]["label"], self.baseline["truth"]["财务/笔记.txt"]["label"])
        self.assertFalse(any(name.startswith("整理结果/") for name in self.baseline["truth"]))
        self.assertTrue((self.workspace / "文档/课程材料.pdf").read_bytes().startswith(b"%PDF"))
        self.assertTrue((self.workspace / "文档/课程大纲.docx").read_bytes().startswith(b"PK"))

    def test_generator_refuses_existing_even_empty_directory(self):
        before = tool.inventory(self.root)
        with self.assertRaises(FileExistsError):
            tool.generate(self.root)
        empty = self.parent / "empty"
        empty.mkdir()
        with self.assertRaises(FileExistsError):
            tool.generate(empty)
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual(tool.inventory(self.root), before)

    def test_generator_refuses_relative_path_or_missing_parent(self):
        with self.assertRaises(tool.UnsafeInput):
            tool.generate(Path("relative"))
        with self.assertRaises(FileNotFoundError):
            tool.generate(self.parent / "missing" / "new")

    def test_no_real_results_is_blocked_not_95_percent(self):
        report = tool.check(self.root)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"]["status"], "blocked")
        self.assertIsNone(report["classification"]["accuracy"])
        self.assertIsNone(report["classification"]["coverage"])
        self.assertEqual(report["execution"]["status"], "not_run")
        self.assertEqual(report["originals"]["status"], "passed")
        self.assertFalse(report["e2e_certified"])

    def test_checker_cli_readonly_and_both_report_formats(self):
        before = tool.inventory(self.root)
        with mock.patch.object(tool, "generate", side_effect=AssertionError("No generation in check")):
            for fmt in ("json", "markdown"):
                with contextlib.redirect_stdout(io.StringIO()) as stream:
                    code = tool.main(["check", "--directory", str(self.root), "--format", fmt])
                self.assertEqual(code, 2)
                self.assertIn("blocked", stream.getvalue())
        self.assertEqual(tool.inventory(self.root), before)

    def test_same_size_changed_original_is_failed(self):
        path = self.workspace / "未知/数据.bin"
        path.write_bytes(b"\x00\x01\x02\xfe")
        report = tool.check(self.root)
        self.assertEqual(report["status"], "failed")
        self.assertIn("未知/数据.bin", report["originals"]["changed_or_missing"])

    def test_missing_original_is_failed(self):
        (self.workspace / "资料/说明.txt").unlink()  # Owned temporary unit file only.
        self.assertEqual(tool.check(self.root)["originals"]["status"], "failed")

    def test_preexisting_target_overwrite_is_failed(self):
        self.target("整理结果/财务/笔记.txt", b"overwritten synthetic sentinel")
        report = tool.check(self.root)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["preexisting_output"]["status"], "failed")

    def test_unreported_duplicate_copy_is_failed(self):
        content = (self.workspace / "学习/笔记.txt").read_bytes()
        self.target("整理结果/课程/extra.txt", content)
        report = tool.check(self.root)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["execution"]["unexpected_files"], ["整理结果/课程/extra.txt"])

    def test_observed_bytes_match_without_certifying_approval(self):
        name, target = "学习/笔记.txt", "整理结果/课程/笔记.txt"
        self.target(target, (self.workspace / name).read_bytes())
        raw, review = self.evidence([{"source": name, "target": target, "success": True}])
        report = self.observe(raw, review)
        self.assertEqual(report["execution"]["status"], "passed")
        self.assertTrue(report["execution"]["copies"][0]["bytes_match"])
        self.assertEqual(report["status"], "unverifiable")
        self.assertFalse(report["e2e_certified"])
        self.assertAlmostEqual(report["classification"]["coverage"], 7 / 12)

    def test_reported_success_with_missing_or_wrong_bytes_is_failed(self):
        for content in (None, b"incorrect target"):
            with self.subTest(content=content):
                name, target = "学习/笔记.txt", "整理结果/课程/wrong.txt"
                if content is not None:
                    self.target(target, content)
                raw, review = self.evidence([{"source": name, "target": target, "success": True}])
                report = self.observe(raw, review)
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["execution"]["copies"][0]["status"], "failed")

    def test_failed_copy_and_residual_never_become_success(self):
        name, target = "学习/笔记.txt", "整理结果/课程/partial.txt"
        self.target(target, b"partial")
        raw, review = self.evidence([{"source": name, "target": target, "success": False}])
        review["execution_status"] = "failed"
        report = self.observe(raw, review)
        self.assertEqual(report["execution"]["status"], "failed")
        self.assertTrue((self.workspace / target).exists())  # Checker never cleans it.

    def test_duplicate_source_or_case_insensitive_target_is_rejected(self):
        pairs = [
            [{"source": "学习/笔记.txt", "target": "整理结果/课程/a.txt", "success": True}, {"source": "学习/笔记.txt", "target": "整理结果/课程/b.txt", "success": True}],
            [{"source": "学习/笔记.txt", "target": "整理结果/课程/a.txt", "success": True}, {"source": "资料/说明.txt", "target": "整理结果/课程/A.TXT", "success": True}],
        ]
        for copies in pairs:
            raw, review = self.evidence(copies)
            report = self.observe(raw, review)
            self.assertEqual(report["execution"]["status"], "unverifiable")
            self.assertTrue(report["issues"])
            self.assertTrue(all(row["status"] == "unverifiable" for row in report["execution"]["copies"]))

    def test_occupied_target_is_rejected_even_if_report_claims_success(self):
        raw, review = self.evidence([{"source": "财务/笔记.txt", "target": "整理结果/财务/笔记.txt", "success": True}])
        report = self.observe(raw, review)
        self.assertEqual(report["execution"]["status"], "unverifiable")
        self.assertIn("occupied target", " ".join(report["issues"]))

    def test_windows_relative_paths_and_unsafe_path_rejection(self):
        self.assertEqual(tool.relative("中文路径\\计划.txt"), "中文路径/计划.txt")
        for value in ("../x", "a/../x", "C:\\x", "\\\\server\\share\\x", "/x", "x:stream", "a/NUL.txt", "a/x.", "a//b", "a/./x"):
            with self.subTest(value=value), self.assertRaises(tool.UnsafeInput):
                tool.relative(value)

    def test_reparse_and_symlink_guards_fail_closed_without_reading(self):
        for mode, attrs in ((stat.S_IFDIR, 0x400), (stat.S_IFLNK, 0)):
            fake = SimpleNamespace(st_mode=mode, st_file_attributes=attrs)
            with mock.patch.object(Path, "lstat", return_value=fake), self.assertRaises(tool.UnsafeInput):
                tool.guarded(self.root)

    def test_hardlinked_file_is_rejected(self):
        path = self.workspace / "未知/数据.bin"
        with mock.patch.object(tool, "guarded", return_value=path), mock.patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=2)), self.assertRaises(tool.UnsafeInput):
            tool.stable_bytes(path)

    def test_changed_or_incomplete_baseline_is_rejected(self):
        path = self.root / "evidence/baseline.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(tool.UnsafeInput):
            tool.check(self.root)

    def test_nonreal_provenance_task_mismatch_and_invalid_pointers_are_unverifiable(self):
        for mutate in (lambda r: r.update(run_kind="fixture"), lambda r: r.update(dataset_id="foreign"), lambda r: r.update(task_id="foreign"), lambda r: r["classifications"][0].update(category_pointer="/missing")):
            raw, review = self.evidence()
            mutate(review)
            report = self.observe(raw, review)
            self.assertEqual(report["classification"]["status"], "unverifiable")
            self.assertIsNone(report["classification"]["accuracy"])

    def test_incomplete_or_duplicate_decisions_do_not_produce_cherry_picked_accuracy(self):
        for kind in ("missing", "duplicate"):
            raw, review = self.evidence()
            if kind == "missing":
                review["classifications"].pop()
            else:
                review["classifications"].append(copy.deepcopy(review["classifications"][0]))
            report = self.observe(raw, review)
            self.assertEqual(report["classification"]["status"], "unverifiable")
            self.assertIsNone(report["classification"]["accuracy"])

    def test_metric_denominators_and_abstention_do_not_inflate_accuracy(self):
        truth = {"a": {"label": "course"}, "b": {"label": "finance"}, "c": {"label": "needs_confirmation"}}
        measured = tool.classification_metrics(truth, {"a": "course", "b": "course", "c": "needs_confirmation"})
        self.assertEqual(measured["accuracy"], 0.5)
        self.assertEqual(measured["coverage"], 2 / 3)
        self.assertEqual(measured["status"], "failed")
        abstained = tool.classification_metrics(truth, dict.fromkeys(truth, "needs_confirmation"))
        self.assertIsNone(abstained["accuracy"])
        self.assertEqual(abstained["coverage"], 0)
        self.assertIsNone(abstained["target_met"])


if __name__ == "__main__":
    unittest.main()

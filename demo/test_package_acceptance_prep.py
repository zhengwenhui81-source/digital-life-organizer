"""In-memory preparation tests. No course materials are generated."""
import copy
import unittest

from package_acceptance_prep import inspect_capabilities, inspect_checklist


def template():
    return {"items": [dict(slot=i, filename=None, extension=None, file_type=None,
                           readability=None, expected_handling=None, status="待提供")
                      for i in range(1, 23)]}


class PreparationTests(unittest.TestCase):
    def test_pending_template_does_not_claim_acceptance(self):
        value = template()
        original = copy.deepcopy(value)
        result = inspect_checklist(value)
        self.assertTrue(result["template_valid"])
        self.assertEqual((result["status"], result["verified_files"]), ("blocked", 0))
        self.assertEqual(value, original)

    def test_wrong_count_and_malformed_rows(self):
        for value in (None, [], {}, {"items": []}, {"items": [None] * 22}):
            with self.subTest(value=value):
                self.assertFalse(inspect_checklist(value)["template_valid"])

    def test_invented_details_are_not_pending_template(self):
        for key in ("filename", "extension", "file_type", "readability", "expected_handling"):
            value = template()
            value["items"][0][key] = "invented"
            self.assertFalse(inspect_checklist(value)["template_valid"])

    def test_slot_identity_and_status(self):
        for key, replacement in (("slot", 2), ("status", "passed")):
            value = template()
            value["items"][0][key] = replacement
            self.assertFalse(inspect_checklist(value)["template_valid"])

    def test_missing_field_is_not_explicit_pending_null(self):
        value = template()
        del value["items"][0]["filename"]
        self.assertFalse(inspect_checklist(value)["template_valid"])

    def test_current_style_static_blockers(self):
        result = inspect_capabilities(
            'class Router:\n def __init__(self):\n  self._tools: dict = {"read_document": reader}',
            '_MAX_CANDIDATE_READS = 10\nraise Exception("Package execution is not available")')
        self.assertEqual(result["candidate_read_limit"], 10)
        self.assertTrue(result["execution_unavailable_guard_present"])
        self.assertEqual(len(result["missing_default_router_tools"]), 3)

    def test_future_registration_is_not_runtime_acceptance(self):
        result = inspect_capabilities(
            'class Router:\n def __init__(self):\n  self._tools: dict = '
            '{"plan_package": p, "build_package": b, "write_package_report": w}', '')
        self.assertEqual(result["missing_default_router_tools"], [])
        self.assertFalse(result["runtime_execution_verified"])
        self.assertEqual(result["status"], "blocked")

    def test_unknown_source_structure_is_not_success(self):
        result = inspect_capabilities('', '')
        self.assertIsNone(result["candidate_read_limit"])
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()

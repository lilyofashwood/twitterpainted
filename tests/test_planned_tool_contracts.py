"""No real external tool is launched by these recovery regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import tooling
from engine.analyzers import tool_suite


class PlannedToolContracts(unittest.TestCase):
    def test_installed_stubs_are_not_available(self):
        with patch.object(tooling.shutil, "which", side_effect=lambda cmd: "/mock/" + cmd):
            status = tooling.get_tool_status()
        for name in tooling.PLANNED_INTEGRATIONS:
            with self.subTest(name=name):
                self.assertFalse(status[name]["available"])
                self.assertTrue(status[name]["command_found"])
                self.assertEqual(status[name]["state"], "planned")
                self.assertIn("placeholder", status[name]["reason"])
        self.assertTrue(status["stegosuite"]["available"])
        self.assertTrue(status["jpeginfo"]["available"])

    def test_missing_planned_commands_still_say_planned(self):
        with patch.object(tooling.shutil, "which", return_value=None):
            status = tooling.get_tool_status()
        self.assertEqual(status["openpuff"]["state"], "planned")
        self.assertFalse(status["openpuff"]["command_found"])
        self.assertEqual(status["jpeginfo"]["state"], "unavailable")

    def test_selected_planned_integrations_never_run_or_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            carrier = root / "fixture.bin"
            carrier.write_bytes(b"review fixture")
            output = root / "results"
            with patch.object(tool_suite, "_detect_mime", return_value="application/octet-stream"), \
                    patch.object(tool_suite.shutil, "which", side_effect=lambda cmd: "/mock/" + cmd), \
                    patch.object(tool_suite.subprocess, "run", side_effect=AssertionError("A planned tool was launched")):
                tool_suite.analyze_tool_suite(carrier, output, selected_tools=tooling.PLANNED_INTEGRATIONS)
            results = json.loads((output / "results.json").read_text())
            self.assertEqual(set(results), set(tooling.PLANNED_INTEGRATIONS))
            for result in results.values():
                self.assertEqual(result["status"], "skipped")
                self.assertIn("placeholder", result["reason"])

    def test_real_presence_probe_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(tool_suite.shutil, "which", return_value="/mock/stegosuite"):
            output = Path(tmp)
            tool_suite._record_presence_probe(output, "stegosuite", ["stegosuite"], note="Real command presence only; launch separately.")
            result = json.loads((output / "results.json").read_text())["stegosuite"]
            self.assertEqual(result["status"], "ok")
            self.assertIn("presence only", result["output"][1])


if __name__ == "__main__":
    unittest.main()

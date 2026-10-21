"""Synthetic migration compatibility acceptance tests; no real profile fixtures."""

import ctypes
import json
import sys
import tempfile
import unittest
from pathlib import Path

from soulsteads.hermes_import import ImportErrorSafe, import_profile, inspect_source


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name).resolve() / "source"
        self.source.mkdir(mode=0o700)
        (self.source / "config.yaml").write_text("{}\n")
        self.destination = Path(self.tmp.name).resolve() / "home"

    def findings(self, config):
        (self.source / "config.yaml").write_text(config)
        report = inspect_source("helper", self.source)
        self.assertEqual(report["compatibility"]["schema_version"], 1)
        self.assertFalse(report["activation_ready"])
        return report, {f["id"]: f for f in report["compatibility"]["findings"]}

    def test_section_findings_never_serialize_configuration_values_or_keys(self):
        marker = "PRIVATE_SYNTHETIC_MARKER"
        config = "\n".join(
            f"{key}: {{private: {marker}}}"
            for key in ("model", "mcp_servers", "tools", "approvals", "memory", marker)
        )
        report, findings = self.findings(config)
        self.assertNotIn(marker, json.dumps(report))
        for key in (
            "model-provider",
            "mcp",
            "tools",
            "permissions",
            "external-memory",
            "unknown-configuration",
        ):
            self.assertEqual(findings[key]["status"], "manual_required")
            self.assertTrue(findings[key]["next_action"])
        with self.assertRaises(ImportErrorSafe):
            import_profile("helper", self.source, path=self.destination)
        self.assertFalse(self.destination.exists())

    def test_defaults_and_explicit_disabled_config_allow_basic_import(self):
        report, findings = self.findings("model: false\n")
        self.assertEqual(findings["model-provider"]["status"], "disabled")
        self.assertEqual(findings["identity"]["status"], "defaults")
        self.assertEqual(findings["local-memory"]["status"], "defaults")
        self.assertEqual(report["unsupported"], [])

    @unittest.skipUnless(
        sys.platform == "linux", "Apply requires Linux no-replace publication"
    )
    def test_basic_import_succeeds_with_no_unsupported_settings_on_linux(self):
        if not hasattr(ctypes.CDLL(None), "renameat2"):
            self.skipTest("Apply requires renameat2")
        report, _ = self.findings("model: false\n")
        applied = import_profile("helper", self.source, path=self.destination)
        self.assertEqual(applied["compatibility"], report["compatibility"])

    def test_apply_refuses_missing_renameat2_without_publishing(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        self.findings("model: false\n")
        with (
            patch(
                "soulsteads.hermes_import.ctypes.CDLL", return_value=SimpleNamespace()
            ),
            self.assertRaisesRegex(
                ImportErrorSafe,
                "^atomic no-replace import publication requires Linux renameat2$",
            ),
        ):
            import_profile("helper", self.source, path=self.destination)
        self.assertFalse(self.destination.exists())

    def test_selected_documents_and_untransferred_state_are_distinct(self):
        (self.source / "SOUL.md").write_text("Synthetic identity")
        (self.source / "MEMORY.md").write_text("Synthetic memory")
        _, findings = self.findings("{}")
        self.assertEqual(findings["identity"]["status"], "selected")
        self.assertEqual(findings["local-memory"]["status"], "selected")
        for key in ("sessions", "schedules", "messaging", "oauth"):
            self.assertEqual(findings[key]["status"], "not_transferred")

    def test_runtime_settings_still_require_partial_acknowledgement(self):
        for key in ("terminal", "agent", "display", "delegation"):
            with self.subTest(key=key):
                report, _ = self.findings(f"{key}: {{example: synthetic}}")
                self.assertTrue(report["unsupported"])
                with self.assertRaises(ImportErrorSafe):
                    import_profile("helper", self.source, path=self.destination)

    def test_disabled_primary_settings_do_not_hide_secondary_settings(self):
        report, findings = self.findings(
            "model: false\ndelegation: {model: synthetic}\n"
            "approvals: false\nsecurity: {example: true}\n"
        )
        self.assertEqual(findings["model-provider"]["status"], "manual_required")
        self.assertEqual(findings["permissions"]["status"], "manual_required")
        self.assertTrue(report["unsupported"])

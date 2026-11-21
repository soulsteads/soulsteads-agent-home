"""Synthetic migration compatibility acceptance tests; no real profile fixtures."""

import ctypes
import json
import sys
import tempfile
import unittest
from pathlib import Path

from soulsteads.compatibility import mark_copied, report as compatibility_report
from soulsteads.hermes_import import ImportErrorSafe, import_profile, inspect_source


class CompatibilityReadinessTests(unittest.TestCase):
    def test_configured_dependencies_are_manual_and_runtime_checks_are_unrun(self):
        sentinels = {
            "model": "synthetic-primary-provider/model",
            "fallback_model": "synthetic-fallback-provider/model",
            "chat": {"owner": "synthetic-chat-owner", "route": "synthetic-chat-route"},
            "tools": {"required": ["synthetic-harmless-tool"]},
            "mcp_servers": {
                "synthetic-private-server": {
                    "url": "https://synthetic.invalid/private-route",
                    "api_key": "synthetic-secret-value",
                }
            },
            "memory": {"provider": "hindsight", "scope": "synthetic-private-scope"},
            "private_unknown_key_sentinel": "synthetic-private-value",
        }
        report, manual = compatibility_report(
            documents={"SOUL.md": b"synthetic instructions"},
            skills=[],
            config=sentinels,
            hindsight_detected=False,
        )
        findings = {item["id"]: item for item in report["findings"]}
        readiness = report["readiness"]
        transfer = {item["id"]: item["state"] for item in readiness["transfers"]}
        checks = {item["id"]: item for item in readiness["runtime_checks"]}
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(
            all(
                set(item)
                == {"id", "category", "status", "consequence", "next_action"}
                for item in report["findings"]
            )
        )
        self.assertEqual(
            readiness["runtime_status_values"], ["not_run", "passed", "failed"]
        )

        for finding_id in (
            "fallback-model",
            "chat-routing",
            "tools",
            "mcp",
            "external-memory",
        ):
            self.assertEqual(findings[finding_id]["status"], "manual_required")
        for item_id in (
            "fallback-model",
            "chat-routing",
            "required-tools",
            "external-memory",
        ):
            self.assertEqual(transfer[item_id], "manual_setup")
        self.assertEqual(transfer["sessions"], "not_transferred")
        self.assertEqual(transfer["vault"], "not_transferred")
        self.assertEqual(transfer["hermes-transcripts"], "not_transferred")
        self.assertTrue(manual)
        for check_id in (
            "native-identity",
            "native-workspace",
            "native-skills",
            "provider-identity",
            "provider-fallback",
            "chat-ownership-routing",
            "harmless-required-tool",
            "hindsight-scoped-recall",
            "hindsight-deny-isolation",
            "network-permissions",
        ):
            self.assertEqual(checks[check_id]["status"], "not_run")
        for check_id in (
            "provider-fallback",
            "harmless-required-tool",
            "hindsight-scoped-recall",
            "hindsight-deny-isolation",
        ):
            self.assertTrue(checks[check_id]["applicable"])
        serialized = json.dumps(report)
        for secret in (
            "synthetic-primary-provider/model",
            "synthetic-fallback-provider/model",
            "synthetic-chat-owner",
            "synthetic-chat-route",
            "synthetic-harmless-tool",
            "synthetic-private-server",
            "https://synthetic.invalid/private-route",
            "synthetic-secret-value",
            "synthetic-private-scope",
            "private_unknown_key_sentinel",
            "synthetic-private-value",
        ):
            self.assertNotIn(secret, serialized)

    def test_copy_marker_only_changes_planned_portable_items(self):
        report, _ = compatibility_report(
            documents={"SOUL.md": b"synthetic instructions"},
            skills=["synthetic-skill"],
            config={},
            hindsight_detected=False,
        )
        readiness = report["readiness"]
        before = {item["id"]: item["state"] for item in readiness["transfers"]}
        self.assertEqual(before["portable-instructions"], "planned")
        self.assertEqual(before["portable-skills"], "planned")
        mark_copied(readiness)
        after = {item["id"]: item["state"] for item in readiness["transfers"]}
        self.assertEqual(after["portable-instructions"], "copied")
        self.assertEqual(after["portable-skills"], "copied")
        self.assertEqual(after["sessions"], "not_transferred")
        self.assertTrue(
            all(item["status"] == "not_run" for item in readiness["runtime_checks"])
        )


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

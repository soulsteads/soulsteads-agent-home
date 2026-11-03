"""Offline reports distinguish prepared files from qualified native behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core
from soulsteads.native_config import sync
from soulsteads.verification import verify_home


class NativeReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = core.create(
            "report", "opencode", path=Path(self.tmp.name).resolve() / "home"
        )

    def test_all_adapters_describe_paths_mechanism_and_qualification_limits(self):
        report = verify_home(self.home)
        adapters = {item["runtime"]: item for item in report.get("native_adapters", [])}
        self.assertEqual(set(adapters), {"opencode", "pi", "codex", "claude"})
        for runtime, adapter in adapters.items():
            self.assertEqual(adapter["evidence"], "offline-structural")
            self.assertEqual(adapter["runtime_version"], "unverified")
            self.assertEqual(adapter["mode"], "home-root")
            self.assertTrue(adapter["paths"])
            self.assertTrue(adapter["reload"])
            self.assertTrue(adapter["trust"])
            self.assertIn(
                adapter["mechanism"],
                {"native reference", "generated native projection"},
                runtime,
            )
        self.assertIn(".pi/APPEND_SYSTEM.md", adapters["pi"]["paths"])
        self.assertIn(".codex/config.toml", adapters["codex"]["paths"])
        self.assertNotIn(str(self.home), json.dumps(report))

    def test_memory_config_is_not_connectivity_or_bank_qualification(self):
        sync(
            self.home,
            hindsight={
                "url": "https://synthetic.example/mcp/private-bank/",
                "token_env": "SYNTHETIC_REPORT_TOKEN",
            },
        )
        with patch.dict("os.environ", {}, clear=True):
            report = verify_home(self.home)
        findings = {item["id"]: item for item in report["findings"]}
        self.assertEqual(
            findings.get("memory-credential", {}).get("status"), "needs-review"
        )
        self.assertEqual(
            findings.get("memory-qualification", {}).get("status"), "needs-review"
        )
        self.assertIn("not set", findings["memory-credential"]["consequence"])
        self.assertIn("bank", findings["memory-qualification"]["next_action"])
        self.assertFalse(report["activation_ready"])
        self.assertNotIn("private-bank", json.dumps(report))
        self.assertNotIn("synthetic.example", json.dumps(report))

    def test_present_credential_is_never_reported_as_live_success_or_echoed(self):
        sync(
            self.home,
            hindsight={
                "url": "https://synthetic.example/mcp/bank/",
                "token_env": "SYNTHETIC_REPORT_TOKEN",
            },
        )
        with patch.dict(
            "os.environ", {"SYNTHETIC_REPORT_TOKEN": "fixture-secret-not-for-output"}
        ):
            report = verify_home(self.home)
        findings = {item["id"]: item for item in report["findings"]}
        self.assertEqual(findings.get("memory-credential", {}).get("status"), "passed")
        self.assertEqual(
            findings.get("memory-qualification", {}).get("status"), "needs-review"
        )
        self.assertNotIn("fixture-secret-not-for-output", json.dumps(report))

    def test_no_memory_configuration_needs_no_service_or_credential(self):
        report = verify_home(self.home)
        self.assertFalse(
            any(item["id"].startswith("memory-") for item in report["findings"])
        )
        self.assertEqual(report["status"], "passed")

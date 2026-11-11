"""CLI boundary regressions independent of native Home fixture construction."""

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from soulsteads import cli


class SettingsCliBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_duplicate_and_nonfinite_json_are_rejected_before_engine_call(self):
        for value in (
            '{"model":"one","model":"two"}',
            "NaN",
            "Infinity",
            "1e9999",
            "[" * 1100 + "0" + "]" * 1100,
        ):
            with self.subTest(value=value):
                engine = SimpleNamespace(
                    plan_changes=lambda *a, **k: self.fail(
                        "invalid JSON reached engine"
                    )
                )
                with (
                    patch.dict("sys.modules", {"soulsteads.settings": engine}),
                    redirect_stdout(StringIO()),
                    redirect_stderr(StringIO()),
                ):
                    self.assertEqual(
                        cli.main(
                            [
                                "settings",
                                "set",
                                "--runtime",
                                "opencode",
                                "--key",
                                "@model",
                                "--value",
                                value,
                            ]
                        ),
                        1,
                    )

    def test_saved_plan_does_not_overwrite_existing_file(self):
        destination = self.root / "existing.json"
        destination.write_text("keep this evidence\n")
        engine = SimpleNamespace(plan_changes=lambda *a, **k: {"preview": True})
        with (
            patch.dict("sys.modules", {"soulsteads.settings": engine}),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
            self.assertEqual(
                cli.main(
                    [
                        "settings",
                        "plan",
                        "--runtime",
                        "opencode",
                        "--changes",
                        "[]",
                        "--plan-file",
                        str(destination),
                    ]
                ),
                1,
            )
        self.assertEqual(destination.read_text(), "keep this evidence\n")

    def test_saved_plan_never_follows_output_symlink(self):
        victim = self.root / "victim.json"
        victim.write_text("unchanged\n")
        output = self.root / "plan.json"
        output.symlink_to(victim)
        engine = SimpleNamespace(plan_changes=lambda *a, **k: {"preview": True})
        with (
            patch.dict("sys.modules", {"soulsteads.settings": engine}),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
            self.assertEqual(
                cli.main(
                    [
                        "settings",
                        "plan",
                        "--runtime",
                        "opencode",
                        "--changes",
                        "[]",
                        "--plan-file",
                        str(output),
                    ]
                ),
                1,
            )
        self.assertEqual(victim.read_text(), "unchanged\n")

    def test_launch_passes_native_adapter_environment_without_replacing_host_environment(
        self,
    ):
        home = self.root / "home"
        project = self.root / "project"
        native = {
            "cwd": str(project),
            "argv": ["opencode", str(project)],
            "env": {"OPENCODE_CONFIG_CONTENT": '{"instructions":["fixture"]}'},
        }
        with (
            patch("soulsteads.core.load", return_value={"runtime": "opencode"}),
            patch(
                "soulsteads.launch.prepare_launch",
                return_value=native,
            ),
            patch(
                "soulsteads.cli.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as run,
            patch.dict(
                os.environ,
                {"SOULSTEADS_BOUNDARY_TEST": "preserved"},
            ),
        ):
            self.assertEqual(cli.main(["run", str(home), "--project", str(project)]), 0)
        environment = run.call_args.kwargs.get("env", {})
        self.assertEqual(
            environment.get("OPENCODE_CONFIG_CONTENT"),
            native["env"]["OPENCODE_CONFIG_CONTENT"],
        )
        self.assertEqual(environment.get("SOULSTEADS_BOUNDARY_TEST"), "preserved")

    def test_opencode_resource_overlay_preserves_ambient_native_settings(self):
        ambient = {
            "model": "keep-model",
            "permission": {"bash": "deny"},
            "instructions": ["ambient.md"],
            "skills": {
                "paths": ["ambient-skills"],
                "urls": ["https://example.invalid/skills"],
            },
        }
        requested = {"instructions": ["home.md"], "skills": ["home-skills"]}
        plan = {
            "cwd": str(self.root),
            "argv": ["opencode"],
            "env": {"OPENCODE_CONFIG_CONTENT": json.dumps(requested)},
        }
        with (
            patch("soulsteads.core.load", return_value={"runtime": "opencode"}),
            patch(
                "soulsteads.launch.prepare_launch",
                return_value=plan,
            ),
            patch(
                "soulsteads.cli.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as run,
            patch.dict(
                os.environ,
                {"OPENCODE_CONFIG_CONTENT": json.dumps(ambient)},
            ),
        ):
            self.assertEqual(
                cli.main(["run", str(self.root), "--project", str(self.root)]), 0
            )
        actual = json.loads(run.call_args.kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(actual["model"], ambient["model"])
        self.assertEqual(actual["permission"], ambient["permission"])
        self.assertEqual(actual["instructions"], ["ambient.md", "home.md"])
        self.assertEqual(actual["skills"]["paths"], ["ambient-skills", "home-skills"])
        self.assertEqual(actual["skills"]["urls"], ambient["skills"]["urls"])


if __name__ == "__main__":
    unittest.main()

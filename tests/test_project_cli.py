"""Public project launch selection; never launches a model in ordinary tests."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core


class ProjectCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.home = core.create("project-agent", "pi", path=root / "home")
        self.project = root / "project"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("Synthetic project rules\n")

    def invoke(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(
                    ["run", str(self.home), "--project", str(self.project), *extra]
                )
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_project_dry_run_selects_native_home_resources_without_changing_project(
        self,
    ):
        before = {p.name: p.read_bytes() for p in self.project.iterdir()}
        code, out, err = self.invoke("--dry-run", "--", "--no-session")
        self.assertEqual(code, 0, err)
        plan = json.loads(out)
        self.assertEqual(plan["cwd"], str(self.project))
        self.assertEqual(plan["argv"][0], "pi")
        self.assertIn(str(self.home / ".pi/APPEND_SYSTEM.md"), plan["argv"])
        self.assertEqual(plan["argv"][-1], "--no-session")
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.project.iterdir()}
        )

    def test_project_live_route_passes_native_arguments_without_a_shell(self):
        original = subprocess.run
        calls = []

        def routed(argv, **kwargs):
            if argv[0] == "pi":
                calls.append((argv, kwargs))
                return subprocess.CompletedProcess(argv, 7)
            return original(argv, **kwargs)

        with patch.object(cli.subprocess, "run", side_effect=routed):
            code, _, err = self.invoke("--", "--no-session")
        self.assertEqual(code, 7, err)
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertEqual(argv[0], "pi")
        self.assertIn("--append-system-prompt", argv)
        self.assertEqual(kwargs["cwd"], str(self.project))
        self.assertNotIn("shell", kwargs)

    def test_unqualified_runtime_project_mode_fails_without_launch(self):
        core.configure(self.home, "claude")
        original = subprocess.run

        def routed(argv, **kwargs):
            self.assertNotEqual(argv[0], "claude", "unqualified native launch")
            return original(argv, **kwargs)

        with patch.object(cli.subprocess, "run", side_effect=routed):
            code, _, err = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn("not qualified", err)

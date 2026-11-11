"""Project launch adapters preserve Home and project state."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core
from soulsteads.launch import prepare_launch


class ProjectAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        old_umask = os.umask(0o077)
        self.addCleanup(os.umask, old_umask)
        self.temp = tempfile.TemporaryDirectory(prefix="project-adapters-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.home = root / "agent-home"
        self.home.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.home)], check=True)
        (self.home / "soulsteads.json").write_text(
            json.dumps({"schema_version": 1, "name": "adapter-test", "runtime": "pi"})
        )
        (self.home / ".pi").mkdir()
        (self.home / ".pi" / "APPEND_SYSTEM.md").write_text("identity context\n")
        (self.home / "AGENTS.md").write_text("home instructions\n")
        self.skills = self.home / "skills"
        skill = self.skills / "sample"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: skill-name\ndescription: adapter fixture\n---\nskill context\n"
        )
        (self.home / "codex-auth.json").write_text("credential sentinel\n")
        (self.home / "claude-session.json").write_text("session sentinel\n")
        self.project = root / "project"
        self.project.mkdir()
        (self.project / "untouched.txt").write_text("keep\n")

    def _snapshot(self, root: Path) -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

    def test_native_project_launch_uses_home_resources_and_preserves_state(
        self,
    ) -> None:
        home_before = self._snapshot(self.home)
        project_before = self._snapshot(self.project)

        expected = {"codex": "codex", "claude": "claude", "opencode": "opencode"}
        for runtime, executable in expected.items():
            with self.subTest(runtime=runtime):
                plan = prepare_launch(
                    self.home, runtime, self.project, allow_context_in_argv=True
                )
                self.assertEqual(plan["cwd"], str(self.project))
                self.assertEqual(plan["argv"][0], executable)
                self.assertTrue(plan["qualification"])
                self.assertNotIn("credential sentinel", repr(plan))
                self.assertNotIn("session sentinel", repr(plan))

                if runtime == "claude":
                    self.assertIn("--append-system-prompt", plan["argv"])
                    prompt = plan["argv"][
                        plan["argv"].index("--append-system-prompt") + 1
                    ]
                    for marker in (
                        "identity context",
                        "home instructions",
                        "skill context",
                        "skill-name",
                    ):
                        self.assertIn(marker, prompt)
                    self.assertEqual(plan["env"], {})
                elif runtime == "opencode":
                    overlay = json.loads(plan["env"]["OPENCODE_CONFIG_CONTENT"])
                    self.assertEqual(
                        overlay["instructions"],
                        [
                            str(self.home / ".pi" / "APPEND_SYSTEM.md"),
                            str(self.home / "AGENTS.md"),
                        ],
                    )
                    self.assertEqual(overlay["skills"], [str(self.skills)])
                else:
                    self.assertIn("--config", plan["argv"])
                    override = plan["argv"][plan["argv"].index("--config") + 1]
                    self.assertTrue(override.startswith("developer_instructions="))
                    for marker in (
                        "identity context",
                        "home instructions",
                        "skill context",
                        "skill-name",
                    ):
                        self.assertIn(marker, override)
                    self.assertEqual(plan["env"], {})

        self.assertEqual(self._snapshot(self.home), home_before)
        self.assertEqual(self._snapshot(self.project), project_before)

    def test_explicit_extra_arguments_are_preserved(self) -> None:
        extra = ("--model", "model-name", "--", "literal prompt")
        for runtime in ("codex", "claude", "opencode"):
            with self.subTest(runtime=runtime):
                plan = prepare_launch(
                    self.home,
                    runtime,
                    self.project,
                    extra=extra,
                    allow_context_in_argv=True,
                )
                self.assertEqual(plan["argv"][-len(extra) :], list(extra))

    def test_fixture_resolves_platform_temporary_directory_alias(self) -> None:
        canonical = self.home.parent / "canonical-temp"
        canonical.mkdir(mode=0o700)
        alias = self.home.parent / "temporary-alias"
        alias.symlink_to(canonical, target_is_directory=True)
        original = tempfile.TemporaryDirectory

        def temporary(*args, **kwargs):
            return original(*args, dir=alias, **kwargs)

        result = unittest.TestResult()
        with patch.object(tempfile, "TemporaryDirectory", side_effect=temporary):
            case = ProjectAdapterTests(
                "test_pi_keeps_established_home_resource_selection"
            )
            case.run(result)
        self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))

    def test_pi_keeps_established_home_resource_selection(self) -> None:
        plan = prepare_launch(self.home, "pi", self.project, extra=("--no-session",))
        self.assertEqual(plan["cwd"], str(self.project))
        self.assertEqual(plan["argv"][0], "pi")
        self.assertIn(str(self.home / ".pi" / "APPEND_SYSTEM.md"), plan["argv"])
        self.assertIn(str(self.home / "AGENTS.md"), plan["argv"])
        self.assertIn(
            ("--skill", str(self.skills / "sample")),
            list(zip(plan["argv"], plan["argv"][1:])),
        )
        self.assertEqual(plan["argv"][-1], "--no-session")
        self.assertEqual(plan["env"], {})

    def test_prepare_launch_rejects_invalid_home_before_native_plan(self) -> None:
        invalid = self.project.parent / "not-a-home"
        invalid.mkdir()
        with self.assertRaises(core.HomeError):
            prepare_launch(invalid, "claude", self.project)


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path

from soulsteads import core
from soulsteads.project_adapters.resources import ResourceLaunch


class ProjectLaunchTests(unittest.TestCase):
    def setUp(self):
        old_umask = os.umask(0o077)
        self.addCleanup(os.umask, old_umask)
        self.tmp = tempfile.TemporaryDirectory(prefix="soulsteads-launch-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.home = core.create("identity", "pi", path=root / "home-a")
        (self.home / "AGENTS.md").write_text("HOME A operating instructions\n")
        skill = self.home / "skills" / "home-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: home-skill\ndescription: Home skill\n---\nFollow Home A skill.\n"
        )
        self.project = root / "project-b"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("PROJECT B operating instructions\n")

    def test_pi_selects_home_resources_and_runs_in_project_directory(self):
        from soulsteads.launch import prepare_launch

        plan = prepare_launch(self.home, "pi", self.project, extra=("--no-session",))

        self.assertEqual(plan["cwd"], str(self.project))
        self.assertEqual(plan["argv"][0], "pi")
        self.assertEqual(plan["argv"].count("--append-system-prompt"), 2)
        assert isinstance(plan, ResourceLaunch)
        self.addCleanup(plan.close)
        resources = Path(plan["argv"][2]).parents[1]
        self.assertFalse(resources.is_relative_to(self.home))
        self.assertEqual(
            Path(plan["argv"][2]).read_bytes(),
            (self.home / ".pi/APPEND_SYSTEM.md").read_bytes(),
        )
        self.assertEqual(
            Path(plan["argv"][4]).read_bytes(), (self.home / "AGENTS.md").read_bytes()
        )
        self.assertIn(
            ("--skill", str(resources / "skills/home-skill")),
            list(zip(plan["argv"], plan["argv"][1:])),
        )
        self.assertNotIn(str(self.project / "AGENTS.md"), plan["argv"])
        self.assertEqual(plan["argv"][-1], "--no-session")
        self.assertEqual(plan["env"], {})

    def test_codex_uses_native_project_root(self):
        from soulsteads.launch import prepare_launch

        plan = prepare_launch(
            self.home, "codex", self.project, allow_context_in_argv=True
        )

        self.assertEqual(plan["cwd"], str(self.project))
        self.assertEqual(plan["argv"][:3], ["codex", "--cd", str(self.project)])
        override = plan["argv"][plan["argv"].index("--config") + 1]
        self.assertIn("HOME A operating instructions", override)
        self.assertIn("Follow Home A skill", override)
        self.assertEqual(plan["env"], {})


if __name__ == "__main__":
    unittest.main()

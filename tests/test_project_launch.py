import os
import tempfile
import unittest
from pathlib import Path

from soulsteads import core


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
        self.assertIn(str(self.home / ".pi/APPEND_SYSTEM.md"), plan["argv"])
        self.assertIn(str(self.home / "AGENTS.md"), plan["argv"])
        self.assertIn(
            ("--skill", str(self.home / "skills/home-skill")),
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

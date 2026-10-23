import tempfile
import unittest
from pathlib import Path

from soulsteads import core


class ProjectLaunchTests(unittest.TestCase):
    def setUp(self):
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

    def test_codex_is_rejected_until_native_home_skills_are_selectable(self):
        from soulsteads.launch import prepare_launch

        with self.assertRaisesRegex(
            core.HomeError, "native Home A AGENTS.md and skills"
        ):
            prepare_launch(self.home, "codex", self.project)


if __name__ == "__main__":
    unittest.main()

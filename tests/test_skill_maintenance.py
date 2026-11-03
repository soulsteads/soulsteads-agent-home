import difflib
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from soulsteads import core, templates


class SkillMaintenanceTemplateTests(unittest.TestCase):
    def test_exports_a_portable_skill_maintenance_skill(self):
        content = getattr(templates, "SKILL_MAINTENANCE", "")
        self.assertTrue(content, "templates must export SKILL_MAINTENANCE")
        self.assertTrue(content.startswith("---\n"))
        self.assertIn("\n---\n", content)
        frontmatter, _, body = content[4:].partition("\n---\n")
        self.assertRegex(frontmatter, r"(?m)^name: skill-maintenance$")
        description = re.search(r"(?m)^description: (.+)$", frontmatter)
        if description is None:
            self.fail("portable skill frontmatter must include a description")
        description_text = description.group(1)
        self.assertTrue(description_text.startswith("Use when "))
        self.assertLessEqual(len(description_text), 1024)
        self.assertTrue(body.strip())
        self.assertIn("# ", body)

    def test_teaches_harness_native_skill_lookup_and_tooling(self):
        content = " ".join(getattr(templates, "SKILL_MAINTENANCE", "").lower().split())
        for required in (
            "canonical `skills/`",
            "native file and shell tools",
            "tool names vary",
            "hermes-specific",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_proposes_focused_skill_changes_without_assuming_authority(self):
        content = " ".join(getattr(templates, "SKILL_MAINTENANCE", "").lower().split())
        for required in (
            "user correction",
            "nontrivial work",
            "propose",
            "explicit user authorization",
            "preapproved scope",
            "identity",
            "security",
            "permissions",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_validates_and_reports_authorized_changes_without_automation(self):
        content = " ".join(getattr(templates, "SKILL_MAINTENANCE", "").lower().split())
        for required in (
            "validate",
            "report",
            "commit only",
            "authorized",
            "plugins",
            "schedules",
            "install",
            "credentials",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_defines_review_modes_and_separates_learning_artifacts(self):
        content = " ".join(getattr(templates, "SKILL_MAINTENANCE", "").lower().split())
        for required in (
            "off",
            "propose",
            "scoped-apply",
            "propose is the default",
            "explicit user authorization",
            "narrowly preapproved",
            "facts and preferences",
            "reusable procedures",
            "task checkpoints",
            "service-owned memories",
            "competing writer",
            "soul.md",
            "permissions",
            "credentials",
            "plugins",
            "schedules",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_provides_small_remember_correct_learn_and_handoff_workflows(self):
        content = " ".join(getattr(templates, "SKILL_MAINTENANCE", "").lower().split())
        for required in (
            "remember",
            "correct",
            "learn",
            "handoff",
            "evidence",
            "propose the smallest",
            "reviewable diff",
            "validate",
            "report",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_correction_and_procedure_example_stays_in_a_disposable_home(self):
        """Deterministic fixture validation; this does not model agent behavior."""
        with TemporaryDirectory(prefix="skill-learning-") as temporary_home:
            home = core.create(
                "learning", "pi", path=Path(temporary_home).resolve() / "home"
            )
            memory_path = home / "MEMORY.md"
            skill_path = home / "skills" / "focused" / "SKILL.md"
            skill_path.parent.mkdir()
            before_memory = "# Memory\n\n## Preferences\n- Concise updates.\n\n## Facts\n- Project uses Python.\n"
            before_skill = "---\nname: focused\ndescription: Use when handing off a validated task.\n---\n\n# Handoff\n\n1. Send a status update.\n"
            memory_path.write_text(before_memory, encoding="utf-8")
            skill_path.write_text(before_skill, encoding="utf-8")

            memory_path.write_text(
                before_memory.replace(
                    "Concise updates.", "Concise updates with validation results."
                ),
                encoding="utf-8",
            )
            skill_path.write_text(
                before_skill.replace(
                    "1. Send a status update.",
                    "1. Validate the result.\n2. Send a status update with evidence.",
                ),
                encoding="utf-8",
            )
            memory_diff = "".join(
                difflib.unified_diff(
                    before_memory.splitlines(keepends=True),
                    memory_path.read_text(encoding="utf-8").splitlines(keepends=True),
                    fromfile="a/MEMORY.md",
                    tofile="b/MEMORY.md",
                )
            )
            skill_diff = "".join(
                difflib.unified_diff(
                    before_skill.splitlines(keepends=True),
                    skill_path.read_text(encoding="utf-8").splitlines(keepends=True),
                    fromfile="a/skills/focused/SKILL.md",
                    tofile="b/skills/focused/SKILL.md",
                )
            )

            self.assertIn("- Concise updates.", memory_diff)
            self.assertIn("+1. Validate the result.", skill_diff)
            self.assertNotIn("+ Project uses Python.", memory_diff)
            self.assertTrue(
                memory_path.read_text(encoding="utf-8").startswith("# Memory\n")
            )
            validated_home = core.create(
                "validation", "pi", path=Path(temporary_home).resolve() / "validation"
            )
            installed = core.install_skill(validated_home, skill_path.parent)
            self.assertEqual(
                (installed / "SKILL.md").read_text(), skill_path.read_text()
            )
            core.commit(home, "Apply explicitly authorized synthetic learning fixture")
            skill_path.write_text(before_skill, encoding="utf-8")
            core.commit(
                home, "Undo authorized procedural change without resetting history"
            )
            self.assertEqual(skill_path.read_text(), before_skill)

    def test_rollback_keeps_authority_and_history_boundaries(self):
        content = " ".join(templates.SKILL_MAINTENANCE.lower().split())
        self.assertIn("rollback", content)
        self.assertIn("reset history", content)


class AgentInstructionsTemplateTests(unittest.TestCase):
    def test_distinguishes_task_location_from_the_agent_home(self):
        content = " ".join(templates.DOCUMENTS["AGENTS.md"].lower().split())
        for required in (
            "task's current working directory",
            "workspace/",
            "identity",
            "privacy",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_describes_curated_memory_separately_from_optional_hindsight(self):
        content = " ".join(templates.DOCUMENTS["AGENTS.md"].lower().split())
        self.assertIn("curated", content)
        self.assertIn("memory.md", content)
        self.assertIn("hindsight", content)
        self.assertIn("if configured", content)
        self.assertIn("separate", content)

    def test_prioritizes_relevant_skills_and_native_harness_tools(self):
        content = " ".join(templates.DOCUMENTS["AGENTS.md"].lower().split())
        for required in (
            "relevant skills",
            "before",
            "native file and shell tools",
            "tool names vary",
            "hermes-specific",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_self_improvement_is_proposed_by_default(self):
        content = " ".join(templates.DOCUMENTS["AGENTS.md"].lower().split())
        self.assertIn("self-improvement", content)
        self.assertIn("propose", content)
        self.assertIn("default", content)
        self.assertIn("explicit user authority", content)


if __name__ == "__main__":
    unittest.main()

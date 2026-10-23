"""Black-box safety regressions; every home is disposable."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = core.create("helper", "opencode", path=self.root / "home")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.home), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_identity_instructions_and_useful_original_starter(self):
        instructions = (self.home / "AGENTS.md").read_text()
        for name in ("SOUL.md", "USER.md", "MEMORY.md"):
            self.assertIn(name, instructions)
        self.assertIn(
            "verify", (self.home / "skills/starter/SKILL.md").read_text().lower()
        )

    def test_no_skills_still_has_install_destination(self):
        home = core.create(
            "empty", "claude", path=self.root / "empty", with_skills=False
        )
        self.assertTrue((home / "skills").is_dir())
        self.assertEqual([p.name for p in (home / "skills").iterdir()], [".gitkeep"])

    def test_secret_variants_cannot_be_committed_even_if_force_staged(self):
        skill = self.home / "skills/starter/.env.local"
        skill.write_text("TEST_ONLY=not-a-real-secret\n")
        self.git("add", "-f", "--", str(skill))
        (self.home / "USER.md").write_text("Changed user\n")
        with self.assertRaises(core.HomeError):
            core.commit(self.home, "Must refuse unsafe index")
        self.assertNotIn(".env.local", self.git("ls-tree", "-r", "--name-only", "HEAD"))

    def test_nested_git_is_refused_at_immediate_parent(self):
        with self.assertRaises(core.HomeError):
            core.create("nested", "opencode", path=self.home / "nested")

    def test_configuration_is_committable_and_round_trips(self):
        old = self.git("rev-parse", "HEAD")
        persona = (self.home / "SOUL.md").read_text()
        core.configure(self.home, "claude")
        self.assertEqual((self.home / "SOUL.md").read_text(), persona)
        self.assertTrue((self.home / "opencode.json").exists())
        core.commit(self.home, "Switch runtime")
        self.assertEqual(self.git("status", "--porcelain"), "")
        core.revert(self.home, old)
        self.assertEqual(core.load(self.home)["runtime"], "opencode")
        self.assertTrue((self.home / ".agents/skills").is_symlink())

    def test_ignored_secrets_and_workspace_survive_restore(self):
        old = self.git("rev-parse", "HEAD")
        (self.home / ".env").write_text("TEST_ONLY=not-a-real-secret\n")
        (self.home / "workspace/output.txt").write_text("Keep task output\n")
        (self.home / "MEMORY.md").write_text("Remember a generic fact\n")
        core.commit(self.home, "Remember")
        core.revert(self.home, old)
        self.assertIn("TEST_ONLY", (self.home / ".env").read_text())
        self.assertEqual(
            (self.home / "workspace/output.txt").read_text(), "Keep task output\n"
        )

    def test_git_environment_cannot_redirect_commit(self):
        outside = self.root / "outside"
        outside.mkdir()
        subprocess.run(["git", "init", "-q", str(outside)], check=True)
        (self.home / "USER.md").write_text("Changed user\n")
        with patch.dict(
            os.environ,
            {"GIT_DIR": str(outside / ".git"), "GIT_WORK_TREE": str(outside)},
        ):
            core.commit(self.home, "Local only")
        self.assertIn("Local only", core.history(self.home))
        self.assertFalse((outside / "USER.md").exists())

    def test_untrusted_links_are_rejected_without_changing_target(self):
        sentinel = self.root / "sentinel"
        sentinel.write_text("untouched")
        (self.home / "skills/bad").symlink_to(sentinel)
        with self.assertRaises(core.HomeError):
            core.commit(self.home, "No links")
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_customized_runtime_config_is_not_removed(self):
        (self.home / "opencode.json").write_text('{"custom": true}\n')
        core.commit(self.home, "Customize")
        core.configure(self.home, "codex")
        self.assertEqual(core.load(self.home)["runtime"], "codex")
        self.assertEqual(
            (self.home / "opencode.json").read_text(), '{"custom": true}\n'
        )

    def test_filenames_with_spaces_are_tracked_and_restored(self):
        extra = self.home / "skills/starter/a reference.md"
        extra.write_text("Reference one\n")
        core.commit(self.home, "Add spaced file")
        first = self.git("rev-parse", "HEAD")
        extra.write_text("Reference two\n")
        core.commit(self.home, "Edit spaced file")
        core.revert(self.home, first)
        self.assertEqual(extra.read_text(), "Reference one\n")

    def test_revert_rejects_hardlinked_worktree_file_without_mutating_external_target(
        self,
    ):
        initial = self.git("rev-parse", "HEAD")
        user = self.home / "USER.md"
        user.write_text("Changed user\n")
        core.commit(self.home, "Change user")
        external = self.root / "external-user.md"
        os.link(user, external)

        with self.assertRaises(core.HomeError):
            core.revert(self.home, initial)

        self.assertEqual(external.read_text(), "Changed user\n")
        self.assertEqual(user.read_text(), "Changed user\n")

    def test_home_without_starter_is_portable_through_local_git_clone(self):
        source = core.create(
            "empty", "codex", path=self.root / "empty", with_skills=False
        )
        clone = self.root / "copy"
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(source), str(clone)],
            check=True,
        )
        self.assertEqual(core.load(clone)["runtime"], "codex")
        self.assertTrue((clone / "skills").is_dir())

    def test_manifest_cannot_select_arbitrary_program(self):
        import json

        manifest = self.home / "soulsteads.json"
        value = json.loads(manifest.read_text())
        value["runtime"] = "/bin/sh"
        manifest.write_text(json.dumps(value))
        with self.assertRaises(core.HomeError):
            core.load(self.home)


if __name__ == "__main__":
    unittest.main()

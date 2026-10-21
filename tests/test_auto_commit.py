"""Automatic commit messages use metadata, never agent contents."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from soulsteads.core import HomeError, commit, create


class AutomaticCommitTests(unittest.TestCase):
    def git(self, home, *args):
        return subprocess.check_output(
            ["git", "-C", str(home), *args], text=True
        ).strip()

    def test_default_api_message_counts_added_modified_and_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = create("helper", "opencode", base=Path(tmp) / "agents")
            (home / "USER.md").write_text("Synthetic private contents\n")
            (home / "MEMORY.md").unlink()
            skill = home / "skills" / "example"
            skill.mkdir()
            (skill / "SKILL.md").write_text("Synthetic skill\n")
            revision = commit(home)
            self.assertEqual(revision, self.git(home, "rev-parse", "HEAD"))
            self.assertEqual(
                self.git(home, "log", "-1", "--format=%B"),
                "Update agent home (3 files)",
            )

    def test_no_changes_does_not_create_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = create("helper", "opencode", base=Path(tmp) / "agents")
            before = self.git(home, "rev-parse", "HEAD")
            with self.assertRaises(HomeError):
                commit(home)
            self.assertEqual(self.git(home, "rev-parse", "HEAD"), before)

    def test_unsafe_staged_file_still_rejected_without_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = create("helper", "opencode", base=Path(tmp) / "agents")
            before = self.git(home, "rev-parse", "HEAD")
            (home / ".env").write_text("SYNTHETIC_SECRET=never-stage\n")
            self.git(home, "add", "-f", ".env")
            with self.assertRaisesRegex(HomeError, "unsafe paths"):
                commit(home)
            self.assertEqual(self.git(home, "rev-parse", "HEAD"), before)

    def test_explicit_message_preserved_and_blank_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = create("helper", "opencode", base=Path(tmp) / "agents")
            (home / "USER.md").write_text("Synthetic update\n")
            before = self.git(home, "rev-parse", "HEAD")
            with self.assertRaises(HomeError):
                commit(home, "  ")
            self.assertEqual(self.git(home, "rev-parse", "HEAD"), before)
            message = "Personalize helper\n\nKeep this explicit body."
            commit(home, message)
            self.assertEqual(self.git(home, "log", "-1", "--format=%B"), message)

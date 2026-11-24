"""Explicit workspace versioning uses the existing local Home history."""

import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core
from soulsteads.verification import verify_home


class WorkspaceTrackingTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name).resolve()
        self.home = core.create("helper", "pi", path=self.root / "home")

    def git(self, *args):
        return core._git(self.home, *args).stdout

    def write(self, path, text="Synthetic workspace output\n"):
        target = self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def test_commit_opt_in_is_per_path_and_identity_restore_leaves_it_alone(self):
        chosen = "workspace/reports/report [1].md"
        other = "workspace/reports/report 1.md"
        tracked = self.write(chosen)
        self.write(other)
        self.write("USER.md", "A generic correction\n")
        core.commit(self.home, "Update identity only")
        self.assertNotIn(chosen, self.git("ls-tree", "-r", "--name-only", "HEAD"))

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = cli.main(["commit", str(self.home), "--workspace-file", chosen])
        self.assertEqual(result, 0)
        first = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(self.git("show", f"HEAD:{chosen}"), tracked.read_text())
        self.assertNotIn(other, self.git("ls-tree", "-r", "--name-only", "HEAD"))

        tracked.write_text("Second version\n")
        self.write("USER.md", "Another generic correction\n")
        core.commit(self.home, "No workspace changes without an explicit path")
        self.assertNotEqual(self.git("show", f"HEAD:{chosen}"), tracked.read_text())
        core.commit(self.home, "Version the workspace change", workspace_files=[chosen])
        story = self.git("rev-parse", "HEAD").strip()
        core.revert(self.home, first)
        self.assertNotEqual(self.git("rev-parse", "HEAD").strip(), first)
        self.assertNotEqual(self.git("rev-parse", "HEAD").strip(), story)
        self.assertEqual((self.home / "USER.md").read_text(), "A generic correction\n")
        self.assertEqual(tracked.read_text(), "Second version\n")
        self.assertEqual(self.git("show", f"HEAD:{chosen}"), "Second version\n")
        self.assertEqual((self.home / other).read_text(), "Synthetic workspace output\n")

    def test_unchanged_commit_reports_no_changes_instead_of_unsafe_index(self):
        name = "workspace/report.md"
        self.write(name)
        revision = core.commit(self.home, workspace_files=[name])

        for options in ([], ["--workspace-file", name]):
            with self.subTest(options=options):
                with (
                    redirect_stdout(io.StringIO()) as stdout,
                    redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = cli.main(["commit", str(self.home), *options])
                self.assertEqual(result, 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "soulsteads: no changes to commit\n")
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), revision)
                self.assertEqual(self.git("status", "--porcelain"), "")

    def test_protected_or_invalid_selection_does_not_stage_companion_file(self):
        good = "workspace/report.md"
        self.write(good)
        self.write("workspace/.env.local")
        self.write("workspace/.runtime/run.json")
        self.write("workspace/sessions/transcript.jsonl")
        outside = self.root / "outside.md"
        outside.write_text("Foreign file\n")
        os.link(outside, self.home / "workspace/linked.md")
        initial = self.git("rev-parse", "HEAD")
        index = (self.home / ".git/index").read_bytes()
        for bad in (
            "workspace", "workspace/", "workspace/../USER.md", "workspace//report.md",
            "workspace/./report.md", "workspace/absent.md", "workspace/.env.local",
            "workspace/.runtime/run.json", "workspace/sessions/transcript.jsonl",
            "workspace/linked.md", "USER.md", "./workspace/report.md", str(outside),
        ):
            with self.subTest(path=bad), self.assertRaises(core.HomeError):
                core.commit(self.home, workspace_files=[good, bad])
        self.assertEqual(self.git("rev-parse", "HEAD"), initial)
        self.assertEqual((self.home / ".git/index").read_bytes(), index)

    def test_unselected_force_staged_file_refuses_even_when_others_are_selected(self):
        self.write("workspace/first.md")
        self.write("workspace/second.md")
        self.git("add", "-f", "--", "workspace/second.md")
        before = (self.home / ".git/index").read_bytes()
        with self.assertRaisesRegex(core.HomeError, "index contains unsafe paths"):
            core.commit(self.home, workspace_files=["workspace/first.md"])
        self.assertEqual((self.home / ".git/index").read_bytes(), before)

    def test_opted_in_tracked_file_can_be_deleted_and_recovered_with_git(self):
        name = "workspace/notes.md"
        tracked = self.write(name)
        first = core.commit(self.home, workspace_files=[name])
        tracked.unlink()
        deletion = core.commit(self.home, workspace_files=[name])
        self.assertNotEqual(first, deletion)
        self.assertNotIn(name, self.git("ls-tree", "-r", "--name-only", "HEAD"))
        self.git("restore", f"--source={first}", "--", name)
        self.assertEqual(tracked.read_text(), "Synthetic workspace output\n")

    def test_multiple_workspace_paths_store_exact_bytes_for_git_restore(self):
        names = ["workspace/report.txt", "workspace/data.bin"]
        paths = [self.write(name) for name in names]
        original = [b"One\r\nTwo\r\n", b"\x00\xff\r\n"]
        for path, data in zip(paths, original):
            path.write_bytes(data)
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(cli.main([
                "commit", str(self.home), "--workspace-file", names[0],
                "--workspace-file", names[1],
            ]), 0)
        revision = stdout.getvalue().strip()
        for path in paths:
            path.write_bytes(b"New contents\r\n")
        core.commit(self.home, workspace_files=names)
        self.git("restore", f"--source={revision}", "--", *names)
        self.assertEqual([path.read_bytes() for path in paths], original)

    def test_restore_refuses_to_overwrite_ignored_output_at_historical_path(self):
        name = "workspace/report.md"
        tracked = self.write(name)
        first = core.commit(self.home, workspace_files=[name])
        tracked.unlink()
        deletion = core.commit(self.home, workspace_files=[name])
        tracked.write_text("New, untracked output\n")
        with self.assertRaisesRegex(core.HomeError, "no managed Home changes"):
            core.revert(self.home, first)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), deletion)
        self.assertEqual(tracked.read_text(), "New, untracked output\n")

    def test_nested_repository_files_are_not_added(self):
        name = "workspace/project/report.md"
        target = self.write(name)
        subprocess.run(["git", "init", "-q", str(target.parent)], check=True)
        with self.assertRaisesRegex(core.HomeError, "nested Git repository"):
            core.commit(self.home, workspace_files=[name])
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_restore_does_not_write_inside_a_nested_repository(self):
        name = "workspace/project/report.md"
        target = self.write(name)
        first = core.commit(self.home, workspace_files=[name])
        target.unlink()
        deletion = core.commit(self.home, workspace_files=[name])
        subprocess.run(["git", "init", "-q", str(target.parent)], check=True)
        with self.assertRaisesRegex(core.HomeError, "no managed Home changes"):
            core.revert(self.home, first)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), deletion)
        self.assertFalse(target.exists())

    def test_file_larger_than_workspace_limit_is_refused(self):
        name = "workspace/large.dat"
        target = self.write(name)
        with target.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(core.HomeError, "64 MiB"):
            core.commit(self.home, workspace_files=[name])
        self.assertNotIn(name, self.git("ls-files", "--cached"))

    def test_workspace_path_checks_also_apply_during_verification(self):
        name = "workspace/report.md"
        self.write(name)
        core.commit(self.home, workspace_files=[name])

        def private_status():
            return next(
                item["status"] for item in verify_home(self.home)["findings"]
                if item["id"] == "private-storage"
            )

        self.assertEqual(private_status(), "passed")
        private = "workspace/sessions/state.json"
        self.write(private)
        self.git("add", "-f", "--", private)
        self.assertEqual(private_status(), "failed")

    def test_file_cannot_implicitly_delete_tracked_descendants(self):
        child = "workspace/reports/report.md"
        target = self.write(child)
        initial = core.commit(self.home, workspace_files=[child])
        target.unlink()
        target.parent.rmdir()
        self.write("workspace/reports")
        index = (self.home / ".git/index").read_bytes()
        with self.assertRaisesRegex(core.HomeError, "record deletions first"):
            core.commit(self.home, workspace_files=["workspace/reports"])
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), initial)
        self.assertEqual((self.home / ".git/index").read_bytes(), index)

    def test_workspace_edit_during_snapshot_is_not_committed(self):
        name = "workspace/report.md"
        report = self.write(name)
        initial = self.git("rev-parse", "HEAD")
        git = core._git_bytes

        def concurrent_edit(home, *args, **options):
            result = git(home, *args, **options)
            if args[0] == "hash-object":
                report.write_text("New version from a concurrent editor\n")
            return result

        with (
            patch.object(core, "_git_bytes", side_effect=concurrent_edit),
            self.assertRaisesRegex(core.HomeError, "workspace selection changed"),
        ):
            core.commit(self.home, workspace_files=[name])
        self.assertEqual(self.git("rev-parse", "HEAD"), initial)
        self.assertNotIn(name, self.git("ls-files", "--cached"))

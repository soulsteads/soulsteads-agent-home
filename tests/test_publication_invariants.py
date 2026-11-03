"""Whole-operation root binding and previously published output checks."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, native_config, publication
from soulsteads.cli import main


class PublicationInvariantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = core.create("original", "pi", path=self.root / "home")

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["config", str(self.home), *args])
        return code, err.getvalue()

    def test_previously_published_output_drift_prevents_whole_operation_success(self):
        (self.home / "SOUL.md").write_text("New canonical source\n")
        original = publication.publish_file
        changed = False

        def drift(parent_fd, name, text, **kwargs):
            nonlocal changed
            result = original(parent_fd, name, text, **kwargs)
            if name == "APPEND_SYSTEM.md":
                (self.home / ".pi/APPEND_SYSTEM.md").write_text(
                    "Changed after per-file verification\n"
                )
                changed = True
            return result

        with patch.object(publication, "publish_file", side_effect=drift):
            code, error = self.invoke("--sync")
        self.assertTrue(changed)
        self.assertEqual(
            code,
            1,
            "already-published output drift must not be exempted from final verification",
        )
        self.assertIn("partially applied", error)

    def test_replaced_published_hardlink_is_rejected_before_reading_external_bytes(
        self,
    ):
        (self.home / "SOUL.md").write_text("New canonical source\n")
        outside = self.root / "outside"
        outside.write_text("External private canary\n")
        outside_inode = outside.stat().st_ino
        original = publication.publish_file
        original_read = os.read
        reads = []

        def replace_after_publish(parent_fd, name, text, **kwargs):
            result = original(parent_fd, name, text, **kwargs)
            if name == "APPEND_SYSTEM.md":
                leaf = self.home / ".pi/APPEND_SYSTEM.md"
                leaf.unlink()
                os.link(outside, leaf)
            return result

        def observe_read(fd, count):
            if os.fstat(fd).st_ino == outside_inode:
                reads.append(count)
            return original_read(fd, count)

        with (
            patch.object(
                publication, "publish_file", side_effect=replace_after_publish
            ),
            patch.object(os, "read", side_effect=observe_read),
        ):
            code, _ = self.invoke("--sync")
        self.assertEqual(code, 1)
        self.assertEqual(
            reads, [], "identity/type checks must precede published-output reads"
        )

    def test_missing_posix_lock_support_is_an_actionable_failure(self):
        with patch.object(publication, "fcntl", None):
            code, error = self.invoke("--sync")
        self.assertEqual(code, 1)
        self.assertIn("POSIX", error)

    def test_failed_staging_removes_only_its_own_temporary_file(self):
        parent = self.root / "stage-failure"
        parent.mkdir(mode=0o700)
        fd = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            with (
                patch.object(
                    publication.os,
                    "write",
                    side_effect=OSError("synthetic staging failure"),
                ),
                self.assertRaises(OSError),
            ):
                publication.publish_file(fd, "new-output", "intended")
        finally:
            os.close(fd)
        self.assertEqual(list(parent.iterdir()), [])

    def test_lock_open_cannot_block_on_a_special_file(self):
        original = os.open

        def checked(path, flags, *args, **kwargs):
            if path == "soulsteads-publication.lock":
                self.assertTrue(
                    flags & os.O_NONBLOCK,
                    "reject special lock files without blocking before fstat",
                )
            return original(path, flags, *args, **kwargs)

        with patch.object(publication.os, "open", side_effect=checked):
            self.assertEqual(self.invoke("--sync")[0], 0)

    def test_final_boundary_failure_reports_partial_application(self):
        (self.home / "SOUL.md").write_text("New canonical source\n")
        original_publish = publication.publish_file
        original_verify = native_config._verify_for_publish
        final_published = False
        checks_after_final = 0

        def record(parent_fd, name, text, **kwargs):
            nonlocal final_published
            result = original_publish(parent_fd, name, text, **kwargs)
            final_published |= name == "soulsteads.json"
            return result

        def final_fault(*args, **kwargs):
            nonlocal checks_after_final
            original_verify(*args, **kwargs)
            if final_published:
                checks_after_final += 1
                if checks_after_final == 2:
                    raise core.HomeError("synthetic final verification failure")

        with (
            patch.object(publication, "publish_file", side_effect=record),
            patch.object(native_config, "_verify_for_publish", side_effect=final_fault),
        ):
            code, error = self.invoke("--sync")
        self.assertEqual(checks_after_final, 2)
        self.assertEqual(code, 1)
        self.assertIn("partially applied", error)

    def test_lock_admission_rebind_to_another_regular_home_never_changes_that_home(
        self,
    ):
        other = core.create("other", "pi", path=self.root / "other")
        before = {
            p.relative_to(other): p.read_bytes()
            for p in other.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        original_lock = publication.cooperative_lock
        changed = False

        @contextlib.contextmanager
        def rebind(root_fd):
            nonlocal changed
            with original_lock(root_fd):
                self.home.rename(self.root / "retained")
                other.rename(self.home)
                changed = True
                yield

        with patch.object(publication, "cooperative_lock", rebind):
            code, _ = self.invoke(
                "--hindsight-url", "https://fixture.example/mcp/synthetic/"
            )
        self.assertTrue(changed)
        self.assertEqual(
            code, 1, "the locked Home and admitted Home must remain the same binding"
        )
        after = {
            p.relative_to(self.home): p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        self.assertEqual(
            before,
            after,
            "a replacement Home must not be read as publication authority or modified",
        )

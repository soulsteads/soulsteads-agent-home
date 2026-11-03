"""Publication kernel regressions for bytes, partial failure, and cooperation."""

import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, native_config, publication


def _lock_child(root, ready, acquired):
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        ready.set()
        with publication.cooperative_lock(descriptor):
            acquired.set()
    finally:
        os.close(descriptor)


class PublicationKernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = core.create("publication-test", "opencode", path=self.root / "home")

    def test_output_bytes_are_checked_after_publication(self):
        target = self.root / "target"
        target.write_text("before")
        parent_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        expected = publication._identity(
            os.stat("target", dir_fd=parent_fd, follow_symlinks=False)
        )
        original_open = os.open
        altered = False

        def mutate_before_verification(path, flags, *args, **kwargs):
            nonlocal altered
            if path == "target" and kwargs.get("dir_fd") == parent_fd:
                altered = True
                writer = original_open(path, os.O_WRONLY | os.O_TRUNC, dir_fd=parent_fd)
                try:
                    os.write(writer, b"changed-after-publication")
                finally:
                    os.close(writer)
            return original_open(path, flags, *args, **kwargs)

        try:
            with patch(
                "soulsteads.publication.os.open", side_effect=mutate_before_verification
            ), self.assertRaises(core.HomeError):
                publication.publish_file(
                    parent_fd, "target", "intended", expected=expected
                )
        finally:
            os.close(parent_fd)
        self.assertTrue(altered, "output verification must inspect the published leaf")

    def test_fresh_home_native_files_use_checked_publication(self):
        original_publish = publication.publish_file
        seen = []

        def record(parent_fd, name, text, **kwargs):
            seen.append(name)
            return original_publish(parent_fd, name, text, **kwargs)

        fresh = self.root / "fresh-home"
        with patch.object(publication, "publish_file", side_effect=record):
            core.create("fresh-publication", "opencode", path=fresh)
        self.assertIn("config.toml", seen)
        self.assertIn("soulsteads.json", seen)
        self.assertIn("APPEND_SYSTEM.md", seen)

    def test_partial_failure_reports_exact_applied_and_remaining_paths(self):
        original_publish = publication.publish_file
        count = 0

        def fail_second(parent_fd, name, text, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise core.HomeError("injected publication failure")
            return original_publish(parent_fd, name, text, **kwargs)

        with (
            patch.object(publication, "publish_file", side_effect=fail_second),
            self.assertRaisesRegex(
                core.HomeError,
                r"applied=\['opencode.json'\].*remaining=\['.pi/mcp.json'",
            ),
        ):
            native_config.sync(
                self.home,
                hindsight={
                    "url": "https://memory.example/mcp/publication-test/",
                    "token_env": "TEST_TOKEN",
                },
            )

    def test_cooperating_process_waits_on_persistent_lock_inode(self):
        descriptor = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        acquired = context.Event()
        with publication.cooperative_lock(descriptor):
            child = context.Process(
                target=_lock_child, args=(str(self.home), ready, acquired)
            )
            child.start()
            self.assertTrue(ready.wait(5))
            self.assertFalse(acquired.wait(0.2), "second publisher must block on flock")
        self.assertTrue(
            acquired.wait(5), "second publisher should proceed after lock release"
        )
        child.join(5)
        os.close(descriptor)
        self.assertEqual(child.exitcode, 0)
        lock_path = self.home / ".git/soulsteads-publication.lock"
        inode = lock_path.stat().st_ino
        descriptor = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with publication.cooperative_lock(descriptor):
                pass
        finally:
            os.close(descriptor)
        self.assertEqual(
            lock_path.stat().st_ino,
            inode,
            "cooperative lock inode must not be replaced",
        )

    def test_unsafe_hardlinked_lock_is_rejected(self):
        lock = self.home / ".git/soulsteads-publication.lock"
        lock.write_bytes(b"")
        os.link(lock, self.root / "lock-alias")
        descriptor = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with self.assertRaisesRegex(
                core.HomeError, "unsafe cooperative publication lock"
            ), publication.cooperative_lock(descriptor):
                pass
        finally:
            os.close(descriptor)


if __name__ == "__main__":
    unittest.main()

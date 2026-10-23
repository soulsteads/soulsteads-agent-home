"""CLI-level race probes for native-file publication (investigation only)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core
from soulsteads.cli import main

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class PublicationCLIRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = core.create("helper", "claude", path=self.root / "home")

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(["config", str(self.home), *args])
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_absent_mcp_leaf_appearing_before_replace_is_not_clobbered(self):
        self.assertEqual(
            self.invoke("--hindsight-url", "https://memory.example/mcp/helper/")[0],
            0,
        )
        target = self.home / ".mcp.json"
        target.unlink()
        injected = (
            json.dumps(
                {"mcpServers": {"locally-added": {"url": "https://local.example/mcp"}}},
                indent=2,
            )
            + "\n"
        )
        original_link = os.link
        raced = False

        def inject_then_link(src, dst, *args, **kwargs):
            nonlocal raced
            dst_fd = kwargs.get("dst_dir_fd")
            if dst == ".mcp.json" and dst_fd is not None and not raced:
                raced = True
                descriptor = os.open(
                    dst,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=dst_fd,
                )
                try:
                    os.write(descriptor, injected.encode("utf-8"))
                finally:
                    os.close(descriptor)
            return original_link(src, dst, *args, **kwargs)

        with patch("soulsteads.publication.os.link", side_effect=inject_then_link):
            code, _stdout, stderr = self.invoke("--sync")

        self.assertTrue(raced, "probe must inject after absence preflight")
        self.assertEqual(
            target.read_text(encoding="utf-8"),
            injected,
            "publication must not replace a file created after absence preflight",
        )
        self.assertEqual(
            code, 1, f"late unrelated file should abort sync; stderr={stderr!r}"
        )

    def test_runtime_change_does_not_follow_replaced_home_root(self):
        outside = core.create("external", "claude", path=self.root / "outside")
        outside_manifest = outside / "soulsteads.json"
        before = outside_manifest.read_bytes()
        moved = self.root / "moved-home"
        original_open = os.open
        raced = False

        def replace_root_before_temp_open(path, flags, *args, **kwargs):
            nonlocal raced
            if (
                not raced
                and isinstance(path, (str, os.PathLike))
                and Path(path).name.startswith(".soulsteads.json.")
                and Path(path).name.endswith(".tmp")
                and kwargs.get("dir_fd") is not None
            ):
                raced = True
                self.home.rename(moved)
                self.home.symlink_to(outside, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with patch(
            "soulsteads.core.os.open", side_effect=replace_root_before_temp_open
        ):
            code, _stdout, stderr = self.invoke("--runtime", "pi")

        self.assertTrue(raced, "probe must replace the home at temporary-file open")
        self.assertEqual(
            code,
            1,
            f"runtime update through a replaced root must abort; stderr={stderr!r}",
        )
        self.assertEqual(
            outside_manifest.read_bytes(),
            before,
            "runtime-only publication must not overwrite an unrelated home manifest",
        )
        self.assertTrue(self.home.is_symlink())


if __name__ == "__main__":
    unittest.main()

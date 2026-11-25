"""End-to-end Debian package qualification for the repository-local builder."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-deb.sh"
DPKG_DEB = os.environ.get("DPKG_DEB") or shutil.which("dpkg-deb")

with (ROOT / "pyproject.toml").open("rb") as source:
    VERSION = tomllib.load(source)["project"]["version"]


@unittest.skipUnless(shutil.which("uv") and DPKG_DEB, "requires uv and dpkg-deb")
class DebianPackageTests(unittest.TestCase):
    def test_builder_creates_a_self_contained_debian_payload(self):
        self.assertTrue(BUILD.is_file(), "repository-local Debian builder is missing")
        dpkg_deb = DPKG_DEB
        assert dpkg_deb is not None
        with tempfile.TemporaryDirectory(prefix="deb's ") as temporary:
            out_dir = Path(temporary) / "out"
            environment = {**os.environ, "TMPDIR": temporary}
            environment.pop("DPKG_DEB", None)
            result = subprocess.run(
                ["bash", str(BUILD), "--out-dir", str(out_dir)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            packages = list(out_dir.glob(f"soulsteads-agent-home_{VERSION}_all.deb"))
            self.assertEqual(len(packages), 1)
            control = subprocess.check_output([dpkg_deb, "-f", str(packages[0])], text=True)
            self.assertIn("Package: soulsteads-agent-home", control)
            self.assertIn(f"Version: {VERSION}", control)
            self.assertIn("Maintainer: Soulsteads", control.splitlines())
            self.assertIn("Depends: python3 (>= 3.11), git", control)
            self.assertIn("Recommends: python3-yaml, python3-tomlkit, python3-secretstorage", control)
            listing = subprocess.check_output([dpkg_deb, "-c", str(packages[0])], text=True)
            self.assertIn("./usr/bin/soulsteads", listing)
            self.assertIn("./usr/lib/python3/dist-packages/soulsteads/cli.py", listing)
            self.assertIn("./usr/share/doc/soulsteads-agent-home/NOTICE", listing)
            control_dir = Path(temporary) / "control"
            subprocess.check_call([dpkg_deb, "-e", str(packages[0]), str(control_dir)])
            self.assertEqual(sorted(path.name for path in control_dir.iterdir()), ["control"])


class DebianWorkflowTests(unittest.TestCase):
    def test_build_only_workflow_is_pr_and_manual_with_pinned_actions(self):
        workflow = (ROOT / ".github/workflows/deb.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("release:", workflow)
        self.assertIn("scripts/build-deb.sh --out-dir", workflow)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", workflow)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", workflow)


if __name__ == "__main__":
    unittest.main()

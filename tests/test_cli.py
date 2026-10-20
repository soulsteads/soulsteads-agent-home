import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class CLITests(unittest.TestCase):
    def invoke(self, *args, env=None):
        return subprocess.run(
            [sys.executable, "-m", "soulsteads", *args],
            check=False,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_help_lists_supported_operations(self):
        result = self.invoke("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("create", "config", "commit", "revert", "log", "skill", "run"):
            self.assertIn(command, result.stdout)

    def test_create_at_explicit_path_and_show_config(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "an agent"
            result = self.invoke(
                "create", "helper", "--runtime", "opencode", "--path", str(home)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / "SOUL.md").is_file())
            config = self.invoke("config", str(home))
            self.assertEqual(config.returncode, 0, config.stderr)
            self.assertEqual(json.loads(config.stdout)["runtime"], "opencode")

    def test_commit_and_log(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "agent"
            self.assertEqual(
                self.invoke(
                    "create", "helper", "--runtime", "opencode", "--path", str(home)
                ).returncode,
                0,
            )
            (home / "USER.md").write_text("# User\nGeneric test user\n")
            result = self.invoke("commit", str(home), "-m", "Personalize")
            self.assertEqual(result.returncode, 0, result.stderr)
            log = self.invoke("log", str(home))
            self.assertEqual(log.returncode, 0, log.stderr)
            self.assertIn("Personalize", log.stdout)

    def test_restore_cli_creates_new_commit(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "agent"
            self.assertEqual(
                self.invoke(
                    "create", "helper", "--runtime", "opencode", "--path", str(home)
                ).returncode,
                0,
            )
            old = (home / "USER.md").read_text()
            first = self.invoke("log", str(home)).stdout.split()[0]
            (home / "USER.md").write_text("Changed user\n")
            self.assertEqual(
                self.invoke("commit", str(home), "-m", "change").returncode, 0
            )
            result = self.invoke("revert", str(home), first)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((home / "USER.md").read_text(), old)
            self.assertEqual(len(self.invoke("log", str(home)).stdout.splitlines()), 3)

    def test_install_local_skill_cli(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "agent"
            self.assertEqual(
                self.invoke(
                    "create", "helper", "--runtime", "opencode", "--path", str(home)
                ).returncode,
                0,
            )
            source = Path(tmp) / "sample"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: sample\ndescription: A generic test skill\n---\n# Sample\n"
            )
            result = self.invoke("skill", "install", str(home), str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / "skills/sample/SKILL.md").is_file())

    def test_run_dry_run_and_real_process_boundary(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "agent"
            self.assertEqual(
                self.invoke(
                    "create", "helper", "--runtime", "opencode", "--path", str(home)
                ).returncode,
                0,
            )
            result = self.invoke("run", str(home), "--dry-run", "--", "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {"cwd": str(home), "argv": ["opencode", "--help"]},
            )
            binary = Path(tmp) / "opencode"
            binary.write_text(
                f'#!{sys.executable}\nimport os, sys, json\nprint(json.dumps({{"cwd": os.getcwd(), "args": sys.argv[1:]}}))\nsys.exit(7)\n'
            )
            binary.chmod(0o700)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ.get("PATH", ""))
            result = self.invoke("run", str(home), "--", "a prompt; no shell", env=env)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {"cwd": str(home), "args": ["a prompt; no shell"]},
            )


if __name__ == "__main__":
    unittest.main()

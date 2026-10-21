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

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_import_hermes_inspect_apply_and_dry_run(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            source = Path(tmp) / "source"
            source.mkdir(mode=0o700)
            (source / "config.yaml").write_text("{}\n")
            (source / "SOUL.md").write_text("# Synthetic imported identity\n")
            destination = Path(tmp) / "imported"
            arguments = (
                "import-hermes",
                "helper",
                "--source",
                str(source),
                "--profile",
                "default",
                "--runtime",
                "pi",
                "--path",
                str(destination),
            )
            inspected = self.invoke(*arguments)
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout)["status"], "inspected")
            self.assertFalse(destination.exists())
            applied = self.invoke(*arguments, "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(json.loads(applied.stdout)["status"], "imported")
            dry = self.invoke("run", str(destination), "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(json.loads(dry.stdout)["argv"][0], "pi")
            repeated = self.invoke(*arguments, "--apply")
            self.assertEqual(repeated.returncode, 1)
            self.assertNotIn("Traceback", repeated.stderr)

    def test_without_yaml_ordinary_create_works_and_import_is_actionable(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-m",
                    "soulsteads",
                    "create",
                    "plain",
                    "--runtime",
                    "codex",
                    "--path",
                    str(Path(tmp) / "plain"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            missing = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-m",
                    "soulsteads",
                    "import-hermes",
                    "helper",
                    "--source",
                    tmp,
                    "--runtime",
                    "pi",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(missing.returncode, 1, missing.stderr)
            self.assertIn("soulsteads[hermes]", missing.stderr)
            self.assertNotIn("Traceback", missing.stderr)

    def test_named_profile_with_underscore_is_selected_exactly(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            source = Path(tmp) / "source"
            profile = source / "profiles" / "source_profile"
            profile.mkdir(parents=True, mode=0o700)
            profile.parent.chmod(0o700)
            source.chmod(0o700)
            (profile / "config.yaml").write_text("{}\n")
            (profile / "SOUL.md").write_text("Synthetic named profile\n")
            result = self.invoke(
                "import-hermes",
                "helper",
                "--source",
                str(source),
                "--profile",
                "source_profile",
                "--runtime",
                "codex",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["profile"], "source_profile")
            self.assertIn("SOUL.md", report["files"])

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

    def test_commit_without_message_generates_local_summary(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            home = Path(tmp) / "agent"
            created = self.invoke(
                "create", "helper", "--runtime", "opencode", "--path", str(home)
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            (home / "USER.md").write_text("Private synthetic contents\n")
            (home / ".env").write_text("SYNTHETIC_SECRET=never-stage\n")
            result = self.invoke("commit", str(home))
            self.assertEqual(result.returncode, 0, result.stderr)
            subject = subprocess.check_output(
                ["git", "-C", str(home), "log", "-1", "--format=%s"], text=True
            ).strip()
            self.assertEqual(subject, "Update agent home (1 file)")
            self.assertNotIn("Private synthetic", subject)
            changed = subprocess.check_output(
                ["git", "-C", str(home), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
                text=True,
            ).splitlines()
            self.assertEqual(changed, ["USER.md"])

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

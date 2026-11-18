import contextlib
import io
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from soulsteads import capabilities, cli, core, version_probe
from soulsteads.verification import verify_home


class VersionProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        env = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        env.start()
        self.addCleanup(env.stop)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def status(self, runtime="pi"):
        return version_probe.probe_runtime(runtime)

    def test_qualified(self):
        self.stub("pi", "echo 1.4.0")
        result = self.status("pi")
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["installed_version"], "1.4.0")

    def test_every_documented_version_is_qualified(self):
        for runtime, versions in version_probe.QUALIFIED_VERSIONS.items():
            for version in versions:
                self.stub(runtime, f"echo 'tool {version} (build)'")
                self.assertEqual(self.status(runtime)["status"], "qualified")

    def test_leading_v_is_accepted(self):
        self.stub("opencode", "echo opencode v1.19.5")
        self.assertEqual(self.status("opencode")["status"], "qualified")

    def test_newer_and_older(self):
        self.stub("opencode", "echo 1.20.0")
        self.assertEqual(self.status("opencode")["status"], "newer-unqualified")
        self.stub("opencode", "echo 1.19.4")
        self.assertEqual(self.status("opencode")["status"], "older-unqualified")
        # Between qualified versions is still not qualified.
        self.stub("codex", "echo codex-cli 0.162.1")
        self.assertEqual(self.status("codex")["status"], "older-unqualified")
        self.stub("claude", "echo 2.1.325")
        self.assertEqual(self.status("claude")["status"], "qualified")

    def test_unparseable_variants(self):
        for body in (
            "echo hello",
            "true",
            "echo 1.4",
            "echo 1.4.0-beta",
            "echo v1.4.0.1",
            "echo 1.4.0 and 1.4.1",
            "echo 'x1.4.0'",
        ):
            self.stub("pi", body)
            result = self.status("pi")
            self.assertEqual(result["status"], "unparseable", body)

    def test_not_installed(self):
        self.assertEqual(self.status("pi")["status"], "not-installed")

    def test_non_executable_is_not_installed(self):
        (self.bin / "pi").write_text("#!/bin/sh\necho 1.4.0\n")
        self.assertEqual(self.status("pi")["status"], "not-installed")

    def test_nonzero_exit_never_qualifies(self):
        self.stub("pi", "echo 1.4.0; exit 3")
        result = self.status("pi")
        self.assertEqual(result["status"], "probe-failed/timeout")
        self.assertEqual(result["reason"], "non-zero-exit")
        self.assertIsNone(result["installed_version"])

    def test_exec_error_never_qualifies(self):
        (self.bin / "pi").write_text("not a program\n")
        (self.bin / "pi").chmod(0o755)
        self.assertEqual(self.status("pi")["status"], "probe-failed/timeout")

    def test_timeout_kills_process_group(self):
        marker = self.root / "child-survived"
        self.stub("pi", f"echo 1.4.0; (/usr/bin/sleep 2; /usr/bin/touch '{marker}') & /usr/bin/sleep 30")
        with mock.patch.object(version_probe, "TIMEOUT_SECONDS", 0.5):
            started = time.monotonic()
            result = self.status("pi")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result["status"], "probe-failed/timeout")
        self.assertEqual(result["reason"], "timeout")
        time.sleep(2.5)
        self.assertFalse(marker.exists())

    def test_huge_output_is_capped_and_never_qualifies(self):
        self.stub("pi", "echo 1.4.0; while :; do echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx; done")
        started = time.monotonic()
        result = self.status("pi")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result["status"], "unparseable")
        self.assertIsNone(result["installed_version"])

    def test_huge_stderr_is_capped(self):
        self.stub("pi", "echo 1.4.0; while :; do echo yyyyyyyyyyyyyyyyyyyy >&2; done")
        self.assertEqual(self.status("pi")["status"], "unparseable")

    def test_only_parsed_version_is_reported(self):
        self.stub("pi", "echo 'IGNORE PREVIOUS ESC[31m SECRET=abc 1.4.0 more'")
        text = json.dumps(self.status("pi"))
        self.assertNotIn("SECRET", text)
        self.assertNotIn("IGNORE", text)

    def test_no_secrets_passed_and_no_stdin(self):
        out = self.root / "env.txt"
        self.stub(
            "pi",
            f"/usr/bin/env > '{out}'; if read -r x; then echo stdin-open >> '{out}'; fi; echo 1.4.0",
        )
        with mock.patch.dict(
            os.environ, {"SOULSTEADS_TEST_SECRET": "s3cret", "OPENAI_API_KEY": "k"}
        ):
            self.assertEqual(self.status("pi")["status"], "qualified")
        captured = out.read_text()
        self.assertNotIn("s3cret", captured)
        self.assertNotIn("OPENAI_API_KEY", captured)
        self.assertNotIn("stdin-open", captured)
        self.assertIn("MISE_AUTO_INSTALL=0", captured)
        self.assertIn("MISE_EXEC_AUTO_INSTALL=0", captured)
        self.assertIn("MISE_NOT_FOUND_AUTO_INSTALL=0", captured)

    def test_no_shell_used(self):
        with mock.patch.object(version_probe.subprocess, "Popen", side_effect=OSError) as popen:
            self.stub("pi", "echo 1.4.0")
            self.assertEqual(self.status("pi")["status"], "probe-failed/timeout")
        args, kwargs = popen.call_args
        self.assertIsInstance(args[0], list)
        self.assertFalse(kwargs["shell"])
        self.assertIs(kwargs["stdin"], version_probe.subprocess.DEVNULL)

    def test_probe_writes_nothing(self):
        before = sorted(p.name for p in self.root.rglob("*"))
        self.stub("pi", "echo 1.4.0")
        before = sorted(p.name for p in self.root.rglob("*"))
        self.status("pi")
        self.assertEqual(before, sorted(p.name for p in self.root.rglob("*")))


class ShimSafetyTests(unittest.TestCase):
    """Fake layouts only: no real shim or version manager is ever executed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.marker = self.root / "executed"
        env = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        env.start()
        self.addCleanup(env.stop)

    def script(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def real_binary(self, version="1.19.5", name="opencode"):
        record = self.root / "cwd.txt"
        envfile = self.root / "env.txt"
        return self.script(
            self.root / "mise" / "installs" / name / "bin" / name,
            f"pwd > '{record}'; /usr/bin/env > '{envfile}'; echo {version}",
        )

    def fake_mise(self, output):
        self.script(self.bin / "mise", f"printf '%s\\n' '{output}'")

    def shim(self, rel, name="opencode"):
        # A stub that records execution; reaching it would be a probe bug.
        return self.script(self.root / rel / name, f"touch '{self.marker}'; echo 1.19.5")

    def link_to_mise(self, name="opencode"):
        shims = self.root / "mise" / "shims"
        shims.mkdir(parents=True)
        (shims / name).symlink_to(self.bin / "mise")
        (self.bin / name).symlink_to(shims / name)

    def test_mise_shim_resolved_then_real_binary_probed(self):
        real = self.real_binary()
        self.fake_mise(real)
        self.link_to_mise()
        result = version_probe.probe_runtime("opencode")
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["resolved_via"], "mise which")
        self.assertTrue((self.root / "cwd.txt").exists())

    def test_neutral_cwd_and_env_for_probe_and_resolver(self):
        real = self.real_binary()
        cwd_log = self.root / "mise-cwd.txt"
        self.script(
            self.bin / "mise",
            f"pwd > '{cwd_log}'; /usr/bin/env > '{self.root / 'mise-env.txt'}'; echo '{real}'",
        )
        self.link_to_mise()
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)
        self.assertEqual(version_probe.probe_runtime("opencode")["status"], "qualified")
        self.assertEqual((self.root / "cwd.txt").read_text().strip(), "/")
        self.assertEqual(cwd_log.read_text().strip(), "/")
        for name in ("env.txt", "mise-env.txt"):
            text = (self.root / name).read_text()
            for var in ("MISE_AUTO_INSTALL", "MISE_EXEC_AUTO_INSTALL", "MISE_NOT_FOUND_AUTO_INSTALL"):
                self.assertIn(f"{var}=0", text)

    def test_plain_binary_runs_in_neutral_cwd(self):
        record = self.root / "cwd.txt"
        self.script(self.bin / "pi", f"pwd > '{record}'; echo 1.4.0")
        os.chdir(self.root)
        self.addCleanup(os.chdir, "/")
        self.assertEqual(version_probe.probe_runtime("pi")["status"], "qualified")
        self.assertEqual(record.read_text().strip(), "/")

    def test_mise_without_resolver_is_skipped(self):
        target = self.shim("mise/shims")  # no mise executable on PATH
        (self.bin / "opencode").symlink_to(target)
        result = version_probe.probe_runtime("opencode")
        self.assertEqual(result["status"], "probe-skipped")
        self.assertEqual(result["reason"], "unresolved-mise-shim")
        self.assertFalse(self.marker.exists())

    def test_bad_resolver_answers_are_skipped(self):
        shim_target = self.shim("mise/shims")
        bad = {
            "shim path": str(shim_target),
            "relative": "bin/opencode",
            "missing": str(self.root / "nope"),
            "empty": "",
        }
        for label, answer in bad.items():
            self.fake_mise(answer)
            (self.bin / "opencode").unlink(missing_ok=True)
            (self.bin / "opencode").symlink_to(shim_target)
            result = version_probe.probe_runtime("opencode")
            self.assertEqual(result["status"], "probe-skipped", label)
            self.assertEqual(result["reason"], "unresolved-mise-shim", label)
        self.assertFalse(self.marker.exists())

    def test_resolver_pointing_at_non_executable_or_directory_is_skipped(self):
        target = self.shim("mise/shims")
        plain = self.root / "plain"
        plain.write_text("#!/bin/sh\necho 1.19.5\n")
        (self.bin / "opencode").symlink_to(target)
        for answer in (plain, self.root):
            self.fake_mise(answer)
            self.assertEqual(version_probe.probe_runtime("opencode")["status"], "probe-skipped")

    def test_other_managers_are_skipped_without_execution(self):
        layouts = {
            "volta": ".volta/bin",
            "asdf": ".asdf/shims",
            "pyenv": ".pyenv/shims",
            "shim": "rbenv/shims",
        }
        for manager, rel in layouts.items():
            target = self.shim(rel)
            (self.bin / "opencode").unlink(missing_ok=True)
            (self.bin / "opencode").symlink_to(target)
            result = version_probe.probe_runtime("opencode")
            self.assertEqual(result["status"], "probe-skipped", manager)
            self.assertEqual(result["reason"], f"wrapper:{manager}", manager)
            self.assertNotEqual(result["status"], "qualified")
            self.assertFalse(self.marker.exists(), manager)

    def test_volta_symlink_to_volta_shim_is_skipped(self):
        volta = self.script(self.root / "opt" / "volta-shim", f"touch '{self.marker}'")
        (self.bin / "opencode").symlink_to(volta)
        result = version_probe.probe_runtime("opencode")
        self.assertEqual(result["reason"], "wrapper:volta")
        self.assertFalse(self.marker.exists())

    def test_script_with_manager_shebang_is_skipped(self):
        path = self.bin / "pi"
        path.write_text(f"#!/usr/bin/env asdf\ntouch '{self.marker}'\n")
        path.chmod(0o755)
        result = version_probe.probe_runtime("pi")
        self.assertEqual(result["status"], "probe-skipped")
        self.assertEqual(result["reason"], "wrapper:asdf")
        self.assertFalse(self.marker.exists())

    def test_ordinary_binary_and_shebang_are_not_wrappers(self):
        self.script(self.bin / "pi", "echo 1.4.0")
        self.assertIsNone(version_probe.detect_wrapper(str(self.bin / "pi")))
        self.assertEqual(version_probe.probe_runtime("pi")["status"], "qualified")

    def test_skipped_is_a_known_non_qualified_status(self):
        self.assertIn("probe-skipped", version_probe.STATUSES)


class DefaultOffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / "home"
        core.create("helper", "opencode", path=self.home, with_skills=False)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_default_verify_is_unchanged_and_never_probes(self):
        with mock.patch.object(version_probe, "_run", side_effect=AssertionError):
            with mock.patch.object(version_probe.shutil, "which", side_effect=AssertionError):
                code, text = self.run_cli("verify", str(self.home))
        self.assertIn(code, (0, 1))
        self.assertEqual(text, json.dumps(verify_home(self.home), indent=2) + "\n")
        self.assertNotIn("version_probe", text)
        self.assertIn('"runtime_version": "unverified"', text)

    def test_default_capabilities_is_unchanged_and_never_probes(self):
        with mock.patch.object(version_probe, "_run", side_effect=AssertionError):
            code, text = self.run_cli("capabilities")
        self.assertEqual(code, 0)
        self.assertEqual(text, json.dumps(capabilities.report(), indent=2) + "\n")
        self.assertNotIn("version_probe", text)

    def test_flag_only_adds_version_probe(self):
        with tempfile.TemporaryDirectory() as raw:
            with mock.patch.dict(os.environ, {"PATH": raw}):
                code, text = self.run_cli("verify", str(self.home), "--probe-versions")
                _, plain = self.run_cli("verify", str(self.home))
        report = json.loads(text)
        probe = report.pop("version_probe")
        self.assertEqual(report, json.loads(plain))
        self.assertEqual(
            {r["runtime"]: r["status"] for r in probe["results"]},
            {name: "not-installed" for name in ("opencode", "pi", "claude", "codex")},
        )
        self.assertEqual(
            sorted(r["runtime"] for r in probe["results"]), ["claude", "codex", "opencode", "pi"]
        )

    def test_capabilities_flag_adds_probe_per_runtime(self):
        with tempfile.TemporaryDirectory() as raw:
            with mock.patch.dict(os.environ, {"PATH": raw}):
                code, text = self.run_cli("capabilities", "--runtime", "pi", "--probe-versions")
        entry = json.loads(text)["runtimes"][0]
        self.assertEqual(entry["version_probe"]["status"], "not-installed")
        self.assertEqual(entry["runtime_version"], "unverified")

    def test_probe_does_not_change_exit_status(self):
        with tempfile.TemporaryDirectory() as raw:
            with mock.patch.dict(os.environ, {"PATH": raw}):
                with_flag, _ = self.run_cli("verify", str(self.home), "--probe-versions")
                without, _ = self.run_cli("verify", str(self.home))
        self.assertEqual(with_flag, without)


if __name__ == "__main__":
    unittest.main()

"""Learning configuration is local, scoped, and projected through native files."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from soulsteads import cli, core
from soulsteads.learning import validate
from soulsteads.native_config import sync
from soulsteads.runtimes import IDENTITY_FILES, digest, render_all
from soulsteads.verification import verify_home


class LearningConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = core.create("helper", "pi", path=self.root / "home")

    def invoke(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(list(args))
        return code, output.getvalue(), error.getvalue()

    def snapshot(self):
        return {
            path.relative_to(self.home).as_posix(): path.read_bytes()
            for path in self.home.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(self.home).parts
        }

    def assert_policy_loaded(self, mode):
        policy = (self.home / "LEARNING.md").read_text()
        self.assertIn(f"Mode: {mode}\n", policy)
        self.assertIn(
            "LEARNING.md",
            json.loads((self.home / "opencode.json").read_text())["instructions"],
        )
        self.assertIn("@LEARNING.md", (self.home / "CLAUDE.md").read_text())
        self.assertIn(policy, (self.home / ".pi/APPEND_SYSTEM.md").read_text())
        self.assertIn(
            policy,
            tomllib.loads((self.home / ".codex/config.toml").read_text())[
                "developer_instructions"
            ],
        )

    def test_new_homes_default_off_and_policy_is_loaded_by_all_adapters(self):
        self.assertEqual(
            core.load(self.home)["learning"], {"mode": "off", "skills": []}
        )
        self.assert_policy_loaded("off")
        self.assertEqual((self.home / "LEARNING.md").stat().st_mode & 0o777, 0o600)
        self.assertEqual(verify_home(self.home)["status"], "passed")
        self.assertIn(
            "LEARNING.md", core._git(self.home, "ls-files").stdout.splitlines()
        )

    def test_create_can_explicitly_enable_proposals_without_bundled_skills(self):
        home = self.root / "plain"
        code, _, error = self.invoke(
            "create",
            "plain",
            "--path",
            str(home),
            "--runtime",
            "claude",
            "--no-skills",
            "--learning",
            "propose",
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(core.load(home)["learning"], {"mode": "propose", "skills": []})
        self.assertFalse((home / "skills/skill-maintenance").exists())
        self.assertIn("Mode: propose", (home / "LEARNING.md").read_text())

    def test_mode_transitions_preserve_canonical_files_and_native_customizations(self):
        path = self.home / "opencode.json"
        config = json.loads(path.read_text())
        config["model"] = "synthetic/model"
        config["instructions"].append("workspace/extra.md")
        path.write_text(json.dumps(config))
        native = self.home / ".codex/config.toml"
        native.write_text(native.read_text() + '\nmodel = "synthetic"\n')
        canonical = {
            p: (self.home / p).read_bytes()
            for p in (*IDENTITY_FILES, "AGENTS.md", "skills/starter/SKILL.md")
        }
        code, _, error = self.invoke(
            "config",
            str(self.home),
            "--learning",
            "scoped-apply",
            "--learning-skill",
            "starter",
            "--learning-skill",
            "skill-maintenance",
            "--hindsight-url",
            "https://synthetic.example/mcp/helper/",
            "--runtime",
            "codex",
        )
        self.assertEqual(code, 0, error)
        self.assert_policy_loaded("scoped-apply")
        self.assertIn(
            "`skills/starter/SKILL.md`", (self.home / "LEARNING.md").read_text()
        )
        self.assertEqual(core.load(self.home)["runtime"], "codex")
        self.assertIn("hindsight", core.load(self.home))
        self.assertEqual(json.loads(path.read_text())["model"], "synthetic/model")
        self.assertIn(
            "workspace/extra.md", json.loads(path.read_text())["instructions"]
        )
        self.assertEqual(tomllib.loads(native.read_text())["model"], "synthetic")
        for mode in ("propose", "off"):
            code, _, error = self.invoke("config", str(self.home), "--learning", mode)
            self.assertEqual(code, 0, error)
            self.assert_policy_loaded(mode)
            self.assertEqual(core.load(self.home)["learning"]["skills"], [])
        self.assertEqual(
            {p: (self.home / p).read_bytes() for p in canonical}, canonical
        )
        self.assertEqual(sync(self.home), [])
        core.commit(self.home, "Configure learning")
        self.assertEqual(core._git(self.home, "status", "--porcelain").stdout, "")

    def test_invalid_or_missing_scope_is_rejected_without_publication(self):
        before = self.snapshot()
        for args in (
            ("--learning", "scoped-apply"),
            ("--learning-skill", "starter"),
            ("--learning", "off", "--learning-skill", "starter"),
            ("--learning", "scoped-apply", "--learning-skill", "missing"),
            ("--learning", "scoped-apply", "--learning-skill", "../outside"),
            ("--learning", "scoped-apply", "--learning-skill", "starter/SKILL.md"),
            (
                "--learning",
                "scoped-apply",
                "--learning-skill",
                "starter",
                "--learning-skill",
                "starter",
            ),
        ):
            with self.subTest(args=args):
                code, _, _ = self.invoke("config", str(self.home), *args)
                self.assertEqual(code, 1)
                self.assertEqual(self.snapshot(), before)

    def test_scope_cannot_follow_a_link_to_another_home(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("Synthetic private outside skill")
        (self.home / "skills/escape").symlink_to(outside, target_is_directory=True)
        before = (self.home / "soulsteads.json").read_bytes()
        code, output, error = self.invoke(
            "config",
            str(self.home),
            "--learning",
            "scoped-apply",
            "--learning-skill",
            "escape",
        )
        self.assertEqual(code, 1)
        self.assertNotIn("Synthetic private", output + error)
        self.assertEqual((self.home / "soulsteads.json").read_bytes(), before)

    def test_customized_policy_refuses_entire_update(self):
        (self.home / "LEARNING.md").write_text("Customized learning guidance\n")
        before = self.snapshot()
        code, _, _ = self.invoke("config", str(self.home), "--learning", "propose")
        self.assertEqual(code, 1)
        self.assertEqual(self.snapshot(), before)

    def test_missing_scoped_target_is_detected_but_can_be_disabled(self):
        sync(self.home, learning={"mode": "scoped-apply", "skills": ["starter"]})
        (self.home / "skills/starter/SKILL.md").unlink()
        (self.home / "skills/starter").rmdir()
        self.assertEqual(verify_home(self.home)["status"], "failed")
        sync(self.home, learning={"mode": "off", "skills": []})
        self.assertEqual(verify_home(self.home)["status"], "passed")

    def test_legacy_sync_preserves_guidance_until_explicit_configuration(self):
        manifest = core.load(self.home)
        manifest.pop("learning")
        documents = {name: (self.home / name).read_text() for name in IDENTITY_FILES}
        rendered = render_all(documents)
        for name, content in rendered.items():
            (self.home / name).write_text(content)
        (self.home / "LEARNING.md").unlink()
        manifest["managed_files"] = {p: digest(s) for p, s in rendered.items()}
        (self.home / "soulsteads.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        before = self.snapshot()
        self.assertEqual(sync(self.home), [])
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn("learning", core.load(self.home))
        self.assertEqual(
            verify_home(self.home)["native_adapters"][0]["learning"]["mode"],
            "legacy-guidance",
        )
        sync(self.home, learning={"mode": "off", "skills": []})
        self.assert_policy_loaded("off")

    def test_restore_returns_to_previous_policy_as_a_new_commit(self):
        first = core._git(self.home, "rev-parse", "HEAD").stdout.strip()
        sync(self.home, learning={"mode": "scoped-apply", "skills": ["starter"]})
        core.commit(self.home, "Enable scoped learning")
        untracked = self.home / "workspace/result.txt"
        untracked.write_text("Synthetic task output\n")
        core.revert(self.home, first)
        self.assert_policy_loaded("off")
        self.assertEqual(
            core.load(self.home)["learning"], {"mode": "off", "skills": []}
        )
        self.assertEqual(len(core.history(self.home).splitlines()), 3)
        self.assertEqual(untracked.read_text(), "Synthetic task output\n")
        self.assertEqual(verify_home(self.home)["status"], "passed")

    def test_unknown_policy_fields_and_malformed_types_are_rejected(self):
        for value in (
            False,
            [],
            "off",
            {},
            {"mode": "off"},
            {"mode": "off", "skills": [], "permissions": "all"},
            {"mode": ["off"], "skills": []},
            {"mode": "scoped-apply", "skills": [False]},
            {"mode": "scoped-apply", "skills": "starter"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value)

    def test_create_rejects_unavailable_scope_without_creating_home(self):
        home = self.root / "invalid"
        with self.assertRaises(core.HomeError):
            core.create(
                "invalid",
                "pi",
                path=home,
                with_skills=False,
                learning={"mode": "scoped-apply", "skills": ["starter"]},
            )
        self.assertFalse(home.exists())

    def test_malformed_feature_settings_fail_verification_without_echoing_values(self):
        manifest = core.load(self.home)
        for feature, value in (
            ("hindsight", {"url": "private-synthetic-value"}),
            ("learning", {"mode": "private-synthetic-value", "skills": []}),
            (
                "learning",
                {"mode": "scoped-apply", "skills": ["../private-synthetic-value"]},
            ),
        ):
            with self.subTest(feature=feature, value=value):
                (self.home / "soulsteads.json").write_text(
                    json.dumps({**manifest, feature: value})
                )
                before = self.snapshot()
                report = verify_home(self.home)
                self.assertEqual(report["status"], "failed")
                self.assertNotIn("private-synthetic-value", json.dumps(report))
                self.assertEqual(self.snapshot(), before)

    def test_create_and_config_work_without_optional_yaml(self):
        home = self.root / "without-yaml"
        commands = (
            [
                "create",
                "plain",
                "--runtime",
                "codex",
                "--path",
                str(home),
                "--learning",
                "propose",
            ],
            [
                "config",
                str(home),
                "--learning",
                "scoped-apply",
                "--learning-skill",
                "starter",
            ],
        )
        for command in commands:
            result = subprocess.run(
                [sys.executable, "-S", "-m", "soulsteads", *command],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
                env=dict(os.environ, PYTHONPYCACHEPREFIX="/tmp/soulsteads-pycache"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class CapabilityTests(unittest.TestCase):
    def test_cli_capabilities_need_no_home_and_describe_limits(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["capabilities"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(len(report["runtimes"]), 4)
        for adapter in report["runtimes"]:
            self.assertEqual(adapter["runtime_version"], "unverified")
            features = adapter["features"]
            self.assertTrue(features["hindsight"]["automatic_recall"])
            self.assertTrue(features["hindsight"]["automatic_retention"])
            self.assertTrue(features["hindsight"]["automation"]["opt_in"])
            self.assertFalse(features["learning"]["scope_enforced_by_soulsteads"])
            self.assertEqual(
                features["project_selection"]["support"],
                "qualified-native-resource-loading"
                if adapter["runtime"] == "pi"
                else "unqualified",
            )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(["capabilities", "--runtime", "pi"]), 0)
        self.assertEqual(
            [r["runtime"] for r in json.loads(output.getvalue())["runtimes"]], ["pi"]
        )

    def test_verify_reports_effective_mode_without_exposing_scope_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = core.create(
                "helper", "pi", path=Path(tmp).resolve() / "home", with_skills=False
            )
            name = "private-synthetic-procedure"
            skill = home / "skills" / name
            skill.mkdir(mode=0o700)
            core._write_private(
                skill / "SKILL.md",
                f"---\nname: {name}\ndescription: Synthetic procedure\n---\n",
            )
            sync(home, learning={"mode": "scoped-apply", "skills": [name]})
            report = verify_home(home)
            self.assertEqual(report["status"], "passed", report)
            for adapter in report["native_adapters"]:
                self.assertIn("capabilities", adapter)
                self.assertIn("LEARNING.md", adapter["paths"])
                self.assertEqual(
                    adapter["learning"], {"mode": "scoped-apply", "target_count": 1}
                )
            self.assertNotIn(name, json.dumps(report))
            self.assertNotIn(str(home), json.dumps(report))

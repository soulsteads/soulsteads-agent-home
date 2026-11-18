"""Native harness files, not launcher prompts, carry the Home identity."""

import contextlib
import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from soulsteads import core, native_config

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class NativeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.home = core.create("helper", "opencode", path=Path(self.tmp.name) / "home")

    def invoke(self, *args):
        from soulsteads.cli import main

        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return main(["config", str(self.home), *args])

    def test_every_home_is_ready_for_direct_native_launch(self):
        for relative in (
            "opencode.json",
            "CLAUDE.md",
            ".claude/settings.json",
            ".pi/settings.json",
            ".pi/APPEND_SYSTEM.md",
            ".codex/config.toml",
        ):
            self.assertTrue((self.home / relative).is_file(), relative)
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text())
        pi = (self.home / ".pi/APPEND_SYSTEM.md").read_text()
        for name in ("SOUL.md", "USER.md", "MEMORY.md"):
            original = (self.home / name).read_text()
            self.assertIn(original, codex["developer_instructions"])
            self.assertIn(original, pi)
        self.assertNotIn("model_instructions_file", codex)
        self.assertNotIn("sandbox_mode", codex)
        self.assertNotIn("approval_policy", codex)
        self.assertIn("managed_files", core.load(self.home))
        for native in (".agents", ".claude"):
            self.assertTrue(
                (self.home / native / "skills/skill-maintenance/SKILL.md").is_file()
            )

    def test_sync_refreshes_uncommitted_identity_and_preserves_native_customizations(
        self,
    ):
        (self.home / "USER.md").write_text('Synthetic café user with "quotes".\n')
        config = self.home / "opencode.json"
        value = json.loads(config.read_text())
        value["model"] = "example/model"
        value["instructions"].append("workspace/extra.md")
        config.write_text(json.dumps(value))
        native = self.home / ".codex/config.toml"
        native.write_text(
            native.read_text() + '\nmodel = "example-model"\n[custom]\nflag = true\n'
        )
        self.assertEqual(self.invoke("--sync"), 0)
        parsed = tomllib.loads(native.read_text())
        self.assertEqual(parsed["model"], "example-model")
        self.assertTrue(parsed["custom"]["flag"])
        self.assertIn(
            'Synthetic café user with "quotes".', parsed["developer_instructions"]
        )
        self.assertIn(
            "Synthetic café", (self.home / ".pi/APPEND_SYSTEM.md").read_text()
        )
        self.assertEqual(json.loads(config.read_text()), value)
        before = native.read_bytes()
        self.assertEqual(self.invoke("--sync"), 0)
        self.assertEqual(native.read_bytes(), before)

    def test_sync_preflights_every_file_before_writing(self):
        (self.home / "SOUL.md").write_text("New synthetic identity\n")
        native = self.home / ".codex/config.toml"
        native.write_text(
            native.read_text().replace("# Agent Home identity", "# Customized identity")
        )
        before = {
            p: p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        self.assertEqual(self.invoke("--sync"), 1)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_sync_upgrades_a_legacy_home_without_replacing_user_configuration(self):
        manifest = core.load(self.home)
        manifest.pop("managed_files")
        (self.home / "soulsteads.json").write_text(json.dumps(manifest))
        for name in (
            "CLAUDE.md",
            ".claude/settings.json",
            ".pi/settings.json",
            ".pi/APPEND_SYSTEM.md",
        ):
            (self.home / name).unlink()
        (self.home / ".codex/config.toml").write_text(
            '# User customization\nmodel = "example"\n'
        )
        self.assertEqual(self.invoke("--sync"), 0)
        self.assertTrue((self.home / ".pi/APPEND_SYSTEM.md").exists())
        parsed = tomllib.loads((self.home / ".codex/config.toml").read_text())
        self.assertEqual(parsed["model"], "example")
        self.assertIn("developer_instructions", parsed)
        self.assertIn("managed_files", core.load(self.home))

    def test_runtime_selection_keeps_other_native_configuration(self):
        old = (self.home / "opencode.json").read_bytes()
        core.configure(self.home, "codex")
        self.assertEqual((self.home / "opencode.json").read_bytes(), old)
        self.assertTrue((self.home / "CLAUDE.md").is_file())
        self.assertEqual(core.load(self.home)["runtime"], "codex")

    def test_malformed_nested_json_fails_without_partial_publication_or_content(self):
        path = self.home / "opencode.json"
        path.write_text(
            '{"private@example.invalid":' + "[" * 2000 + "0" + "]" * 2000 + "}"
        )
        before = (self.home / ".pi/APPEND_SYSTEM.md").read_bytes()
        self.assertEqual(self.invoke("--sync"), 1)
        self.assertEqual((self.home / ".pi/APPEND_SYSTEM.md").read_bytes(), before)

    def test_offline_verification_detects_stale_projections_without_repairing(self):
        from soulsteads.verification import verify_home

        (self.home / "MEMORY.md").write_text("New synthetic remembered preference\n")
        before = (self.home / ".pi/APPEND_SYSTEM.md").read_bytes()
        report = verify_home(self.home)
        statuses = {item["id"]: item["status"] for item in report["findings"]}
        self.assertEqual(statuses.get("native-projections"), "needs-review")
        self.assertEqual((self.home / ".pi/APPEND_SYSTEM.md").read_bytes(), before)
        self.assertNotIn("New synthetic remembered", json.dumps(report))
        from soulsteads.native_config import sync

        sync(self.home)
        statuses = {
            item["id"]: item["status"] for item in verify_home(self.home)["findings"]
        }
        self.assertEqual(statuses.get("native-projections"), "passed")

    def test_imported_identity_is_used_by_native_projections(self):
        import sys

        if sys.platform != "linux":
            self.skipTest("atomic import publication requires Linux")
        from soulsteads.hermes_import import import_profile

        source = Path(self.tmp.name) / "source"
        source.mkdir(mode=0o700)
        (source / "config.yaml").write_text("{}\n")
        (source / "SOUL.md").write_text("Synthetic imported identity sentinel\n")
        imported = Path(self.tmp.name) / "imported"
        import_profile("imported", source, runtime="codex", path=imported)
        self.assertIn(
            "Synthetic imported identity sentinel",
            (imported / ".pi/APPEND_SYSTEM.md").read_text(),
        )
        self.assertIn(
            "Synthetic imported identity sentinel",
            tomllib.loads((imported / ".codex/config.toml").read_text())[
                "developer_instructions"
            ],
        )

    def test_pi_launcher_does_not_inject_identity_as_a_user_prompt(self):
        from soulsteads.cli import main

        core.configure(self.home, "pi")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["run", str(self.home), "--dry-run"]), 0)
        self.assertEqual(json.loads(output.getvalue())["argv"], ["pi"])


class NativeConflictRecoveryTests(unittest.TestCase):
    """Roadmap gate: unowned settings preserved, conflicts explicit, recovery repeatable."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.home = core.create("helper", "claude", path=Path(self.tmp.name) / "home")
        self.settings = self.home / ".claude/settings.json"

    def snapshot(self):
        return {
            p.relative_to(self.home): p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }

    def head(self):
        return core._git(self.home, "rev-parse", "HEAD").stdout.strip()

    def edit_settings(self, **changes):
        value = json.loads(self.settings.read_text())
        value.update(changes)
        self.settings.write_text(json.dumps(value, indent=2) + "\n")

    def test_native_only_settings_survive_apply_and_restore(self):
        native = {"nativeOnly": {"nested": [1, 2], "flag": True}}
        self.edit_settings(**native)
        base = core.commit(self.home, "Native-only setting")
        native_config.configure_shared(self.home, {"model": "model-a"})
        applied = json.loads(self.settings.read_text())
        self.assertEqual(applied["model"], "model-a")
        self.assertEqual(applied["nativeOnly"], native["nativeOnly"])
        core.commit(self.home, "Apply shared model")
        core.revert(self.home, base)
        restored = json.loads(self.settings.read_text())
        self.assertNotIn("model", restored)
        self.assertEqual(restored["nativeOnly"], native["nativeOnly"])
        native_config.sync(self.home)
        self.assertEqual(
            json.loads(self.settings.read_text())["nativeOnly"], native["nativeOnly"]
        )

    def test_user_edit_to_owned_setting_conflicts_and_leaves_files_identical(self):
        native_config.configure_shared(self.home, {"model": "model-a"})
        core.commit(self.home, "Apply shared model")
        self.edit_settings(model="user-choice")
        (self.home / "SOUL.md").write_text("Changed canonical identity\n")
        before = self.snapshot()
        head = self.head()
        with self.assertRaisesRegex(core.HomeError, "conflict"):
            native_config.sync(self.home)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.head(), head)
        self.assertEqual(json.loads(self.settings.read_text())["model"], "user-choice")

    def test_customized_generated_file_reports_explicit_conflict_byte_identical(self):
        target = self.home / ".pi/APPEND_SYSTEM.md"
        target.write_text(target.read_text() + "\nUser customization.\n")
        (self.home / "SOUL.md").write_text("Changed canonical identity\n")
        before = self.snapshot()
        with self.assertRaisesRegex(
            core.HomeError,
            r"native configuration conflict: \.pi/APPEND_SYSTEM\.md; preserve your edits",
        ):
            native_config.sync(self.home)
        self.assertEqual(self.snapshot(), before)

    def test_repeated_restore_of_same_revision_is_refused_and_state_unchanged(self):
        base = self.head()
        native_config.configure_shared(self.home, {"model": "model-a"})
        core.commit(self.home, "Apply shared model")
        restored = core.revert(self.home, base)
        after_first = self.snapshot()
        with self.assertRaisesRegex(core.HomeError, "already checked out"):
            core.revert(self.home, base)
        self.assertEqual(self.snapshot(), after_first)
        self.assertEqual(self.head(), restored)
        self.assertEqual(core._git(self.home, "status", "--porcelain").stdout, "")
        native_config.sync(self.home)
        self.assertEqual(self.snapshot(), after_first)

    def test_recovery_after_conflict_is_repeatable(self):
        native_config.configure_shared(self.home, {"model": "model-a"})
        good = core.commit(self.home, "Apply shared model")
        good_bytes = self.settings.read_bytes()
        for attempt in range(3):
            self.edit_settings(model=f"user-choice-{attempt}")
            before = self.snapshot()
            for _ in range(2):  # the same conflict is reported every time
                with self.assertRaisesRegex(core.HomeError, "conflict"):
                    native_config.sync(self.home)
                self.assertEqual(self.snapshot(), before)
            # Recovery: the user's choice is reviewed and discarded.
            self.settings.write_bytes(good_bytes)
            native_config.sync(self.home)
            self.assertEqual(self.settings.read_bytes(), good_bytes)
            self.assertEqual(core._git(self.home, "status", "--porcelain").stdout, "")
            self.assertEqual(self.head(), good)


if __name__ == "__main__":
    unittest.main()

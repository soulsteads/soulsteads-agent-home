"""Public settings workflows against disposable native Homes, not real agents."""

from __future__ import annotations

import importlib
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from soulsteads import core


class SettingsAcceptanceTests(unittest.TestCase):
    """Exercise the public API and actual native files across every harness."""

    def setUp(self):
        self.settings = importlib.import_module("soulsteads.settings")
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def home(self, runtime):
        return core.create("settings-test", runtime, path=self.root / runtime)

    @staticmethod
    def native(home, runtime):
        paths = {
            "codex": ".codex/config.toml",
            "pi": ".pi/settings.json",
            "claude": ".claude/settings.json",
            "opencode": "opencode.json",
        }
        text = (home / paths[runtime]).read_text()
        return tomllib.loads(text) if runtime == "codex" else json.loads(text)

    def test_model_preview_apply_unset_preserves_identity_for_every_runtime(self):
        for runtime in ("codex", "pi", "claude", "opencode"):
            with self.subTest(runtime=runtime):
                home = self.home(runtime)
                before = self.native(home, runtime)
                plan = self.settings.plan_changes(
                    home,
                    runtime,
                    [{"op": "set", "path": "@model", "value": "example-model"}],
                )
                self.assertEqual(
                    self.native(home, runtime), before, "preview wrote files"
                )
                self.settings.apply_plan(home, plan)
                changed = self.native(home, runtime)
                model_key = "defaultModel" if runtime == "pi" else "model"
                self.assertEqual(changed[model_key], "example-model")
                for key, value in before.items():
                    self.assertEqual(changed[key], value, "native identity changed")
                removal = self.settings.plan_changes(
                    home,
                    runtime,
                    [{"op": "unset", "path": "@model"}],
                )
                self.settings.apply_plan(home, removal)
                self.assertEqual(self.native(home, runtime), before)

    def test_stale_plan_refuses_without_destroying_external_edit(self):
        home = self.home("opencode")
        plan = self.settings.plan_changes(
            home,
            "opencode",
            [{"op": "set", "path": "@model", "value": "planned"}],
        )
        target = home / "opencode.json"
        value = json.loads(target.read_text())
        value["model"] = "external-edit"
        target.write_text(json.dumps(value) + "\n")
        external = target.read_bytes()
        with self.assertRaises(core.HomeError):
            self.settings.apply_plan(home, plan)
        self.assertEqual(target.read_bytes(), external)

    def test_identity_and_parent_traversal_are_not_generic_settings_targets(self):
        for runtime, pointer in (
            ("codex", "/developer_instructions"),
            ("opencode", "/instructions"),
        ):
            with self.subTest(runtime=runtime):
                home = self.home(runtime)
                before = self.native(home, runtime)
                for path in (pointer, "../../outside"):
                    with self.assertRaises(core.HomeError):
                        self.settings.plan_changes(
                            home,
                            runtime,
                            [{"op": "set", "path": path, "value": "untrusted"}],
                        )
                self.assertEqual(self.native(home, runtime), before)

    def test_native_advanced_settings_roundtrip_without_translation(self):
        home = self.home("opencode")
        value = {"bash": {"*": "ask", "git status": "allow"}}
        plan = self.settings.plan_changes(
            home,
            "opencode",
            [{"op": "set", "path": "/permission", "value": value}],
        )
        self.settings.apply_plan(home, plan)
        self.assertEqual(self.native(home, "opencode")["permission"], value)
        exported = self.settings.export_profile(home, "opencode")
        destination = core.create(
            "destination", "opencode", path=self.root / "destination"
        )
        imported = self.settings.plan_import(destination, "opencode", exported)
        self.settings.apply_plan(destination, imported)
        self.assertEqual(self.native(destination, "opencode")["permission"], value)

    def test_secret_literal_is_not_accepted_as_portable_provider_setting(self):
        home = self.home("opencode")
        before = self.native(home, "opencode")
        with self.assertRaises(core.HomeError):
            self.settings.plan_changes(
                home,
                "opencode",
                [
                    {
                        "op": "set",
                        "path": "/provider/example/options/apiKey",
                        "value": "synthetic-secret-must-not-be-stored",
                    }
                ],
            )
        self.assertEqual(self.native(home, "opencode"), before)

    def test_native_file_symlink_is_never_followed_for_apply(self):
        home = self.home("opencode")
        plan = self.settings.plan_changes(
            home,
            "opencode",
            [{"op": "set", "path": "@model", "value": "planned"}],
        )
        outside = self.root / "outside.json"
        outside.write_text('{"model": "outside"}\n')
        original = outside.read_bytes()
        (home / "opencode.json").unlink()
        (home / "opencode.json").symlink_to(outside)
        with self.assertRaises(core.HomeError):
            self.settings.apply_plan(home, plan)
        self.assertEqual(outside.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

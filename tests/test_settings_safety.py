"""Adversarial settings lifecycles using real disposable Homes and native files."""

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core, native_config, settings
from soulsteads.settings_formats import delete_jsonc, parse_jsonc, update_jsonc


class SettingsSafetyTests(unittest.TestCase):
    def setUp(self):
        old = os.umask(0o077)
        self.addCleanup(os.umask, old)
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def home(self, runtime="opencode", name="home"):
        return core.create(name, runtime, path=self.root / name)

    def test_actual_cli_saved_plan_roundtrip_is_private_and_applies(self):
        home = self.home()
        output = self.root / "plan.json"
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(
                cli.main(
                    [
                        "settings",
                        "set",
                        "--home",
                        str(home),
                        "--runtime",
                        "opencode",
                        "--key",
                        "@model",
                        "--value",
                        '"provider/model"',
                        "--plan-file",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertNotIn("model", json.loads((home / "opencode.json").read_text()))
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                cli.main(
                    [
                        "settings",
                        "apply",
                        "--home",
                        str(home),
                        "--plan-file",
                        str(output),
                    ]
                ),
                0,
            )
        self.assertEqual(
            json.loads((home / "opencode.json").read_text())["model"], "provider/model"
        )

    def test_modified_preview_cannot_hide_different_native_changes(self):
        home = self.home()
        plan = settings.plan_changes(
            home, "opencode", [{"op": "set", "path": "@model", "value": "shown"}]
        )
        original = (home / "opencode.json").read_bytes()
        plan["changes"][0]["value"] = "not-shown"
        with self.assertRaises(core.HomeError):
            settings.apply_plan(home, plan)
        self.assertEqual((home / "opencode.json").read_bytes(), original)

    def test_cli_large_saved_plan_round_trip_uses_bounded_transfer_limit(self):
        home = self.home()
        changes = self.root / "large-changes.json"
        receipt = self.root / "large-plan.json"
        value = "portable transfer text " * 30000
        changes.write_text(
            json.dumps([{"op": "set", "path": "/application_notes", "value": value}])
        )
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            planned = cli.main(
                [
                    "settings",
                    "plan",
                    "--home",
                    str(home),
                    "--runtime",
                    "opencode",
                    "--changes-file",
                    str(changes),
                    "--plan-file",
                    str(receipt),
                ]
            )
            self.assertEqual(planned, 0)
            self.assertGreater(receipt.stat().st_size, 1024 * 1024)
            applied = cli.main(
                ["settings", "apply", "--home", str(home), "--plan-file", str(receipt)]
            )
        self.assertEqual(applied, 0)
        self.assertEqual(
            json.loads((home / "opencode.json").read_text())["application_notes"], value
        )

    def test_manifest_changes_invalidate_a_previously_saved_plan(self):
        home = self.home()
        plan = settings.plan_changes(
            home, "opencode", [{"op": "set", "path": "@model", "value": "shown"}]
        )
        manifest = json.loads((home / "soulsteads.json").read_text())
        manifest["name"] = "changed-name"
        (home / "soulsteads.json").write_text(json.dumps(manifest))
        with self.assertRaises(core.HomeError):
            settings.apply_plan(home, plan)

    def test_invalid_known_enum_types_are_user_errors_not_tracebacks(self):
        home = self.home("codex")
        for path in ("/sandbox_mode", "/approval_policy"):
            with self.subTest(path=path), self.assertRaises(core.HomeError):
                settings.plan_changes(
                    home,
                    "codex",
                    [{"op": "set", "path": path, "value": {"invalid": True}}],
                )

    def test_root_rebind_before_publication_does_not_write_foreign_home(self):
        home = self.home()
        foreign = self.home(name="foreign")
        before = (foreign / "opencode.json").read_bytes()
        plan = settings.plan_changes(
            home, "opencode", [{"op": "set", "path": "@model", "value": "planned"}]
        )
        original = native_config._prepare_parents
        moved = self.root / "moved"

        def rebound(*args):
            result = original(*args)
            home.rename(moved)
            foreign.rename(home)
            return result

        with (
            patch("soulsteads.settings.native._prepare_parents", side_effect=rebound),
            self.assertRaises(core.HomeError),
        ):
            settings.apply_plan(home, plan)
        self.assertEqual((home / "opencode.json").read_bytes(), before)
        self.assertNotIn("model", json.loads((moved / "opencode.json").read_text()))

    def test_multidocument_profile_keeps_primary_and_mcp_native(self):
        home = self.home("claude")
        changes = [
            {"op": "set", "path": "@model", "value": "example"},
            {
                "op": "set",
                "path": "/mcpServers/application",
                "value": {
                    "type": "http",
                    "url": "http://127.0.0.1:9/mcp",
                    "headers": {"Authorization": "Bearer ${APP_TOKEN}"},
                },
            },
        ]
        settings.apply_plan(home, settings.plan_changes(home, "claude", changes))
        profile = settings.export_profile(home, "claude")
        destination = self.home("claude", "destination")
        plan = settings.plan_import(destination, "claude", profile)
        self.assertEqual(set(plan["targets"]), {".claude/settings.json", ".mcp.json"})
        settings.apply_plan(destination, json.loads(json.dumps(plan)))
        self.assertEqual(
            json.loads((destination / ".claude/settings.json").read_text())["model"],
            "example",
        )
        self.assertIn(
            "application",
            json.loads((destination / ".mcp.json").read_text())["mcpServers"],
        )

    def test_partial_multidocument_publication_is_reported_and_original_plan_is_stale(
        self,
    ):
        home = self.home("claude")
        plan = settings.plan_changes(
            home,
            "claude",
            [
                {"op": "set", "path": "@model", "value": "example"},
                {
                    "op": "set",
                    "path": "/mcpServers/application",
                    "value": {"command": "example-tool"},
                },
            ],
        )
        publish = settings.publish_file
        count = 0

        def failure(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("synthetic second-file publication failure")
            return publish(*args, **kwargs)

        with (
            patch("soulsteads.settings.publish_file", side_effect=failure),
            self.assertRaisesRegex(core.HomeError, "partial"),
        ):
            settings.apply_plan(home, plan)
        self.assertEqual(
            json.loads((home / ".claude/settings.json").read_text())["model"], "example"
        )
        self.assertFalse((home / ".mcp.json").exists())
        with self.assertRaises(core.HomeError):
            settings.apply_plan(home, plan)

    def test_codex_managed_block_survives_native_settings_and_sync(self):
        home = self.home("codex")
        native_config.sync(
            home,
            hindsight={
                "url": "http://127.0.0.1:9/mcp/testbank/",
                "token_env": "APP_TOKEN",
            },
        )
        before = (
            (home / ".codex/config.toml")
            .read_text()
            .split("# END SOULSTEADS MANAGED\n")[0]
        )
        plan = settings.plan_changes(
            home,
            "codex",
            [
                {"op": "set", "path": "@model", "value": "example"},
                {
                    "op": "set",
                    "path": "/mcp_servers/application",
                    "value": {"command": "example-tool"},
                },
            ],
        )
        settings.apply_plan(home, plan)
        self.assertEqual(
            (home / ".codex/config.toml")
            .read_text()
            .split("# END SOULSTEADS MANAGED\n")[0],
            before,
        )
        core.commit(home, "Configure example native settings")
        native_config.sync(home)
        self.assertEqual(
            settings.get_setting(home, "codex", "@model")["value"], "example"
        )

    def test_export_omits_credential_literals_with_explicit_ledger(self):
        home = self.home()
        path = home / "opencode.json"
        value = json.loads(path.read_text())
        value["provider"] = {"example": {"options": {"apiKey": "synthetic-literal"}}}
        path.write_text(json.dumps(value))
        profile = settings.export_profile(home, "opencode")
        self.assertNotIn("synthetic-literal", json.dumps(profile))
        self.assertIn(
            "/provider/example/options/apiKey",
            [row["path"] for row in profile["omissions"]],
        )
        self.assertNotIn("[REDACTED]", json.dumps(profile["settings"]))

    def test_toml_operations_are_ordered_not_grouped(self):
        home = self.home("codex")
        plan = settings.plan_changes(
            home,
            "codex",
            [
                {"op": "set", "path": "@model", "value": "one"},
                {"op": "unset", "path": "@model"},
                {"op": "set", "path": "@model", "value": "last"},
            ],
        )
        settings.apply_plan(home, plan)
        self.assertEqual(settings.get_setting(home, "codex", "@model")["value"], "last")

    def test_jsonc_nested_delete_and_repeated_pointer_names(self):
        text = '{"before":1,"nested":{"only":2},"after":3}'
        changed = delete_jsonc(text, ("nested", "only"))
        self.assertEqual(parse_jsonc(changed), {"before": 1, "nested": {}, "after": 3})
        changed = update_jsonc('{"same":{"same":{}}}', [(("same", "same", "new"), 4)])
        self.assertEqual(parse_jsonc(changed), {"same": {"same": {"new": 4}}})
        self.assertEqual(
            parse_jsonc(delete_jsonc('{"only":2, /*keep*/}', ("only",))), {}
        )

    def test_jsonc_duplicate_and_overflow_numbers_fail_closed(self):
        for text in ('{"x":1,"x":2}', '{"x":1e9999}', '{"x":NaN}'):
            with self.subTest(text=text), self.assertRaises(core.HomeError):
                parse_jsonc(text)


if __name__ == "__main__":
    unittest.main()

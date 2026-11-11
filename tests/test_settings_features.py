"""Feature contracts: settings must reach the correct native document and scope."""

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from soulsteads import core


class SettingsFeatureContractTests(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.engine = importlib.import_module("soulsteads.settings")
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def home(self, runtime):
        return core.create("feature-test", runtime, path=self.root / runtime)

    def apply(self, home, runtime, path, value):
        plan = self.engine.plan_changes(
            home, runtime, [{"op": "set", "path": path, "value": value}]
        )
        return self.engine.apply_plan(home, json.loads(json.dumps(plan)))

    def test_observed_version_is_not_a_fake_catalog_revision_gate(self):
        result = self.engine.catalog("codex", version="0.157.1")
        self.assertEqual(result["observed_version"], "0.157.1")
        self.assertIn("catalog_revision", result)
        self.assertIn("qualification", result)

    def test_pi_provider_and_reasoning_aliases_use_real_native_keys(self):
        home = self.home("pi")
        self.apply(home, "pi", "@provider", "example-provider")
        self.apply(home, "pi", "@reasoning", "high")
        document = json.loads((home / ".pi/settings.json").read_text())
        self.assertEqual(document["defaultProvider"], "example-provider")
        self.assertEqual(document["defaultThinkingLevel"], "high")

    def test_managed_instructions_are_readable_but_not_writable(self):
        home = self.home("opencode")
        result = self.engine.get_setting(home, "opencode", "/instructions")
        self.assertEqual(result["value"], ["SOUL.md", "USER.md", "MEMORY.md"])
        with self.assertRaises(core.HomeError):
            self.apply(home, "opencode", "/instructions", ["replacement.md"])

    def test_claude_hooks_are_native_advanced_settings_not_managed_identity(self):
        home = self.home("claude")
        value = {
            "PreToolUse": [{"hooks": [{"type": "command", "command": "printf safe"}]}]
        }
        self.apply(home, "claude", "/hooks", value)
        self.assertEqual(
            json.loads((home / ".claude/settings.json").read_text())["hooks"], value
        )
        exported = self.engine.export_profile(home, "claude")
        self.assertEqual(exported["settings"]["hooks"], value)

    def test_generic_mcp_reaches_each_harness_native_document(self):
        for runtime, path, document_path in (
            ("codex", "/mcp_servers/application", ".codex/config.toml"),
            ("opencode", "/mcp/application", "opencode.json"),
            ("claude", "/mcpServers/application", ".mcp.json"),
            ("pi", "/mcpServers/application", ".pi/mcp.json"),
        ):
            with self.subTest(runtime=runtime):
                home = self.home(runtime)
                value = {"url": "http://127.0.0.1:9/mcp"}
                if runtime == "opencode":
                    value["type"] = "remote"
                elif runtime in {"claude", "pi"}:
                    value["type"] = "http"
                self.apply(home, runtime, path, value)
                self.assertTrue((home / document_path).is_file())
                result = self.engine.get_setting(home, runtime, path)
                self.assertEqual(result["value"]["url"], value["url"])
                if runtime in {"claude", "pi"}:
                    self.assertNotIn(
                        "mcpServers",
                        json.loads(
                            (
                                home
                                / (
                                    ".claude/settings.json"
                                    if runtime == "claude"
                                    else ".pi/settings.json"
                                )
                            ).read_text()
                        ),
                    )

    def test_native_env_reference_survives_connection_export_and_import(self):
        home = self.home("opencode")
        value = {
            "type": "remote",
            "url": "http://127.0.0.1:9/mcp",
            "headers": {"Authorization": "Bearer {env:APP_TOKEN}"},
        }
        self.apply(home, "opencode", "/mcp/application", value)
        exported = self.engine.export_profile(home, "opencode")
        self.assertEqual(exported["settings"]["mcp"]["application"], value)
        destination = core.create(
            "profile-destination", "opencode", path=self.root / "destination"
        )
        plan = self.engine.plan_import(destination, "opencode", exported)
        self.engine.apply_plan(destination, json.loads(json.dumps(plan)))
        self.assertEqual(
            json.loads((destination / "opencode.json").read_text())["mcp"][
                "application"
            ],
            value,
        )

    def test_hindsight_owned_connection_is_not_an_edit_target(self):
        home = self.home("opencode")
        for path, value in (
            ("/mcp/hindsight", {"url": "http://127.0.0.1:9"}),
            ("/mcp", {"hindsight": {"url": "http://127.0.0.1:9"}}),
        ):
            with self.subTest(path=path), self.assertRaises(core.HomeError):
                self.apply(home, "opencode", path, value)

    def test_claude_user_project_and_local_sources_resolve_static_provenance(self):
        home = self.home("claude")
        user = self.root / "user"
        project = self.root / "project"
        for root, relative, value in (
            (user, ".claude/settings.json", "user-model"),
            (project, ".claude/settings.json", "project-model"),
            (project, ".claude/settings.local.json", "local-model"),
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"model": value}) + "\n")
        result = self.engine.get_setting(
            home, "claude", "@model", user_dir=user, project=project
        )
        self.assertEqual(result["value"], "local-model")
        self.assertEqual(result["source"], "project-local")
        self.assertFalse(
            self.engine.inspect_settings(
                home, "claude", user_dir=user, project=project
            )["runtime_effective"]
        )

    def test_pi_user_scope_uses_agent_settings_directory(self):
        home = self.home("pi")
        user = self.root / "user"
        target = user / ".pi/agent/settings.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"defaultModel":"user-model"}\n')
        result = self.engine.get_setting(home, "pi", "@model", user_dir=user)
        self.assertEqual(result["value"], "user-model")
        self.assertEqual(result["source"], "user")

    def test_opencode_user_scope_and_existing_jsonc_are_supported(self):
        home = self.home("opencode")
        original = (home / "opencode.json").read_text()
        (home / "opencode.json").unlink()
        target = home / "opencode.jsonc"
        target.write_text("// retain this native comment\n" + original)
        user = self.root / "user"
        user_config = user / ".config/opencode/opencode.jsonc"
        user_config.parent.mkdir(parents=True)
        user_config.write_text('// user setting\n{"model":"user-model"}\n')
        self.assertEqual(
            self.engine.get_setting(home, "opencode", "@model", user_dir=user)["value"],
            "user-model",
        )
        self.apply(home, "opencode", "@model", "home-model")
        self.assertFalse((home / "opencode.json").exists())
        self.assertIn("retain this native comment", target.read_text())
        self.assertEqual(
            self.engine.get_setting(home, "opencode", "@model")["value"], "home-model"
        )

    def test_redacted_placeholders_are_not_imported_as_configuration(self):
        home = self.home("opencode")
        profile = self.engine.export_profile(home, "opencode")
        profile["settings"] = {"model": "[REDACTED]"}
        with self.assertRaises(core.HomeError):
            self.engine.plan_import(home, "opencode", profile)


if __name__ == "__main__":
    unittest.main()

"""Concrete regressions found by independent frozen-source review."""

import copy
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core, native_config, settings
from soulsteads.launch import prepare_launch


class SettingsReviewRegressions(unittest.TestCase):
    def setUp(self):
        old = os.umask(0o077)
        self.addCleanup(os.umask, old)
        temporary = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def home(self, name, runtime):
        return core.create(name, runtime, path=self.root / name)

    def apply(self, home, runtime, path, value):
        plan = settings.plan_changes(
            home, runtime, [{"op": "set", "path": path, "value": value}]
        )
        return settings.apply_plan(home, json.loads(json.dumps(plan)))

    def user_file(self, relative, text):
        user = self.root / "native-user"
        target = user / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_text(text)
        return user

    def test_known_codex_token_count_is_not_a_credential(self):
        home = self.home("count-source", "codex")
        self.apply(home, "codex", "/model_auto_compact_token_limit", 128000)
        self.apply(home, "codex", "/tool_output_token_limit", 16000)
        self.apply(
            home, "codex", "/model_auto_compact_token_limit_scope", "body_after_prefix"
        )
        self.assertEqual(
            settings.get_setting(home, "codex", "/model_auto_compact_token_limit")[
                "value"
            ],
            128000,
        )
        profile = settings.export_profile(home, "codex")
        self.assertEqual(profile["settings"]["model_auto_compact_token_limit"], 128000)
        self.assertEqual(profile["settings"]["tool_output_token_limit"], 16000)
        self.assertEqual(
            profile["settings"]["model_auto_compact_token_limit_scope"],
            "body_after_prefix",
        )
        destination = self.home("count-destination", "codex")
        settings.apply_plan(
            destination, settings.plan_import(destination, "codex", profile)
        )
        self.assertEqual(
            settings.get_setting(
                destination, "codex", "/model_auto_compact_token_limit"
            )["value"],
            128000,
        )
        for path, value in [
            ("/access_token", 128000),
            ("/model_auto_compact_token_limit", "literal-secret"),
            ("/tool_output_token_limit", -1),
            ("/model_auto_compact_token_limit", True),
            ("/model_auto_compact_token_limit_scope", "literal-secret"),
        ]:
            with self.subTest(path=path), self.assertRaises(core.HomeError):
                settings.plan_changes(
                    home, "codex", [{"op": "set", "path": path, "value": value}]
                )

    def test_mcp_import_preserves_managed_and_unrelated_destination_entries(self):
        for runtime, root in [
            ("codex", "mcp_servers"),
            ("pi", "mcpServers"),
            ("claude", "mcpServers"),
            ("opencode", "mcp"),
        ]:
            with self.subTest(runtime=runtime):
                source = self.home("source-" + runtime, runtime)
                value = (
                    {"type": "local", "command": ["fixture-tool"]}
                    if runtime == "opencode"
                    else {"command": "fixture-tool"}
                )
                self.apply(source, runtime, "/" + root + "/application", value)
                profile = settings.export_profile(source, runtime)
                destination = self.home("destination-" + runtime, runtime)
                native_config.sync(
                    destination,
                    hindsight={
                        "url": "http://127.0.0.1:9/mcp/review/",
                        "token_env": "FIXTURE_TOKEN",
                    },
                )
                self.apply(destination, runtime, "/" + root + "/existing", value)
                owned = settings.get_setting(
                    destination, runtime, "/" + root + "/hindsight"
                )["value"]
                settings.apply_plan(
                    destination, settings.plan_import(destination, runtime, profile)
                )
                self.assertEqual(
                    settings.get_setting(
                        destination, runtime, "/" + root + "/application"
                    )["value"],
                    value,
                )
                self.assertEqual(
                    settings.get_setting(
                        destination, runtime, "/" + root + "/existing"
                    )["value"],
                    value,
                )
                self.assertEqual(
                    settings.get_setting(
                        destination, runtime, "/" + root + "/hindsight"
                    )["value"],
                    owned,
                )
                own_profile = settings.export_profile(destination, runtime)
                settings.apply_plan(
                    destination, settings.plan_import(destination, runtime, own_profile)
                )
                injected = copy.deepcopy(profile)
                injected["settings"][root]["hindsight"] = {
                    "url": "http://127.0.0.1:9/replacement"
                }
                with self.assertRaises(core.HomeError):
                    settings.plan_import(destination, runtime, injected)

    def test_codex_replaced_array_reports_only_the_winning_source(self):
        home = self.home("array-home", "codex")
        self.apply(home, "codex", "/project_doc_fallback_filenames", ["home.md"])
        user = self.user_file(
            ".codex/config.toml", 'project_doc_fallback_filenames = ["user.md"]\n'
        )
        result = settings.get_setting(
            home, "codex", "/project_doc_fallback_filenames", user_dir=user
        )
        self.assertEqual(result["value"], ["home.md"])
        self.assertEqual(result["source"], "home")
        self.assertEqual(result["sources"], ["home"])

    def test_scalar_replacement_and_shadowed_children_have_no_false_contributors(self):
        home = self.home("provenance-home", "opencode")
        self.apply(home, "opencode", "/model", "home-model")
        self.apply(home, "opencode", "/permission", "deny")
        user = self.user_file(
            ".config/opencode/opencode.json",
            '{"model":"user-model","permission":{"bash":"allow"}}',
        )
        scalar = settings.get_setting(home, "opencode", "/model", user_dir=user)
        self.assertEqual(scalar["sources"], ["home"])
        missing = settings.get_setting(
            home, "opencode", "/permission/bash", user_dir=user
        )
        self.assertFalse(missing["present"])
        self.assertIsNone(missing["source"])
        self.assertEqual(missing["sources"], [])

    def test_actually_merged_arrays_keep_both_contributors(self):
        home = self.home("merged-home", "opencode")
        self.apply(home, "opencode", "/plugin", ["home-plugin"])
        user = self.user_file(
            ".config/opencode/opencode.json", '{"plugin":["user-plugin"]}'
        )
        result = settings.get_setting(home, "opencode", "/plugin", user_dir=user)
        self.assertEqual(result["value"], ["user-plugin", "home-plugin"])
        self.assertEqual(result["source"], "merged")
        self.assertEqual(result["sources"], ["user", "home"])

    def test_reference_name_exemptions_do_not_apply_to_literal_environment_values(self):
        marker = "SYNTHETIC_LITERAL_CREDENTIAL"
        cases = [
            ("claude", {"env": {"TOKEN_ENV": marker}}),
            ("opencode", {"mcp": {"app": {"environment": {"API_KEY_ENV": marker}}}}),
        ]
        for runtime, value in cases:
            with self.subTest(runtime=runtime):
                with self.assertRaises(core.HomeError):
                    settings._secret_check(value, runtime=runtime)
                self.assertNotIn(
                    marker, json.dumps(settings._redact(value, runtime=runtime))
                )
        settings._secret_check(
            {
                "model_providers": {
                    "app": {
                        "env_key": "APP_KEY",
                        "env_http_headers": {"Authorization": "APP_AUTH"},
                    }
                },
                "mcp_servers": {
                    "app": {
                        "bearer_token_env_var": "APP_TOKEN",
                        "env_http_headers": {"Authorization": "APP_AUTH"},
                    }
                },
            },
            runtime="codex",
        )

    def test_split_credential_flags_are_rejected_and_redacted(self):
        for flag in ["--access-token", "--refresh_token", "--client-secret"]:
            for args in [[flag, "SYNTHETIC_LITERAL_CREDENTIAL"], [flag]]:
                with self.subTest(args=args):
                    with self.assertRaises(core.HomeError):
                        settings._secret_check(args, runtime="claude")
                    self.assertEqual(
                        settings._redact(args, runtime="claude"), "[REDACTED]"
                    )
            settings._secret_check([flag, "${APPLICATION_TOKEN}"], runtime="claude")
        settings._secret_check(["--max-tokens", "16000"], runtime="claude")

    def test_type_tampered_receipt_is_refused_without_writing(self):
        home = self.home("typed-receipt", "opencode")
        before = (home / "opencode.json").read_bytes()
        plan = settings.plan_changes(
            home,
            "opencode",
            [{"op": "set", "path": "/application_flag", "value": True}],
        )
        plan["changes"][0]["value"] = 1
        with self.assertRaises(core.HomeError):
            settings.apply_plan(home, plan)
        self.assertEqual((home / "opencode.json").read_bytes(), before)

    def test_managed_boolean_cannot_be_replaced_with_equal_integer(self):
        home = self.home("typed-owner", "opencode")
        native_config.sync(
            home,
            hindsight={
                "url": "http://127.0.0.1:9/mcp/review/",
                "token_env": "FIXTURE_TOKEN",
            },
        )
        value = settings.get_setting(home, "opencode", "/mcp")["value"]
        self.assertIs(value["hindsight"]["oauth"], False)
        value["hindsight"]["oauth"] = 0
        with self.assertRaises(core.HomeError):
            settings.plan_changes(
                home, "opencode", [{"op": "set", "path": "/mcp", "value": value}]
            )

    def test_rendered_semantic_types_must_match_preview(self):
        home = self.home("typed-render", "opencode")
        wrong = json.loads((home / "opencode.json").read_text())
        wrong["application_flag"] = 1
        with (
            patch("soulsteads.settings._render", return_value=json.dumps(wrong)),
            self.assertRaises(core.HomeError),
        ):
            settings.plan_changes(
                home,
                "opencode",
                [{"op": "set", "path": "/application_flag", "value": True}],
            )

    def test_native_sync_refuses_type_changed_managed_boolean(self):
        home = self.home("typed-native-owner", "opencode")
        native_config.sync(
            home,
            hindsight={
                "url": "http://127.0.0.1:9/mcp/review/",
                "token_env": "FIXTURE_TOKEN",
            },
        )
        target = home / "opencode.json"
        value = json.loads(target.read_text())
        value["mcp"]["hindsight"]["oauth"] = 0
        target.write_text(json.dumps(value))
        with self.assertRaises(core.HomeError):
            native_config.plan(home, core.load(home))

    def jsonc_home(self, name):
        home = self.home(name, "opencode")
        primary = home / "opencode.json"
        alternate = home / "opencode.jsonc"
        primary.rename(alternate)
        alternate.write_text(
            "// Native JSONC must remain authoritative.\n" + alternate.read_text()
        )
        settings.apply_plan(
            home,
            settings.plan_changes(
                home,
                "opencode",
                [{"op": "set", "path": "@model", "value": "jsonc-active-model"}],
            ),
        )
        return home

    def test_jsonc_native_refresh_refuses_without_publishing_conflicting_json(self):
        home = self.jsonc_home("jsonc-refresh")
        before = {
            str(p.relative_to(home)): p.read_bytes()
            for p in home.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(home).parts
        }
        with self.assertRaisesRegex(core.HomeError, "JSONC"):
            native_config.sync(home)
        self.assertFalse((home / "opencode.json").exists())
        after = {
            str(p.relative_to(home)): p.read_bytes()
            for p in home.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(home).parts
        }
        self.assertEqual(after, before)

    def test_commit_versions_active_jsonc_settings(self):
        home = self.jsonc_home("jsonc-commit")
        core.commit(home, "Version the active JSONC settings")
        tracked = core._git(home, "ls-tree", "--name-only", "HEAD").stdout.splitlines()
        self.assertIn("opencode.jsonc", tracked)
        self.assertNotIn("opencode.json", tracked)
        content = core._git(home, "show", "HEAD:opencode.jsonc").stdout
        self.assertEqual(content, (home / "opencode.jsonc").read_text())
        self.assertIn("jsonc-active-model", content)

    def test_tuple_credential_sequences_are_rejected_at_both_api_ingresses(self):
        for runtime, root, field in [
            ("codex", "mcp_servers", "args"),
            ("pi", "mcpServers", "args"),
            ("claude", "mcpServers", "args"),
            ("opencode", "mcp", "command"),
        ]:
            home = self.home("tuple-secret-" + runtime, runtime)
            arguments = ("--access-token", "SYNTHETIC_LITERAL_CREDENTIAL")
            if runtime == "opencode":
                arguments = ("fixture-tool", *arguments)
            with (
                self.subTest(runtime=runtime, api="change"),
                self.assertRaises(core.HomeError),
            ):
                settings.plan_changes(
                    home,
                    runtime,
                    [
                        {
                            "op": "set",
                            "path": f"/{root}/fixture/{field}",
                            "value": arguments,
                        }
                    ],
                )
            server: dict[str, object] = {field: arguments}
            if field == "args":
                server["command"] = "fixture-tool"
            profile = {
                "format": "soulsteads-settings-v1",
                "runtime": runtime,
                "catalog_revision": settings.CATALOG_REVISION,
                "settings": {root: {"fixture": server}},
            }
            with (
                self.subTest(runtime=runtime, api="import"),
                self.assertRaises(core.HomeError),
            ):
                settings.plan_import(home, runtime, profile)

    def test_safe_tuple_reference_sequences_normalize_to_json_lists(self):
        home = self.home("tuple-reference", "opencode")
        arguments = ("fixture-tool", "--access-token", "{env:FIXTURE_TOKEN}")
        receipt = settings.plan_changes(
            home,
            "opencode",
            [{"op": "set", "path": "/mcp/fixture/command", "value": arguments}],
        )
        self.assertIsInstance(receipt["changes"][0]["value"], list)
        settings.apply_plan(home, receipt)
        profile = {
            "format": "soulsteads-settings-v1",
            "runtime": "opencode",
            "catalog_revision": settings.CATALOG_REVISION,
            "settings": {"mcp": {"fixture": {"command": arguments}}},
        }
        imported = settings.plan_import(home, "opencode", profile)
        self.assertIsInstance(imported["changes"][0]["value"]["command"], list)
        settings.apply_plan(home, imported)
        self.assertEqual(
            json.loads((home / "opencode.json").read_text())["mcp"]["fixture"][
                "command"
            ],
            list(arguments),
        )

    def test_native_sync_refuses_overflowing_json_before_publication(self):
        home = self.home("finite-sync", "opencode")
        target = home / "opencode.json"
        value = json.loads(target.read_text())
        value["application_number"] = "OVERFLOW_MARKER"
        target.write_text(json.dumps(value).replace('"OVERFLOW_MARKER"', "1e9999"))
        before = target.read_bytes()
        with self.assertRaises(core.HomeError):
            native_config.plan(
                home,
                core.load(home),
                hindsight={
                    "url": "http://127.0.0.1:9/mcp/review/",
                    "token_env": "FIXTURE_TOKEN",
                },
            )
        self.assertEqual(target.read_bytes(), before)

    def test_private_argv_project_context_requires_explicit_consent(self):
        project = self.root / "project"
        project.mkdir(mode=0o700)
        for runtime in ["codex", "claude"]:
            home = self.home("consent-" + runtime, runtime)
            with (
                self.subTest(runtime=runtime),
                self.assertRaisesRegex(core.HomeError, "argv|process"),
            ):
                prepare_launch(home, runtime, project)

    def test_all_project_adapters_refuse_hardlinked_or_oversized_context(self):
        project = self.root / "project"
        project.mkdir(mode=0o700)
        for runtime in ["pi", "opencode", "codex", "claude"]:
            home = self.home("resource-" + runtime, runtime)
            agents = home / "AGENTS.md"
            alias = self.root / (runtime + "-hardlink")
            os.link(agents, alias)
            with (
                self.subTest(runtime=runtime, unsafe="hardlink"),
                self.assertRaises(core.HomeError),
            ):
                prepare_launch(home, runtime, project, allow_context_in_argv=True)
            alias.unlink()
            agents.write_text("x" * (native_config.MAX_FILE_BYTES + 1))
            with (
                self.subTest(runtime=runtime, unsafe="oversize"),
                self.assertRaises(core.HomeError),
            ):
                prepare_launch(home, runtime, project, allow_context_in_argv=True)

    def test_opted_in_cli_dry_run_does_not_print_private_context(self):
        home = self.home("private-dry-run", "codex")
        project = self.root / "project"
        project.mkdir(mode=0o700)
        marker = "SYNTHETIC_PRIVATE_MEMO"
        (home / "MEMORY.md").write_text(marker)
        native_config.sync(home)
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            result = cli.main(
                [
                    "run",
                    str(home),
                    "--project",
                    str(project),
                    "--allow-context-in-argv",
                    "--dry-run",
                ]
            )
        self.assertEqual(result, 0, error.getvalue())
        self.assertNotIn(marker, output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["private_context_redacted"])


if __name__ == "__main__":
    unittest.main()

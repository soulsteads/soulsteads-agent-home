"""Tests for the native settings command-line interface."""

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from soulsteads.cli import main, parser


class SettingsParserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.scratch = Path(self.tmp.name)

    def test_help_lists_settings_workflows_without_loading_engine(self):
        parsed = parser()
        action = next(action for action in parsed._actions if action.dest == "command")
        commands = action.choices
        settings_action = next(
            action
            for action in commands["settings"]._actions
            if action.dest == "settings_command"
        )
        self.assertEqual(
            set(settings_action.choices),
            {
                "catalog",
                "inspect",
                "get",
                "set",
                "unset",
                "plan",
                "apply",
                "export",
                "import",
            },
        )

    def test_settings_help_has_preview_and_explicit_apply_options(self):
        parsed = parser()
        top = next(action for action in parsed._actions if action.dest == "command")
        settings_action = next(
            action
            for action in top.choices["settings"]._actions
            if action.dest == "settings_command"
        )
        settings = settings_action.choices
        for name in ("set", "unset", "plan", "import"):
            sub = settings[name]
            flags = {flag for action in sub._actions for flag in action.option_strings}
            self.assertIn("--apply", flags)
            self.assertIn("--plan-file", flags)

    def test_change_value_is_json_not_python_literal(self):
        parsed = parser()
        args = parsed.parse_args(
            [
                "settings",
                "set",
                "--home",
                "/tmp/home",
                "--runtime",
                "opencode",
                "--key",
                "@model",
                "--value",
                '{"name":"m","enabled":true}',
            ]
        )
        self.assertEqual(json.loads(args.value), {"name": "m", "enabled": True})

    def test_native_pointer_and_alias_share_the_same_option(self):
        parsed = parser()
        pointer = parsed.parse_args(
            [
                "settings",
                "get",
                "--home",
                "/tmp/home",
                "--runtime",
                "opencode",
                "--key",
                "/agents/default/model",
            ]
        )
        alias = parsed.parse_args(
            [
                "settings",
                "get",
                "--home",
                "/tmp/home",
                "--runtime",
                "opencode",
                "--key",
                "@model",
            ]
        )
        self.assertEqual(pointer.key, "/agents/default/model")
        self.assertEqual(alias.key, "@model")

    def test_preview_does_not_apply_and_json_value_is_passed_as_native_data(self):
        calls = []
        fake_engine = SimpleNamespace(
            plan_changes=lambda *args, **kwargs: (
                calls.append(("plan", args, kwargs)) or {"plan_id": "p1"}
            ),
            apply_plan=lambda *args, **kwargs: (
                calls.append(("apply", args, kwargs)) or {"applied": True}
            ),
        )
        output = StringIO()
        with (
            patch.dict("sys.modules", {"soulsteads.settings": fake_engine}),
            redirect_stdout(output),
        ):
            status = main(
                [
                    "settings",
                    "set",
                    "--home",
                    "/tmp/home",
                    "--runtime",
                    "opencode",
                    "--key",
                    "@model",
                    "--value",
                    '{"id":"m1","enabled":true}',
                ]
            )
        self.assertEqual(status, 0)
        self.assertEqual([call[0] for call in calls], ["plan"])
        self.assertEqual(
            calls[0][1][2],
            [{"op": "set", "path": "@model", "value": {"id": "m1", "enabled": True}}],
        )
        self.assertEqual(json.loads(output.getvalue()), {"plan_id": "p1"})

    def test_explicit_apply_calls_engine_apply_after_preview(self):
        calls = []
        fake_engine = SimpleNamespace(
            plan_changes=lambda *args, **kwargs: (
                calls.append("plan") or {"plan_id": "p1"}
            ),
            apply_plan=lambda *args, **kwargs: (
                calls.append("apply") or {"applied": True}
            ),
        )
        output = StringIO()
        with (
            patch.dict("sys.modules", {"soulsteads.settings": fake_engine}),
            redirect_stdout(output),
        ):
            status = main(
                [
                    "settings",
                    "unset",
                    "--home",
                    "/tmp/home",
                    "--runtime",
                    "opencode",
                    "--key",
                    "/model",
                    "--apply",
                ]
            )
        self.assertEqual(status, 0)
        self.assertEqual(calls, ["plan", "apply"])
        self.assertEqual(json.loads(output.getvalue()), {"applied": True})

    def test_apply_reads_stored_plan_as_json(self):
        plan_path = self.scratch / "plan.json"
        plan = {"runtime": "opencode", "expected": "state-hash", "changes": []}
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        calls = []
        fake_engine = SimpleNamespace(
            apply_plan=lambda home, value: (
                calls.append((home, value)) or {"applied": True}
            )
        )
        output = StringIO()
        try:
            with (
                patch.dict("sys.modules", {"soulsteads.settings": fake_engine}),
                redirect_stdout(output),
            ):
                status = main(["settings", "apply", "--plan-file", str(plan_path)])
        finally:
            plan_path.unlink(missing_ok=True)
        self.assertEqual(status, 0)
        self.assertEqual(calls[0][1], plan)
        self.assertEqual(json.loads(output.getvalue()), {"applied": True})

    def test_catalog_inspect_get_and_export_dispatch(self):
        calls = []
        fake_engine = SimpleNamespace(
            catalog=lambda *a, **k: (
                calls.append(("catalog", a, k)) or {"runtime": "opencode"}
            ),
            inspect_settings=lambda *a, **k: (
                calls.append(("inspect", a, k)) or {"layers": []}
            ),
            get_setting=lambda *a, **k: calls.append(("get", a, k)) or {"value": "m"},
            export_profile=lambda *a, **k: (
                calls.append(("export", a, k)) or {"profile": 1}
            ),
        )
        cases = [
            ["settings", "catalog", "--runtime", "opencode"],
            [
                "settings",
                "inspect",
                "--home",
                "/tmp/home",
                "--runtime",
                "opencode",
                "--project",
                "/tmp/project",
                "--user-dir",
                "/tmp/user",
            ],
            [
                "settings",
                "get",
                "--home",
                "/tmp/home",
                "--runtime",
                "opencode",
                "--key",
                "@model",
            ],
            ["settings", "export", "--home", "/tmp/home", "--runtime", "opencode"],
        ]
        with patch.dict("sys.modules", {"soulsteads.settings": fake_engine}):
            for argv in cases:
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(argv), 0)
                self.assertTrue(json.loads(output.getvalue()))
        self.assertEqual(
            [call[0] for call in calls], ["catalog", "inspect", "get", "export"]
        )
        self.assertEqual(
            calls[1][2],
            {
                "project": Path("/tmp/project"),
                "user_dir": Path("/tmp/user"),
                "version": None,
            },
        )

    def test_plan_and_import_preview_dispatch(self):
        scratch = self.scratch
        profile_path = scratch / "cli-test-profile.json"
        profile_path.write_text(
            json.dumps({"settings": {"model": "m"}}), encoding="utf-8"
        )
        calls = []
        fake_engine = SimpleNamespace(
            plan_changes=lambda *a, **k: (
                calls.append(("plan", a, k)) or {"plan": "changes"}
            ),
            plan_import=lambda *a, **k: (
                calls.append(("import", a, k)) or {"plan": "import"}
            ),
            apply_plan=lambda *a, **k: (
                calls.append(("apply", a, k)) or {"applied": True}
            ),
        )
        try:
            with patch.dict("sys.modules", {"soulsteads.settings": fake_engine}):
                for argv in (
                    [
                        "settings",
                        "plan",
                        "--runtime",
                        "opencode",
                        "--changes",
                        '[{"op":"unset","path":"@model"}]',
                    ],
                    [
                        "settings",
                        "import",
                        "--runtime",
                        "opencode",
                        "--profile",
                        str(profile_path),
                    ],
                ):
                    output = StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(main(argv), 0)
                    self.assertEqual(
                        json.loads(output.getvalue())["plan"],
                        "changes" if argv[1] == "plan" else "import",
                    )
        finally:
            profile_path.unlink(missing_ok=True)
        self.assertEqual([call[0] for call in calls], ["plan", "import"])

    def test_preview_plan_file_contains_engine_plan_json(self):
        plan_path = self.scratch / "saved-plan.json"
        plan = {"runtime": "opencode", "expected": "hash", "changes": []}
        fake_engine = SimpleNamespace(plan_changes=lambda *a, **k: plan)
        try:
            with (
                patch.dict("sys.modules", {"soulsteads.settings": fake_engine}),
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "settings",
                            "plan",
                            "--runtime",
                            "opencode",
                            "--changes",
                            "[]",
                            "--plan-file",
                            str(plan_path),
                        ]
                    ),
                    0,
                )
            self.assertEqual(json.loads(plan_path.read_text(encoding="utf-8")), plan)
        finally:
            plan_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

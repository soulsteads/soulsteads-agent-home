"""Settings edits cannot remove manifest-owned memory automation."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from soulsteads import core, native_config, settings


class SettingsMemoryOwnershipTests(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home_count = 0

    def home(self, runtime, automation=None):
        if automation is None:
            automation = {"recall": True, "retain": True}
        self.home_count += 1
        home = core.create(
            "settings-memory", runtime, path=self.root / f"{runtime}-{self.home_count}"
        )
        native_config.sync(
            home,
            hindsight={
                "url": "http://127.0.0.1:9/mcp/settings-memory/",
                "token_env": "SYNTHETIC_MEMORY_TOKEN",
            },
            automation=automation,
        )
        return home

    def snapshot(self, home, *relative):
        return {path: (home / path).read_bytes() for path in relative}

    def assert_rejected_unchanged(self, home, runtime, changes, *paths):
        before = self.snapshot(home, *paths)
        with self.assertRaisesRegex(
            core.HomeError, "managed (memory hook|Codex hooks feature)"
        ):
            settings.plan_changes(home, runtime, changes)
        self.assertEqual(self.snapshot(home, *paths), before)

    @staticmethod
    def user_hook():
        return {"hooks": [{"type": "command", "command": "printf user"}]}

    def test_claude_owned_hook_group_cannot_be_replaced_by_generic_settings(self):
        home = self.home("claude")
        self.assert_rejected_unchanged(
            home,
            "claude",
            [
                {
                    "op": "set",
                    "path": "/hooks",
                    "value": {"PreToolUse": [self.user_hook()]},
                }
            ],
            ".claude/settings.json",
            "soulsteads.json",
        )

    def test_claude_owned_events_follow_each_enabled_manifest_policy(self):
        for policy, protected in (
            ({"recall": True, "retain": True}, ("UserPromptSubmit", "Stop")),
            ({"recall": True, "retain": False}, ("UserPromptSubmit",)),
            ({"recall": False, "retain": True}, ("UserPromptSubmit", "Stop")),
        ):
            with self.subTest(policy=policy):
                home = self.home("claude", policy)
                for event in protected:
                    with self.subTest(event=event):
                        self.assert_rejected_unchanged(
                            home,
                            "claude",
                            [{"op": "unset", "path": "/hooks/" + event}],
                            ".claude/settings.json",
                            "soulsteads.json",
                        )

    def test_claude_preserves_owned_group_while_allowing_unrelated_group_in_same_event(
        self,
    ):
        home = self.home("claude")
        document = json.loads((home / ".claude/settings.json").read_text())
        value = document["hooks"]["UserPromptSubmit"] + [self.user_hook()]
        plan = settings.plan_changes(
            home,
            "claude",
            [{"op": "set", "path": "/hooks/UserPromptSubmit", "value": value}],
        )
        settings.apply_plan(home, json.loads(json.dumps(plan)))
        actual = json.loads((home / ".claude/settings.json").read_text())["hooks"]
        self.assertEqual(actual["UserPromptSubmit"], value)
        self.assertIn("Stop", actual)

    def test_claude_owned_hook_multiplicity_cannot_change(self):
        home = self.home("claude")
        hooks = json.loads((home / ".claude/settings.json").read_text())["hooks"]
        for event in ("UserPromptSubmit", "Stop"):
            with self.subTest(event=event):
                groups = hooks[event]
                self.assert_rejected_unchanged(
                    home,
                    "claude",
                    [
                        {
                            "op": "set",
                            "path": "/hooks/" + event,
                            "value": groups + [groups[0]],
                        }
                    ],
                    ".claude/settings.json",
                    "soulsteads.json",
                )

    def test_disabled_memory_does_not_forbid_user_claude_hooks(self):
        home = self.home("claude", {"recall": False, "retain": False})
        plan = settings.plan_changes(
            home,
            "claude",
            [
                {
                    "op": "set",
                    "path": "/hooks",
                    "value": {"PreToolUse": [self.user_hook()]},
                }
            ],
        )
        settings.apply_plan(home, json.loads(json.dumps(plan)))
        self.assertEqual(
            json.loads((home / ".claude/settings.json").read_text())["hooks"],
            {"PreToolUse": [self.user_hook()]},
        )

    def test_import_and_saved_plan_cannot_bypass_claude_memory_hook_ownership(self):
        home = self.home("claude")
        before = self.snapshot(home, ".claude/settings.json", "soulsteads.json")
        profile = {
            "format": "soulsteads-settings-v1",
            "runtime": "claude",
            "catalog_revision": settings.CATALOG_REVISION,
            "settings": {"hooks": {"PreToolUse": [self.user_hook()]}},
        }
        with self.assertRaisesRegex(core.HomeError, "managed memory hook"):
            settings.plan_import(home, "claude", profile)
        self.assertEqual(
            self.snapshot(home, ".claude/settings.json", "soulsteads.json"), before
        )

        plan = settings.plan_changes(
            home, "claude", [{"op": "set", "path": "@model", "value": "synthetic"}]
        )
        plan["changes"] = [{"op": "unset", "path": "/hooks/UserPromptSubmit"}]
        with self.assertRaisesRegex(core.HomeError, "managed memory hook"):
            settings.apply_plan(home, plan)
        self.assertEqual(
            self.snapshot(home, ".claude/settings.json", "soulsteads.json"), before
        )

    def test_codex_memory_feature_is_protected_for_each_enabled_policy(self):
        for policy in (
            {"recall": True, "retain": True},
            {"recall": True, "retain": False},
            {"recall": False, "retain": True},
        ):
            with self.subTest(policy=policy):
                home = self.home("codex", policy)
                self.assert_rejected_unchanged(
                    home,
                    "codex",
                    [{"op": "unset", "path": "/features/hooks"}],
                    ".codex/config.toml",
                    "soulsteads.json",
                )

    def test_codex_unrelated_feature_remains_rooted_after_existing_user_table(self):
        home = self.home("codex")
        document = home / ".codex/config.toml"
        document.write_text(
            document.read_text() + '\n[model_providers.fixture]\nname = "fixture"\n'
        )
        plan = settings.plan_changes(
            home,
            "codex",
            [{"op": "set", "path": "/features/multi_agent", "value": True}],
        )
        settings.apply_plan(home, plan)
        self.assertTrue(settings.get_setting(home, "codex", "/features/hooks")["value"])
        self.assertTrue(
            settings.get_setting(home, "codex", "/features/multi_agent")["value"]
        )
        self.assertEqual(
            settings.get_setting(home, "codex", "/model_providers/fixture/name")[
                "value"
            ],
            "fixture",
        )

    def test_codex_memory_feature_is_protected_until_dedicated_disable(self):
        home = self.home("codex")
        self.assert_rejected_unchanged(
            home,
            "codex",
            [{"op": "unset", "path": "/features/hooks"}],
            ".codex/config.toml",
            "soulsteads.json",
        )
        plan = settings.plan_changes(
            home,
            "codex",
            [{"op": "set", "path": "/features/multi_agent", "value": True}],
        )
        settings.apply_plan(home, json.loads(json.dumps(plan)))
        self.assertTrue(settings.get_setting(home, "codex", "/features/hooks")["value"])
        self.assertTrue(
            settings.get_setting(home, "codex", "/features/multi_agent")["value"]
        )

        native_config.sync(
            home,
            automation={"recall": False, "retain": False},
        )
        self.assertFalse(
            settings.get_setting(home, "codex", "/features/hooks")["present"]
        )
        plan = settings.plan_changes(
            home,
            "codex",
            [{"op": "set", "path": "/features/hooks", "value": False}],
        )
        settings.apply_plan(home, json.loads(json.dumps(plan)))
        self.assertIs(
            settings.get_setting(home, "codex", "/features/hooks")["value"], False
        )


if __name__ == "__main__":
    unittest.main()

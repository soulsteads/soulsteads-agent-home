import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from soulsteads import core, native_config
from soulsteads.native_harness import FILE


def commit(home):
    subprocess.run(["git", "-C", str(home), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(home), "-c", "user.name=t", "-c", "user.email=t@l",
                    "commit", "-qm", "x"], check=True)


class NativeHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = core.create("n1", "soulsteads", Path(self.tmp.name) / "n1")

    def text(self):
        return (self.home / FILE).read_text()

    def test_create_is_clean_and_sync_is_idempotent(self):
        native_config.sync(self.home, selected_only=True)
        self.assertEqual(subprocess.run(["git", "-C", str(self.home), "status", "--porcelain"],
                                        capture_output=True, text=True).stdout, "")
        self.assertIn('id = "n1"', self.text())

    def test_settings_map_preserve_native_and_conflict(self):
        (self.home / FILE).write_text(self.text() + '\n[provider]\nbase_url_env = "X"\n\n[limits]\nmax_turns = 5\n')
        commit(self.home)
        native_config.configure_shared(self.home, {
            "model": "m", "permission": "read-only",
            "mcp": {"calc": {"command": "/bin/true", "args": []}}})
        text = self.text()
        self.assertIn('model = "m"', text)
        self.assertIn("max_turns = 5", text)
        self.assertIn('default_approval = "ask"', text)
        self.assertIn('"read_file", "list_dir", "search_files"', text)
        self.assertNotIn("run_command", text)
        commit(self.home)
        (self.home / FILE).write_text(text.replace('model = "m"', 'model = "z"'))
        commit(self.home)
        with self.assertRaises(core.HomeError):
            native_config.sync(self.home, selected_only=True)
        (self.home / FILE).write_text(text)
        commit(self.home)
        native_config.configure_shared(self.home, {"model": "m"})
        self.assertNotIn("mcp_servers", self.text())
        self.assertNotIn("grants", self.text())
        self.assertIn("max_turns = 5", self.text())

    def test_duplicate_owned_mcp_server_blocks_removal_without_changes(self):
        native_config.configure_shared(
            self.home,
            {"mcp": {"calc": {"command": "/bin/true", "args": []}}},
        )
        text = self.text()
        entry = text[text.index("[[mcp_servers]]") :]
        duplicated = text.rstrip() + "\n\n" + entry
        (self.home / FILE).write_text(duplicated)
        commit(self.home)
        before_config = (self.home / FILE).read_bytes()
        before_manifest = (self.home / "soulsteads.json").read_bytes()

        with self.assertRaisesRegex(core.HomeError, "duplicate MCP server name"):
            native_config.configure_shared(self.home, {})

        self.assertEqual((self.home / FILE).read_bytes(), before_config)
        self.assertEqual((self.home / "soulsteads.json").read_bytes(), before_manifest)
        self.assertEqual(self.text().count('name = "calc"'), 2)

    def test_duplicate_unowned_mcp_names_are_rejected_even_when_equal(self):
        text = self.text()
        entry = (
            '[[mcp_servers]]\nname = "calc"\ntransport = "stdio"\n'
            'command = "/bin/true"\nargs = []\ndefault_approval = "ask"\n'
        )
        duplicated = text.rstrip() + "\n\n" + entry + "\n" + entry
        (self.home / FILE).write_text(duplicated)
        commit(self.home)
        before_config = (self.home / FILE).read_bytes()
        before_manifest = (self.home / "soulsteads.json").read_bytes()

        with self.assertRaisesRegex(core.HomeError, "duplicate MCP server name"):
            native_config.configure_shared(
                self.home,
                {"mcp": {"calc": {"command": "/bin/true", "args": []}}},
            )

        self.assertEqual((self.home / FILE).read_bytes(), before_config)
        self.assertEqual((self.home / "soulsteads.json").read_bytes(), before_manifest)
        self.assertEqual(self.text().count('name = "calc"'), 2)

    def test_owned_edit_conflict_is_explicit_byte_identical_and_recovery_repeats(self):
        (self.home / FILE).write_text(self.text() + '\n[limits]\nmax_turns = 5\n')
        commit(self.home)
        native_config.configure_shared(self.home, {"model": "m"})
        commit(self.home)
        good = (self.home / FILE).read_bytes()
        for attempt in range(2):
            edited = good.replace(b'model = "m"', b'model = "user"')
            self.assertNotEqual(edited, good)
            (self.home / FILE).write_bytes(edited)
            commit(self.home)
            for _ in range(2):
                with self.assertRaisesRegex(
                    core.HomeError, "native edit conflicts with shared setting provider.model; preserve"
                ):
                    native_config.sync(self.home, selected_only=True)
                self.assertEqual((self.home / FILE).read_bytes(), edited)
            (self.home / FILE).write_bytes(good)
            commit(self.home)
            native_config.sync(self.home, selected_only=True)
            self.assertEqual((self.home / FILE).read_bytes(), good)
            self.assertIn("max_turns = 5", self.text())

    def test_workspace_write_maps_scoped_file_tools_and_preserves_native(self):
        (self.home / FILE).write_text(self.text() + '\n[limits]\nmax_turns = 5\n')
        commit(self.home)
        native_config.configure_shared(self.home, {"permission": "read-only"})
        commit(self.home)
        native_config.configure_shared(self.home, {"permission": "workspace-write"})
        text = self.text()
        self.assertIn('tools = ["read_file", "write_file", "edit_file", "list_dir", "search_files"]', text)
        self.assertIn('workspace = "workspace"', text)
        self.assertNotIn("run_command", text)
        self.assertNotIn("approval =", text)
        self.assertIn("max_turns = 5", text)
        commit(self.home)
        (self.home / FILE).write_text(text.replace('"write_file", ', ""))
        commit(self.home)
        with self.assertRaises(core.HomeError):  # native edit of an owned key conflicts
            native_config.sync(self.home, selected_only=True)
        (self.home / FILE).write_text(text)
        commit(self.home)
        native_config.configure_shared(self.home, {})
        self.assertNotIn("grants", self.text())
        self.assertIn("max_turns = 5", self.text())

    def test_external_runtimes_still_reject_workspace_write(self):
        for runtime in ("claude", "codex", "opencode", "pi"):
            home = core.create("ext-" + runtime, runtime, Path(self.tmp.name) / runtime)
            with self.assertRaises(core.HomeError):
                native_config.configure_shared(home, {"permission": "workspace-write"})

    def test_native_agent_id_limit_checked_before_mutation(self):
        ok = core.create("a" * 64, "soulsteads", Path(self.tmp.name) / "ok")
        self.assertIn('id = "' + "a" * 64 + '"', (ok / FILE).read_text())
        long = "a" * 65
        with self.assertRaises(core.HomeError):
            core.create(long, "soulsteads", Path(self.tmp.name) / "bad")
        self.assertFalse((Path(self.tmp.name) / "bad").exists())
        ext = core.create(long, "claude", Path(self.tmp.name) / "ext")
        before = subprocess.run(["git", "-C", str(ext), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
        with self.assertRaises(core.HomeError):
            core.configure(ext, "soulsteads")
        after = subprocess.run(["git", "-C", str(ext), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertFalse((ext / FILE).exists())
        self.assertEqual(json.loads((ext / "soulsteads.json").read_text())["runtime"], "claude")

    def test_unsupported_mappings_fail_closed(self):
        for config in ({"provider": "p", "model": "m"}, {"permission": "unrestricted"},
                       {"mcp": {"Bad_Name": {"command": "x"}}}):
            with self.assertRaises(core.HomeError):
                native_config.configure_shared(self.home, config)

    def test_project_launch_is_refused(self):
        from soulsteads.launch import prepare_launch
        with self.assertRaises(core.HomeError):
            prepare_launch(self.home, "soulsteads", self.tmp.name)


if __name__ == "__main__":
    unittest.main()

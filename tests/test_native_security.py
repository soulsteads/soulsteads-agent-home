"""Security regressions for native configuration ownership and publication."""

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, native_config, publication


class NativeSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = core.create("native-security", "opencode", path=self.root / "home")

    def test_removed_managed_instruction_is_not_silently_readded(self):
        config = self.home / "opencode.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["instructions"].remove("SOUL.md")
        config.write_text(json.dumps(value), encoding="utf-8")
        pi_before = (self.home / ".pi/APPEND_SYSTEM.md").read_bytes()
        codex_before = (self.home / ".codex/config.toml").read_bytes()

        with self.assertRaises(core.HomeError):
            native_config.sync(self.home)

        self.assertNotIn("SOUL.md", json.loads(config.read_text())["instructions"])
        self.assertEqual((self.home / ".pi/APPEND_SYSTEM.md").read_bytes(), pi_before)
        self.assertEqual((self.home / ".codex/config.toml").read_bytes(), codex_before)

        value.pop("instructions")
        config.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(core.HomeError):
            native_config.sync(self.home)
        self.assertNotIn("instructions", json.loads(config.read_text()))

    def test_replaced_managed_instruction_is_refused(self):
        config = self.home / "opencode.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["instructions"].remove("SOUL.md")
        value["instructions"].append("workspace/replacement.md")
        config.write_text(json.dumps(value), encoding="utf-8")
        edited = config.read_bytes()

        with self.assertRaises(core.HomeError):
            native_config.sync(self.home)

        self.assertEqual(config.read_bytes(), edited)

    def test_legacy_unmanaged_instructions_can_be_adopted(self):
        manifest = core.load(self.home)
        manifest.pop("managed_files")
        (self.home / "soulsteads.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        config = self.home / "opencode.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["instructions"].remove("SOUL.md")
        value["instructions"].append("workspace/user-added.md")
        config.write_text(json.dumps(value), encoding="utf-8")

        native_config.sync(self.home)

        instructions = json.loads(config.read_text(encoding="utf-8"))["instructions"]
        self.assertIn("SOUL.md", instructions)
        self.assertIn("workspace/user-added.md", instructions)

    def test_generic_sync_refuses_removed_managed_authorization_leaf(self):
        hindsight = {
            "url": "https://localhost:8000/mcp/bank/",
            "token_env": "SYNTHETIC_HINDSIGHT_TOKEN",
        }
        native_config.sync(self.home, hindsight=hindsight)
        config = self.home / ".pi/mcp.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        del value["mcpServers"]["hindsight"]["headers"]["Authorization"]
        config.write_text(json.dumps(value), encoding="utf-8")
        edited = config.read_bytes()

        with self.assertRaises(core.HomeError):
            native_config.sync(self.home)

        self.assertEqual(config.read_bytes(), edited)

    def test_generic_sync_refuses_removed_managed_mcp_server(self):
        hindsight = {
            "url": "https://localhost:8000/mcp/bank/",
            "token_env": "SYNTHETIC_HINDSIGHT_TOKEN",
        }
        native_config.sync(self.home, hindsight=hindsight)
        config = self.home / ".pi/mcp.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["mcpServers"].pop("hindsight")
        config.write_text(json.dumps(value), encoding="utf-8")
        edited = config.read_bytes()

        with self.assertRaises(core.HomeError):
            native_config.sync(self.home)

        self.assertEqual(config.read_bytes(), edited)

    def test_sync_recreates_missing_managed_mcp_json_file(self):
        hindsight = {
            "url": "https://localhost:8000/mcp/bank/",
            "token_env": "SYNTHETIC_HINDSIGHT_TOKEN",
        }
        native_config.sync(self.home, hindsight=hindsight)
        config = self.home / ".pi/mcp.json"
        config.unlink()

        native_config.sync(self.home)

        value = json.loads(config.read_text(encoding="utf-8"))
        self.assertIn("hindsight", value["mcpServers"])

    def test_sync_recreates_missing_native_output_directory(self):
        pi = self.home / ".pi"
        for path in pi.iterdir():
            path.unlink()
        pi.rmdir()

        native_config.sync(self.home)

        self.assertTrue((pi / "settings.json").is_file())
        self.assertTrue((pi / "APPEND_SYSTEM.md").is_file())

    def test_identity_leaf_symlink_raced_after_load_is_not_read(self):
        source = self.home / "SOUL.md"
        sentinel = self.root / "outside-sentinel.txt"
        sentinel.write_text("EXTERNAL_NATIVE_SOURCE_SENTINEL", encoding="utf-8")
        original_read = native_config._read
        swapped = False

        def swap_then_read(path, *args, **kwargs):
            nonlocal swapped
            if Path(path) == source and not swapped:
                source.unlink()
                source.symlink_to(sentinel)
                swapped = True
            return original_read(path, *args, **kwargs)

        caught = None
        with patch.object(native_config, "_read", new=swap_then_read):
            try:
                native_config.sync(self.home)
            except core.HomeError as exc:
                caught = exc

        leaked = [
            str(path.relative_to(self.home))
            for path in (
                self.home / ".pi/APPEND_SYSTEM.md",
                self.home / ".codex/config.toml",
            )
            if "EXTERNAL_NATIVE_SOURCE_SENTINEL" in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(swapped)
        self.assertEqual(leaked, [], f"external source copied into {leaked}")
        self.assertIsNotNone(caught, "raced identity symlink must fail closed")

    def test_identity_replacement_after_preflight_aborts_before_publication(self):
        source = self.home / "SOUL.md"
        source.write_text("Changed source before planning\n", encoding="utf-8")
        sentinel = self.root / "late-outside-sentinel.txt"
        sentinel.write_text("LATE_EXTERNAL_NATIVE_SENTINEL", encoding="utf-8")
        generated = (
            self.home / ".pi/APPEND_SYSTEM.md",
            self.home / ".codex/config.toml",
        )
        before = {path: path.read_bytes() for path in generated}
        original_read = native_config._read
        swapped = False

        def swap_after_plan_read(path, *args, **kwargs):
            nonlocal swapped
            result = original_read(path, *args, **kwargs)
            if Path(path) == self.home / ".codex/config.toml" and not swapped:
                source.unlink()
                source.symlink_to(sentinel)
                swapped = True
            return result

        caught = None
        with patch.object(native_config, "_read", new=swap_after_plan_read):
            try:
                native_config.sync(self.home)
            except core.HomeError as exc:
                caught = exc

        self.assertTrue(swapped)
        self.assertIsNotNone(caught, "changed source snapshot must abort sync")
        self.assertEqual({path: path.read_bytes() for path in generated}, before)
        self.assertTrue(source.is_symlink())
        self.assertEqual(
            sentinel.read_text(encoding="utf-8"), "LATE_EXTERNAL_NATIVE_SENTINEL"
        )

    def test_input_content_hash_detects_same_identity_change(self):
        source = self.home / "SOUL.md"
        source.write_text("Changed identity content\n", encoding="utf-8")
        generated = (
            self.home / ".pi/APPEND_SYSTEM.md",
            self.home / ".codex/config.toml",
        )
        before = {path: path.read_bytes() for path in generated}
        original_read = native_config._read
        swapped = False

        def stat_identity(info):
            return (
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_uid,
                info.st_nlink,
                info.st_size,
            )

        def change_source_after_plan(path, *args, **kwargs):
            nonlocal swapped
            result = original_read(path, *args, **kwargs)
            if Path(path) == self.home / ".codex/config.toml" and not swapped:
                source.write_text("Mutated identity content\n", encoding="utf-8")
                swapped = True
            return result

        caught = None
        with (
            patch.object(native_config, "_identity", new=stat_identity),
            patch.object(native_config, "_read", new=change_source_after_plan),
        ):
            try:
                native_config.sync(self.home)
            except core.HomeError as exc:
                caught = exc

        self.assertTrue(swapped)
        self.assertIsNotNone(caught, "changed input bytes must abort sync")
        self.assertEqual({path: path.read_bytes() for path in generated}, before)

    def test_read_rejects_static_source_symlink(self):
        source = self.home / "SOUL.md"
        sentinel = self.root / "symlink-sentinel.txt"
        sentinel.write_text("STATIC_SYMLINK_SENTINEL", encoding="utf-8")
        source.unlink()
        source.symlink_to(sentinel)

        with self.assertRaises(core.HomeError):
            native_config._read(source)

    def test_read_rejects_hardlinked_source_leaf(self):
        source = self.home / "SOUL.md"
        outside = self.root / "hardlink-sentinel.txt"
        outside.write_text("STATIC_HARDLINK_SENTINEL", encoding="utf-8")
        source.unlink()
        os.link(outside, source)

        with self.assertRaises(core.HomeError):
            native_config._read(source)

    def test_read_rejects_special_source_leaf(self):
        source = self.home / "SOUL.md"
        source.unlink()
        with socket.socket(socket.AF_UNIX) as special:
            special.bind(str(source))
            with self.assertRaises(core.HomeError):
                native_config._read(source)

    def test_swapped_output_parent_is_not_followed_for_publication(self):
        (self.home / "SOUL.md").write_text(
            "Changed output identity\n", encoding="utf-8"
        )
        outside = self.root / "outside-pi"
        outside.mkdir()
        parent = self.home / ".pi"
        moved = self.home / ".pi-raced"
        original_write = publication.publish_file
        swapped = False

        def swap_parent_then_write(parent_fd, name, text, **kwargs):
            nonlocal swapped
            if not swapped:
                parent.rename(moved)
                parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_write(parent_fd, name, text, **kwargs)

        caught = None
        with patch.object(publication, "publish_file", new=swap_parent_then_write):
            try:
                native_config.sync(self.home)
            except core.HomeError as exc:
                caught = exc

        self.assertTrue(swapped)
        self.assertTrue(parent.is_symlink())
        self.assertEqual(parent.readlink(), outside)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertIsNotNone(caught, "replaced output parent must abort sync")

    def test_swapped_home_root_is_not_followed_for_publication(self):
        (self.home / "SOUL.md").write_text("Changed root identity\n", encoding="utf-8")
        outside = self.root / "outside-home"
        outside.mkdir()
        (outside / ".pi").mkdir()
        (outside / ".codex").mkdir()
        moved = self.root / "moved-home"
        original_write = publication.publish_file
        swapped = False

        def swap_root_then_write(parent_fd, name, text, **kwargs):
            nonlocal swapped
            if not swapped:
                self.home.rename(moved)
                self.home.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_write(parent_fd, name, text, **kwargs)

        caught = None
        with patch.object(publication, "publish_file", new=swap_root_then_write):
            try:
                native_config.sync(self.home)
            except core.HomeError as exc:
                caught = exc

        self.assertTrue(swapped)
        self.assertTrue(self.home.is_symlink())
        self.assertEqual(self.home.readlink(), outside)
        self.assertEqual(list((outside / ".pi").iterdir()), [])
        self.assertEqual(list((outside / ".codex").iterdir()), [])
        self.assertFalse((outside / "soulsteads.json").exists())
        self.assertIsNotNone(caught, "replaced home root must abort sync")

    def test_manifest_edit_after_validation_is_not_overwritten(self):
        manifest_path = self.home / "soulsteads.json"
        original_validate = core._validate_home
        changed = False

        def validate_then_edit(home, *args, **kwargs):
            nonlocal changed
            value = original_validate(home, *args, **kwargs)
            if not changed:
                current = json.loads(manifest_path.read_text(encoding="utf-8"))
                current["owner_note"] = "KEEP_CONCURRENT_OWNER_NOTE"
                temporary = manifest_path.with_name(".soulsteads-raced.json")
                temporary.write_text(json.dumps(current), encoding="utf-8")
                temporary.replace(manifest_path)
                changed = True
            return value

        with (
            patch.object(core, "_validate_home", new=validate_then_edit),
            self.assertRaises(core.HomeError),
        ):
            native_config.sync(self.home)

        self.assertTrue(changed)
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8"))["owner_note"],
            "KEEP_CONCURRENT_OWNER_NOTE",
        )

    def test_manifest_leaf_symlink_raced_after_is_file_is_not_read(self):
        manifest_path = self.home / "soulsteads.json"
        outside = self.root / "outside-manifest.json"
        outside.write_bytes(manifest_path.read_bytes())
        original_is_file = Path.is_file
        original_read_text = Path.read_text
        swapped = False
        external_reads = 0

        def race_after_file_check(path):
            nonlocal swapped
            result = original_is_file(path)
            if Path(path) == manifest_path and result and not swapped:
                manifest_path.unlink()
                manifest_path.symlink_to(outside)
                swapped = True
            return result

        def record_external_read(path, *args, **kwargs):
            nonlocal external_reads
            if Path(path) == manifest_path and manifest_path.is_symlink():
                external_reads += 1
            return original_read_text(path, *args, **kwargs)

        with (
            patch.object(Path, "is_file", new=race_after_file_check),
            patch.object(Path, "read_text", new=record_external_read),
            self.assertRaises(core.HomeError),
        ):
            native_config.sync(self.home)

        self.assertTrue(swapped)
        self.assertTrue(manifest_path.is_symlink())
        self.assertEqual(external_reads, 0, "raced manifest target must not be read")


if __name__ == "__main__":
    unittest.main()

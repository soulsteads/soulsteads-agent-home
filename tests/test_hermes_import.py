"""Hermes import acceptance uses synthetic profiles only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, hermes_import
from soulsteads.hermes_import import ImportErrorSafe, import_profile, inspect_source


class HermesImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "hermes"
        self.source.mkdir(mode=0o700)
        (self.source / "SOUL.md").write_text("# Synthetic identity\n")
        (self.source / "config.yaml").write_text("{}\n")
        self.destination = self.root / "new-home"

    def test_hindsight_configuration_is_detected_without_disclosing_details(self):
        directory = self.source / "hindsight"
        directory.mkdir(mode=0o700)
        (directory / "config.json").write_text(
            json.dumps(
                {
                    "mode": "local_external",
                    "api_url": "https://memory.example.invalid",
                    "bank_id": "synthetic-private-bank",
                    "apiKey": "synthetic-private-key",
                }
            )
        )
        (self.source / "config.yaml").write_text("memory:\n  provider: hindsight\n")
        report = inspect_source("helper", self.source)
        self.assertEqual(report["hindsight"]["status"], "configuration-detected")
        self.assertIn("hindsight/config.json", report["private_files"])
        self.assertNotIn("synthetic-private", json.dumps(report))
        self.assertNotIn("memory.example.invalid", json.dumps(report))
        self.assertTrue(any("Hindsight" in item for item in report["unsupported"]))

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_hindsight_source_reference_is_private_and_unchanged(self):
        directory = self.source / "hindsight"
        directory.mkdir(mode=0o700)
        raw = b'{"mode":"local_external","bank_id":"synthetic-bank","apiKey":"synthetic-key"}\n'
        (directory / "config.json").write_bytes(raw)
        import_profile("helper", self.source, path=self.destination, allow_partial=True)
        target = self.destination / ".runtime/hermes/hindsight/config.json"
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual((directory / "config.json").read_bytes(), raw)
        self.assertNotIn(
            "hindsight",
            subprocess.check_output(
                ["git", "-C", str(self.destination), "ls-files"], text=True
            ),
        )

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_import_converts_portable_skills_for_every_harness(self):
        skill = self.skill("category/sample", "sample")
        (skill / "SKILL.md").write_bytes(
            b"---\nname: sample\ndescription: Synthetic portable skill\nplatforms: [linux, macos]\nversion: 1\n---\n# Instructions\nRead references/guide.md.\n"
        )
        (skill / "references").mkdir(mode=0o700)
        (skill / "references/guide.md").write_bytes(b"Synthetic supporting bytes\r\n")
        for runtime in ("opencode", "pi", "claude", "codex"):
            with self.subTest(runtime=runtime):
                target = self.root / runtime
                import_profile("helper", self.source, path=target, runtime=runtime)
                converted = (target / "skills/sample/SKILL.md").read_bytes()
                self.assertIn(b'name: "sample"', converted)
                self.assertNotIn(b"platforms:", converted)
                self.assertNotIn(b"version:", converted)
                self.assertTrue(
                    converted.endswith(b"# Instructions\nRead references/guide.md.\n")
                )
                for alias in (".agents/skills", ".claude/skills"):
                    self.assertEqual(
                        (target / alias / "sample/SKILL.md").read_bytes(), converted
                    )
                    self.assertEqual(
                        (target / alias / "sample/references/guide.md").read_bytes(),
                        b"Synthetic supporting bytes\r\n",
                    )
                self.assertIn(
                    "Native skill portability", (target / "AGENTS.md").read_text()
                )

    def test_hindsight_reference_rejects_invalid_or_ambiguous_json(self):
        directory = self.source / "hindsight"
        directory.mkdir(mode=0o700)
        path = directory / "config.json"
        for raw in (
            b'{"apiKey":"sensitive-synthetic-value",}',
            b'{"bank_id":"a","bank_id":"sensitive-synthetic-value"}',
            b"[]",
        ):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                with self.assertRaises(ImportErrorSafe) as error:
                    inspect_source("helper", self.source)
                self.assertNotIn("sensitive-synthetic-value", str(error.exception))

    def test_inspection_is_read_only_and_metadata_only(self):
        before = sorted(self.root.rglob("*"))
        report = inspect_source("helper", self.source, runtime="pi")
        self.assertIn("SOUL.md", report["files"])
        self.assertNotIn("Synthetic identity", json.dumps(report))
        self.assertEqual(sorted(self.root.rglob("*")), before)
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_public_reports_hide_absolute_paths_and_receipt_preserves_provenance(self):
        workspace = self.root / "workspace"
        workspace.mkdir(mode=0o700)
        (workspace / "USER.md").write_text("Synthetic workspace fallback")
        inspected = inspect_source("helper", self.source, workspace=workspace)
        applied = import_profile(
            "helper", self.source, workspace=workspace, path=self.destination
        )
        for report in (inspected, applied):
            serialized = json.dumps(report)
            self.assertNotIn(str(self.source), serialized)
            self.assertNotIn(str(workspace), serialized)
            self.assertNotIn(str(self.destination), serialized)
        self.assertEqual(applied["name"], "helper")
        self.assertEqual(applied["profile"], "default")
        receipt_path = self.destination / ".runtime/hermes/IMPORT-RECEIPT.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["source_path"], str(self.source))
        self.assertEqual(receipt["destination_path"], str(self.destination))
        self.assertEqual(receipt["name"], "helper")
        self.assertEqual(receipt["profile"], "default")
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        tracked = subprocess.check_output(
            ["git", "-C", str(self.destination), "ls-files"], text=True
        )
        self.assertNotIn(".runtime/", tracked)

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_apply_creates_standard_home_without_touching_source(self):
        memories = self.source / "memories"
        memories.mkdir(mode=0o700)
        (memories / "MEMORY.md").write_bytes(b"# Synthetic memory\r\n")
        originals = {
            p.relative_to(self.source): p.read_bytes()
            for p in self.source.rglob("*")
            if p.is_file()
        }
        result = import_profile(
            "helper", self.source, runtime="codex", path=self.destination
        )
        self.assertEqual(result["status"], "imported")
        self.assertEqual(core.load(self.destination)["runtime"], "codex")
        self.assertEqual(
            (self.destination / "SOUL.md").read_bytes(), originals[Path("SOUL.md")]
        )
        self.assertEqual(
            (self.destination / "MEMORY.md").read_bytes(), b"# Synthetic memory\r\n"
        )
        tracked = subprocess.check_output(
            ["git", "-C", str(self.destination), "ls-files"], text=True
        )
        self.assertNotIn(".runtime/", tracked)
        self.assertFalse((self.destination / "skills/starter").exists())
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", str(self.destination), "remote"], text=True
            ),
            "",
        )
        for relative, data in originals.items():
            self.assertEqual((self.source / relative).read_bytes(), data)
        self.assertFalse((self.source / ".git").exists())
        self.assertEqual(os.stat(self.destination).st_mode & 0o777, 0o700)

    def skill(self, relative, name, description="Synthetic skill"):
        directory = self.source / "skills" / relative
        directory.mkdir(parents=True, mode=0o700)
        for parent in (directory, *directory.parents):
            if parent == self.source:
                break
            parent.chmod(0o700)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n# Synthetic instructions\n"
        )
        return directory

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_enabled_skills_and_nested_disable_filters(self):
        parent = self.skill("category/parent", "parent-skill")
        (parent / "reference.txt").write_text("Synthetic reference")
        child = self.skill("category/parent/nested", "nested-skill")
        (child / "hidden.txt").write_text("DO_NOT_COPY_DISABLED")
        self.skill("category/off", "other-disabled")
        self.skill("category/essential", "hermes-agent")
        (self.source / "config.yaml").write_text(
            "skills:\n  disabled: [nested-skill, hermes-agent]\n"
            "  platform_disabled:\n    matrix: [other-disabled]\n"
        )
        report = inspect_source("helper", self.source, platform="matrix")
        self.assertEqual(report["skills"], ["hermes-agent", "parent-skill"])
        self.assertNotIn("DO_NOT_COPY_DISABLED", json.dumps(report))
        import_profile("helper", self.source, path=self.destination, platform="matrix")
        self.assertTrue(
            (self.destination / "skills/parent-skill/reference.txt").is_file()
        )
        self.assertFalse((self.destination / "skills/parent-skill/nested").exists())
        self.assertTrue((self.destination / "skills/hermes-agent/SKILL.md").is_file())
        self.assertFalse((self.destination / "skills/other-disabled").exists())

    def test_duplicate_skill_ids_refused_even_with_allow_partial(self):
        self.skill("one", "duplicate")
        self.skill("two", "duplicate")
        with self.assertRaises(ImportErrorSafe):
            import_profile(
                "helper", self.source, path=self.destination, allow_partial=True
            )
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_external_discovery_requires_partial_acknowledgement(self):
        (self.source / "config.yaml").write_text(
            "skills:\n  external_dirs: [/not/authorized]\n"
        )
        report = inspect_source("helper", self.source)
        self.assertTrue(report["unsupported"])
        self.assertNotIn("/not/authorized", json.dumps(report))
        with self.assertRaises(ImportErrorSafe):
            import_profile("helper", self.source, path=self.destination)
        import_profile("helper", self.source, path=self.destination, allow_partial=True)
        self.assertTrue(self.destination.is_dir())

    def test_target_cannot_be_inside_any_part_of_source_home(self):
        named = self.source / "profiles" / "named"
        named.mkdir(parents=True, mode=0o700)
        named.parent.chmod(0o700)
        (named / "config.yaml").write_text("{}\n")
        with self.assertRaises(ImportErrorSafe):
            import_profile(
                "helper", self.source, profile="named", path=self.source / "another"
            )
        self.assertFalse((self.source / "another").exists())

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_private_config_and_opt_in_env_never_enter_git_or_stdout(self):
        marker = "SYNTHETIC_VALUE_NOT_A_REAL_CREDENTIAL"
        (self.source / "config.yaml").write_text(f"model:\n  api_key: {marker}\n")
        (self.source / ".env").write_text(f"EXAMPLE_TOKEN={marker}\n")
        report = inspect_source("helper", self.source)
        self.assertNotIn(marker, json.dumps(report))
        self.assertNotIn(".env", report["private_files"])
        result = import_profile(
            "helper",
            self.source,
            path=self.destination,
            allow_partial=True,
            include_secrets=True,
        )
        self.assertNotIn(marker, json.dumps(result))
        reference = self.destination / ".runtime/hermes"
        self.assertIn(marker, (reference / "config.yaml").read_text())
        self.assertIn(marker, (reference / ".env").read_text())
        tracked = subprocess.check_output(
            [
                "git",
                "-C",
                str(self.destination),
                "ls-tree",
                "-r",
                "--name-only",
                "HEAD",
            ],
            text=True,
        )
        self.assertNotIn(".runtime/", tracked)
        self.assertFalse((self.destination / ".env").exists())
        self.assertEqual((reference / ".env").stat().st_mode & 0o777, 0o600)

    def test_yaml_errors_never_echo_source_values(self):
        for raw in (
            "plugins: {}\nplugins: {secret: NEVER_ECHO_ME}\n",
            "key: [NEVER_ECHO_ME\n",
            "key: !!python/object:NEVER_ECHO_ME {}\n",
            "a: &alias [x]\nb: *alias\n",
        ):
            with self.subTest(raw=raw):
                (self.source / "config.yaml").write_text(raw)
                with self.assertRaises(ImportErrorSafe) as caught:
                    import_profile(
                        "helper", self.source, path=self.destination, allow_partial=True
                    )
                self.assertNotIn("NEVER_ECHO_ME", str(caught.exception))
                self.assertFalse(self.destination.exists())

    def test_links_hardlinks_special_and_oversized_files_are_refused(self):
        soul = self.source / "SOUL.md"
        soul.unlink()
        sentinel = self.root / "sentinel"
        sentinel.write_text("KEEP_EXTERNAL_BYTES")
        cases = [
            lambda: soul.symlink_to(sentinel),
            lambda: os.link(sentinel, soul),
            lambda: os.mkfifo(soul),
            lambda: soul.write_bytes(b"x" * (2 * 1024 * 1024 + 1)),
        ]
        for make in cases:
            with self.subTest(case=make):
                make()
                with self.assertRaises(ImportErrorSafe):
                    import_profile(
                        "helper", self.source, path=self.destination, allow_partial=True
                    )
                self.assertFalse(self.destination.exists())
                self.assertEqual(sentinel.read_text(), "KEEP_EXTERNAL_BYTES")
                soul.unlink()

    def test_ancestor_symlink_and_existing_destination_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ImportErrorSafe):
            inspect_source("helper", alias)
        self.destination.mkdir()
        (self.destination / "keep").write_text("UNCHANGED")
        with self.assertRaises(ImportErrorSafe):
            import_profile("helper", self.source, path=self.destination)
        self.assertEqual((self.destination / "keep").read_text(), "UNCHANGED")

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_workspace_fallback_and_memory_precedence(self):
        workspace = self.root / "workspace"
        workspace.mkdir(mode=0o700)
        (workspace / "SOUL.md").write_text("Not selected")
        (workspace / "USER.md").write_text("Workspace fallback")
        (workspace / "AGENTS.md").write_text("# Synthetic project rules\n")
        memories = self.source / "memories"
        memories.mkdir(mode=0o700)
        (memories / "USER.md").write_text("Profile memory user wins")
        import_profile(
            "helper", self.source, workspace=workspace, path=self.destination
        )
        self.assertEqual(
            (self.destination / "SOUL.md").read_text(), "# Synthetic identity\n"
        )
        self.assertEqual(
            (self.destination / "USER.md").read_text(), "Profile memory user wins"
        )
        self.assertIn(
            "read SOUL.md, USER.md, and MEMORY.md",
            (self.destination / "AGENTS.md").read_text(),
        )
        self.assertEqual(
            (self.destination / ".runtime/hermes/AGENTS.md").read_text(),
            "# Synthetic project rules\n",
        )
        receipt = json.loads(
            (self.destination / ".runtime/hermes/IMPORT-RECEIPT.json").read_text()
        )
        self.assertIn("AGENTS.md", receipt["private_files"])

    def test_source_change_or_optional_file_appearance_prevents_publication(self):

        original = core.create
        for filename in ("SOUL.md", "USER.md"):
            with self.subTest(filename=filename):

                def changed(*args, filename=filename, **kwargs):
                    home = original(*args, **kwargs)
                    (self.source / filename).write_text("Changed after snapshot")
                    return home

                with (
                    patch.object(core, "create", side_effect=changed),
                    self.assertRaises(ImportErrorSafe),
                ):
                    import_profile("helper", self.source, path=self.destination)
                self.assertFalse(self.destination.exists())
                self.assertFalse(list(self.root.glob(".hermes-import-*")))

    def test_concurrent_destination_is_never_overwritten(self):

        original = hermes_import._publish

        def collision(*args):
            self.destination.mkdir()
            (self.destination / "sentinel").write_text("CONCURRENT_WINNER")
            return original(*args)

        with (
            patch.object(hermes_import, "_publish", side_effect=collision),
            self.assertRaises(ImportErrorSafe),
        ):
            import_profile("helper", self.source, path=self.destination)
        self.assertEqual(
            (self.destination / "sentinel").read_text(), "CONCURRENT_WINNER"
        )
        self.assertFalse(list(self.root.glob(".hermes-import-*")))

    @unittest.skipUnless(
        sys.platform == "linux", "Atomic import publication requires Linux"
    )
    def test_final_destination_rebind_is_not_reported_as_success(self):

        original = hermes_import._publish
        retained = self.root / "retained-published-home"

        def rebound(*args):
            original(*args)
            self.destination.rename(retained)
            self.destination.mkdir()
            (self.destination / "sentinel").write_text("REPLACEMENT")

        with (
            patch.object(hermes_import, "_publish", side_effect=rebound),
            self.assertRaises(ImportErrorSafe) as caught,
        ):
            import_profile("helper", self.source, path=self.destination)
        self.assertIn("published", str(caught.exception))
        self.assertTrue((retained / "soulsteads.json").is_file())
        self.assertEqual((self.destination / "sentinel").read_text(), "REPLACEMENT")

    def test_missing_named_profile_never_falls_back_to_default(self):
        with self.assertRaises(ImportErrorSafe):
            inspect_source("helper", self.source, profile="missing", runtime="pi")


if __name__ == "__main__":
    unittest.main()

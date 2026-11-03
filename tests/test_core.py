from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads.core import (
    HomeError,
    _write_private,
    commit,
    configure,
    create,
    history,
    install_skill,
    load,
    revert,
)

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class CoreTests(unittest.TestCase):
    def test_configure_replaces_hardlinked_manifest_without_mutating_external_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            home = create("ada", "opencode", base=root / "agents")
            manifest = home / "soulsteads.json"
            external = root / "external.json"
            original = manifest.read_bytes()
            os.link(manifest, external)

            with self.assertRaises(HomeError):
                configure(home, "codex")

            self.assertEqual(external.read_bytes(), original)
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(load(home)["runtime"], "opencode")

    def test_write_private_preserves_preexisting_colliding_temp_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            target = Path(temporary) / "private.txt"
            collision = Path(temporary) / ".private.txt.collision.tmp"
            collision.write_bytes(b"pre-existing")

            with (
                patch("soulsteads.core.secrets.token_hex", return_value="collision"),
                self.assertRaises(FileExistsError),
            ):
                _write_private(target, "replacement")

            self.assertEqual(collision.read_bytes(), b"pre-existing")
            self.assertFalse(target.exists())

    def test_install_skill_preserves_source_executable_files_as_owner_executable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            home = create("ada", "opencode", base=root / "agents")
            source = root / "source"
            scripts = source / "scripts"
            scripts.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: executable-skill\ndescription: A useful skill.\n---\n",
                encoding="utf-8",
            )
            check = scripts / "check.sh"
            check.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            check.chmod(0o700)

            installed = install_skill(home, source)

            self.assertEqual(
                stat.S_IMODE((installed / "scripts/check.sh").stat().st_mode), 0o700
            )

    def test_install_skill_requires_safe_valid_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            home = create("ada", "opencode", base=root / "agents")
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\nname: useful-skill\ndescription: A useful skill.\n---\n\n# Skill\n",
                encoding="utf-8",
            )
            installed = install_skill(home, source)
            self.assertEqual(installed, home / "skills" / "useful-skill")
            self.assertTrue((installed / "SKILL.md").is_file())
            with self.assertRaises(HomeError):
                install_skill(home, source)
            unsafe = root / "unsafe"
            unsafe.mkdir()
            (unsafe / "SKILL.md").write_text(
                "---\nname: bad\ndescription: x\n---\n", encoding="utf-8"
            )
            (unsafe / ".env").write_text("no", encoding="utf-8")
            with self.assertRaises(HomeError):
                install_skill(home, unsafe)

    def test_commit_uses_safe_allowlist_and_restore_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            home = create("ada", "opencode", base=Path(temporary) / "agents")
            initial = subprocess.run(
                ["git", "-C", str(home), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            original_soul = (home / "SOUL.md").read_text(encoding="utf-8")
            (home / "SOUL.md").write_text("# Soul\n\nChanged.\n", encoding="utf-8")
            change = commit(home, "Change soul")
            self.assertIn("Change soul", history(home))
            (home / "credentials").write_text("do-not-stage", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(home), "add", "-f", "credentials"], check=True
            )
            with self.assertRaises(HomeError):
                commit(home, "must fail")
            subprocess.run(
                ["git", "-C", str(home), "reset", "--", "credentials"], check=True
            )
            (home / "credentials").unlink()
            restored = revert(home, initial)
            self.assertNotEqual(restored, change)
            self.assertIn("Restore", history(home))
            self.assertEqual(
                (home / "SOUL.md").read_text(encoding="utf-8"), original_soul
            )

    def test_load_reads_only_standalone_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            home = create("ada", "opencode", base=Path(temporary) / "agents")
            manifest = load(home)
            self.assertEqual(
                {key: manifest[key] for key in ("schema_version", "name", "runtime")},
                {"schema_version": 1, "name": "ada", "runtime": "opencode"},
            )
            self.assertIn("managed_files", manifest)
            (home / "soulsteads.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(HomeError):
                load(home)

    def test_create_rejects_existing_target_invalid_name_and_nested_git(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            root = Path(temporary)
            with self.assertRaises(HomeError):
                create("Not a slug", "opencode", base=root)
            existing = root / "agents" / "ada"
            existing.mkdir(parents=True)
            with self.assertRaises(HomeError):
                create("ada", "opencode", base=root / "agents")
            nested = root / "parent"
            nested.mkdir()
            subprocess.run(["git", "-C", str(nested), "init", "--quiet"], check=True)
            with self.assertRaises(HomeError):
                create("ada", "opencode", base=nested / "agents")

    def test_create_makes_private_git_home_with_generic_identity_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            base = Path(temporary) / "agents"
            home = create("ada", "opencode", base=base)
            self.assertEqual(home, base / "ada")
            self.assertTrue((home / ".git").is_dir())
            self.assertEqual(
                json.loads((home / "soulsteads.json").read_text())["name"], "ada"
            )
            for relative in (
                "USER.md",
                "SOUL.md",
                "AGENTS.md",
                "MEMORY.md",
                "workspace/.gitkeep",
            ):
                self.assertTrue((home / relative).is_file(), relative)
            self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((home / "USER.md").stat().st_mode), 0o600)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(home), "log", "-1", "--format=%an <%ae>"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "Soulsteads <soulsteads@localhost>",
            )


if __name__ == "__main__":
    unittest.main()

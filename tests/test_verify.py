import json
import tempfile
import unittest
from pathlib import Path

from soulsteads import cli, core


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        core.create("helper", "opencode", path=self.home, with_skills=False)

    def test_offline_verification_is_available_and_not_activation_proof(self):
        self.assertIn("verify", cli.parser().format_help())
        from soulsteads.verification import verify_home

        before = {
            p.relative_to(self.home): p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file()
        }
        report = verify_home(self.home)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["activation_ready"])
        self.assertEqual(report["scope"], "offline-structural")
        self.assertEqual(
            before,
            {
                p.relative_to(self.home): p.read_bytes()
                for p in self.home.rglob("*")
                if p.is_file()
            },
        )
        self.assertNotIn(str(self.home), json.dumps(report))

    def test_missing_identity_and_malformed_config_fail_without_content_leaks(self):
        from soulsteads.verification import verify_home

        (self.home / "USER.md").unlink()
        (self.home / "opencode.json").write_text('{"private@example.invalid": }')
        report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("private@example.invalid", json.dumps(report))

    def test_tracked_private_material_fails_even_when_ignored(self):
        from soulsteads.verification import verify_home

        private = self.home / ".runtime/hermes"
        private.mkdir(parents=True)
        (private / "config.yaml").write_text("secret: synthetic-secret")
        core._git(self.home, "add", "-f", ".runtime/hermes/config.yaml")
        report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any(f["id"] == "private-storage" for f in report["findings"]))
        self.assertNotIn("synthetic-secret", json.dumps(report))

    def test_skill_alias_retargeting_is_refused(self):
        from soulsteads.verification import verify_home

        alias = self.home / ".agents/skills"
        alias.unlink()
        alias.symlink_to("/tmp")
        report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")

    def test_invalid_skill_metadata_fails_without_echoing_skill_name(self):
        from soulsteads.verification import verify_home

        skill = self.home / "skills/private-person"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: other\ndescription: example\n---\n")
        report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("private-person", json.dumps(report))

    def test_hermes_only_skill_references_need_review(self):
        from soulsteads.verification import verify_home

        skill = self.home / "skills/helper"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: helper\ndescription: example\n---\nCall skill_view to read a skill.\n"
        )
        report = verify_home(self.home)
        self.assertEqual(report["status"], "needs-review")
        self.assertTrue(any(f["id"] == "skill-portability" for f in report["findings"]))

    def test_narrow_runtime_ignore_does_not_cover_env_or_receipt(self):
        from soulsteads.verification import verify_home

        (self.home / ".gitignore").write_text(".runtime/hermes/config.yaml\n")
        (self.home / ".env").write_text("SYNTHETIC=only\n")
        receipt = self.home / ".runtime/hermes/IMPORT-RECEIPT.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({"status": "imported", "unsupported": []}))
        report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("SYNTHETIC", json.dumps(report))
        self.assertIn("private-storage", {item["id"] for item in report["findings"]})

    def test_selectively_unignored_nested_private_files_fail(self):
        from soulsteads.verification import verify_home

        for relative in (
            ".runtime/hermes/IMPORT-RECEIPT.json",
            ".runtime/hermes/hindsight/config.json",
            "skills/sample/.env",
        ):
            with self.subTest(private_file=relative):
                (self.home / ".gitignore").write_text(
                    ".env\nauth.json\ncredentials*\nsecrets*\n*.key\n*.pem\n"
                    ".runtime/hermes/config.yaml\n!" + relative + "\n"
                )
                path = self.home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.endswith("IMPORT-RECEIPT.json"):
                    path.write_text(
                        json.dumps({"status": "imported", "unsupported": []})
                    )
                else:
                    path.write_text("SYNTHETIC-PRIVATE-FIXTURE")
                if relative.startswith("skills/"):
                    (path.parent / "SKILL.md").write_text(
                        "---\nname: sample\ndescription: Example\n---\nBody\n"
                    )
                report = verify_home(self.home)
                self.assertEqual(report["status"], "failed")
                self.assertNotIn("SYNTHETIC-PRIVATE-FIXTURE", json.dumps(report))
                self.assertIn(
                    "private-storage", {item["id"] for item in report["findings"]}
                )
                path.unlink()

    def test_standard_private_ignores_accept_present_private_state(self):
        from soulsteads.verification import verify_home

        (self.home / ".env").write_text("SYNTHETIC=only\n")
        receipt = self.home / ".runtime/hermes/IMPORT-RECEIPT.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({"status": "imported", "unsupported": []}))
        config = receipt.parent / "hindsight/config.json"
        config.parent.mkdir()
        config.write_text("SYNTHETIC-PRIVATE-FIXTURE")
        report = verify_home(self.home)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["activation_ready"])
        self.assertNotIn("SYNTHETIC", json.dumps(report))

    def test_duplicate_json_and_nonstandard_constants_fail(self):
        from soulsteads.verification import verify_home

        for text in ('{"a": 1, "a": 2}', '{"a": NaN}', "[]"):
            with self.subTest(text=text):
                (self.home / "opencode.json").write_text(text)
                self.assertEqual(verify_home(self.home)["status"], "failed")

    def test_skills_reject_hardlinks_symlinks_and_oversized_files(self):
        import os

        from soulsteads.hermes_import import MAX_FILE
        from soulsteads.verification import verify_home

        leaf = self.home / "skills/asset"
        outside = Path(self.tmp.name) / "outside"
        outside.write_bytes(b"example")
        for kind in ("link", "hardlink", "large"):
            with self.subTest(kind=kind):
                if kind == "link":
                    leaf.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, leaf)
                else:
                    leaf.write_bytes(b"x" * (MAX_FILE + 1))
                self.assertEqual(verify_home(self.home)["status"], "failed")
                leaf.unlink()

    def test_import_receipt_is_not_activation_proof_and_pending_work_is_reported(self):
        from soulsteads.verification import verify_home

        private = self.home / ".runtime/hermes"
        private.mkdir(parents=True)
        receipt = private / "IMPORT-RECEIPT.json"
        receipt.write_text(
            json.dumps(
                {
                    "status": "imported",
                    "activation_ready": False,
                    "unsupported": ["private@example.invalid"],
                }
            )
        )
        report = verify_home(self.home)
        self.assertEqual(report["status"], "needs-review")
        self.assertNotIn("private@example.invalid", json.dumps(report))

    def test_verification_requires_skill_documents(self):
        from soulsteads.verification import verify_home

        (self.home / "skills/incomplete").mkdir()
        self.assertEqual(verify_home(self.home)["status"], "failed")

    def test_without_yaml_skill_validation_is_explicitly_incomplete(self):
        import subprocess
        import sys

        skill = self.home / "skills/helper"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: helper\ndescription: example\n---\n"
        )
        result = subprocess.run(
            [sys.executable, "-S", "-m", "soulsteads", "verify", str(self.home)],
            capture_output=True,
            check=False,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "needs-review")

    def test_deep_json_is_a_sanitized_failure(self):
        from soulsteads.verification import verify_home

        (self.home / "opencode.json").write_text("[" * 20000 + "0" + "]" * 20000)
        self.assertEqual(verify_home(self.home)["status"], "failed")

    def test_final_root_rebinding_is_not_reported_as_success(self):
        from unittest.mock import patch

        from soulsteads.hermes_import import Snapshot
        from soulsteads.verification import verify_home

        original = Snapshot.verify

        def replaced(snapshot):
            self.home.rename(self.home.with_name("retained"))
            self.home.mkdir()
            original(snapshot)

        with patch.object(Snapshot, "verify", replaced):
            self.assertEqual(verify_home(self.home)["status"], "failed")

    def test_cli_failed_check_returns_json_without_home_path(self):
        import subprocess
        import sys

        (self.home / "MEMORY.md").unlink()
        result = subprocess.run(
            [sys.executable, "-m", "soulsteads", "verify", str(self.home)],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.assertNotIn(str(self.home), result.stdout + result.stderr)

    def test_unsupported_platform_is_a_sanitized_failure(self):
        from unittest.mock import patch

        from soulsteads.verification import verify_home

        with patch("os.name", "nt"):
            report = verify_home(self.home)
        self.assertEqual(report["status"], "failed")

"""Exercise review and apply through the installed CLI's entry point."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from soulsteads import core


class SkillReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = core.create(
            "sample",
            "pi",
            path=Path(self.temp.name) / "home",
            learning={"mode": "propose", "skills": []},
        )
        self.skill = self.home / "skills/starter/SKILL.md"
        self.header = b"---\r\nname: starter\r\ndescription: snow\r\n---\r\n"
        self.skill.write_bytes(self.header + b"Use snow.\r\n")
        self.edit = {
            "reason": "Verified in rehearsal",
            "before": "snow",
            "after": "rain",
        }

    def invoke(self, *options, edit=None, name="starter", home=None, cwd=None):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "soulsteads",
                "skill",
                "review",
                str(home or self.home),
                name,
                *options,
            ],
            input=json.dumps(self.edit if edit is None else edit),
            check=False,
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
            capture_output=True,
            text=True,
        )

    def preview(self):
        preview = self.invoke()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        return json.loads(preview.stdout)

    def test_preview_apply_and_native_aliases(self):
        previous = self.skill.read_bytes()
        head = core._git(self.home, "rev-parse", "HEAD").stdout
        report = self.preview()
        self.assertEqual(report["status"], "preview")
        self.assertEqual(report["reason"], self.edit["reason"])
        self.assertIn("+Use rain.\r\n", report["diff"])
        self.assertEqual(self.skill.read_bytes(), previous)
        applied = self.invoke("--apply", report["review_id"])
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(json.loads(applied.stdout)["status"], "applied")
        for tree in ("skills", ".agents/skills", ".claude/skills"):
            self.assertEqual(
                (self.home / tree / "starter/SKILL.md").read_bytes(),
                self.header + b"Use rain.\r\n",
            )
        self.assertEqual(core._git(self.home, "rev-parse", "HEAD").stdout, head)
        self.assertNotEqual(self.invoke("--apply", report["review_id"]).returncode, 0)

    def test_review_binds_input_target_home_and_original_bytes(self):
        identifier = self.preview()["review_id"]
        other = core.create(
            "other",
            "pi",
            path=self.home.parent / "other",
            learning={"mode": "propose", "skills": []},
        )
        (other / "skills/starter/SKILL.md").write_bytes(self.skill.read_bytes())
        self.assertNotEqual(
            self.invoke("--apply", identifier, home=other).returncode, 0
        )
        for key in ("reason", "after"):
            changed = {**self.edit, key: "different"}
            self.assertNotEqual(
                self.invoke("--apply", identifier, edit=changed).returncode, 0
            )
        original = self.skill.read_bytes() + b"Concurrent edit.\n"
        self.skill.write_bytes(original)
        self.assertNotEqual(self.invoke("--apply", identifier).returncode, 0)
        self.assertEqual(self.skill.read_bytes(), original)

    def test_only_unique_body_edits_to_real_skill_files(self):
        for before in ("description: snow", "absent"):
            self.assertNotEqual(
                self.invoke(edit={**self.edit, "before": before}).returncode, 0
            )
        self.skill.write_bytes(self.header + b"snow snow\n")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertNotEqual(self.invoke(name="../starter").returncode, 0)
        self.skill.write_bytes(self.header + b"snow\n")
        os.link(self.skill, self.home.parent / "outside")
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_competing_reviews_preserve_one_winner_and_other_edits(self):
        change = {**self.edit, "after": "ice"}
        first = self.preview()["review_id"]
        second = json.loads(self.invoke(edit=change).stdout)["review_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            runs = [
                pool.submit(self.invoke, "--apply", first),
                pool.submit(self.invoke, "--apply", second, edit=change),
            ]
            codes = [run.result().returncode for run in runs]
        self.assertEqual(sorted(codes), [0, 1])
        winner = b"rain" if codes[0] == 0 else b"ice"
        self.assertEqual(
            self.skill.read_bytes(), self.header + b"Use " + winner + b".\r\n"
        )

    def test_policy_change_invalidates_review(self):
        from soulsteads.native_config import sync

        identifier = self.preview()["review_id"]
        sync(self.home, learning={"mode": "off", "skills": []})
        result = self.invoke("--apply", identifier)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("review ID differs", result.stderr)

    def test_bundled_skill_and_active_learning_policy_advertise_review(self):
        from soulsteads.native_config import sync

        command = "soulsteads skill review HOME SKILL"
        self.assertIn(
            command, (self.home / "skills/skill-maintenance/SKILL.md").read_text()
        )
        self.assertIn(command, (self.home / "LEARNING.md").read_text())
        for path in (".pi/APPEND_SYSTEM.md", ".codex/config.toml"):
            self.assertIn(command, (self.home / path).read_text())
        self.assertIn("@LEARNING.md", (self.home / "CLAUDE.md").read_text())
        self.assertIn(
            "LEARNING.md",
            json.loads((self.home / "opencode.json").read_text())["instructions"],
        )
        sync(self.home, learning={"mode": "off", "skills": []})
        self.assertNotIn(command, (self.home / "LEARNING.md").read_text())

    def test_cwd_anchor_accepts_same_review_and_keeps_private_directory_checks(self):
        identifier = self.preview()["review_id"]
        selected = {"home": ".", "cwd": self.home}
        preview = self.invoke(**selected)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["review_id"], identifier)
        self.skill.parent.chmod(0o777)
        self.assertNotEqual(
            self.invoke("--apply", identifier, **selected).returncode, 0
        )
        self.skill.parent.chmod(0o700)
        self.assertEqual(self.invoke("--apply", identifier, **selected).returncode, 0)

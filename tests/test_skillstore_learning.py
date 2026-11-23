"""Configuration and failure boundaries for Skillstore-backed learning."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, skillstore
from soulsteads.native_config import sync


class SkillstoreLearningTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = core.create(
            "sample",
            "pi",
            path=self.root / "home",
            learning={"mode": "propose", "skills": []},
        )
        self.skill = self.home / "skills/starter/SKILL.md"
        self.original = (
            "---\nname: starter\ndescription: shipping\n---\nRecord weight.\n"
        )
        self.skill.write_text(self.original)
        self.change = {
            "reason": "Use SI units",
            "before": "Record weight.",
            "after": "Record weight in grams.",
        }

    def bind(self, *, auto_submit=True):
        release = {"digest": "sha256:" + hashlib.sha256(b"base").hexdigest()}
        with patch.object(
            skillstore, "_stage", return_value=(None, self.original, release)
        ):
            return skillstore.bind(
                self.home,
                "starter",
                "1.0.0",
                store=str(self.root / "registry"),
                actor="agent",
                token_env=None,
                auto_submit=auto_submit,
            )

    def test_learning_and_submission_configuration(self):
        with patch.object(skillstore, "_command") as remote:
            self.assertEqual(
                skillstore.learn(self.home, "starter", self.change)["status"], "preview"
            )
            self.assertEqual(self.bind(auto_submit=False)["auto_submit"], False)
            result = skillstore.learn(self.home, "starter", self.change)
            self.assertEqual(result["status"], "registry-preview")
            sync(self.home, learning={"mode": "off", "skills": []})
            with self.assertRaisesRegex(core.HomeError, "enable a Home learning mode"):
                skillstore.learn(self.home, "starter", self.change)
            skillstore.bind(
                self.home,
                "starter",
                None,
                store=None,
                actor=None,
                token_env=None,
                auto_submit=False,
            )
            sync(self.home, learning={"mode": "propose", "skills": []})
            self.assertEqual(
                skillstore.learn(self.home, "starter", self.change)["status"], "preview"
            )
            remote.assert_not_called()
        self.assertEqual(self.skill.read_text(), self.original)

    def test_changed_local_file_is_not_submitted(self):
        self.bind()
        changed = self.original + "A local note.\n"
        self.skill.write_text(changed)
        with patch.object(skillstore, "_command") as remote:
            with self.assertRaisesRegex(core.HomeError, "local SKILL.md differs"):
                skillstore.learn(self.home, "starter", self.change)
            remote.assert_not_called()
        self.assertEqual(self.skill.read_text(), changed)

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

    def bind(self, *, auto_submit=True, reviewer_actor=None):
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
                reviewer_actor=reviewer_actor,
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

    def test_auto_requires_scope_and_distinct_reviewer(self):
        sync(self.home, learning={"mode": "auto", "skills": ["skill-maintenance"]})
        with patch.object(skillstore, "_command") as remote:
            with self.assertRaisesRegex(core.HomeError, "outside this Home"):
                skillstore.learn(self.home, "starter", self.change)
            sync(self.home, learning={"mode": "auto", "skills": ["starter"]})
            self.assertIn(
                "Automatically improve only", (self.home / "LEARNING.md").read_text()
            )
            self.bind()
            with self.assertRaisesRegex(core.HomeError, "separate service reviewer"):
                skillstore.learn(self.home, "starter", self.change)
            with self.assertRaisesRegex(
                ValueError, "separate Skillstore service reviewer"
            ):
                self.bind(reviewer_actor="agent")
            remote.assert_not_called()
        self.assertEqual(self.skill.read_text(), self.original)

    def test_retry_adopts_exact_accepted_release_without_another_decision(self):
        self.bind(reviewer_actor="reviewer")
        sync(self.home, learning={"mode": "auto", "skills": ["starter"]})
        updated = self.original.replace(self.change["before"], self.change["after"])
        files = {"SKILL.md": {"mode": "644", "sha256": skillstore._sha(updated)}}
        digest = skillstore._package_digest(files)
        base = {
            "digest": "sha256:" + hashlib.sha256(b"base").hexdigest(),
            "files": files,
        }
        staging = self.root / "candidate"
        staging.mkdir()
        proposal = {
            "id": "p1-example",
            "skill": "starter",
            "base_version": "1.0.0",
            "digest": digest,
            "status": "open",
            "submitted_by": {"actor": "agent", "kind": "agent"},
        }
        release = {
            "name": "starter",
            "version": "1.0.1",
            "status": "reviewed",
            "digest": digest,
            "files": files,
            "provenance": {
                "origin": {"proposal_id": proposal["id"], "base_version": "1.0.0"}
            },
            "review": {
                "reviewer": "reviewer",
                "reviewer_kind": "service",
                "digest_reviewed": digest,
            },
        }
        remote_calls = []

        def registry(_binding, *args, reviewer=False):
            remote_calls.append((args, reviewer))
            if args[0] == "proposals":
                return [proposal.copy()]
            if args == ("inspect", "starter"):
                return {"latest_reviewed": "1.0.0"}
            if args[0] == "decide":
                self.assertTrue(reviewer)
                self.assertEqual(
                    args[1:5], (proposal["id"], "accept", "--version", "1.0.1")
                )
                proposal.update(
                    status="accepted", decision={"released_version": "1.0.1"}
                )
                raise core.HomeError("simulated lost decision response")
            if args == ("inspect", "starter", "--version", "1.0.1"):
                return release
            self.fail(f"unexpected registry call: {args}")

        with (
            patch.object(
                skillstore, "_stage", return_value=(staging, self.original, base)
            ),
            patch.object(skillstore, "_command", side_effect=registry),
        ):
            with self.assertRaisesRegex(
                core.HomeError, "p1-example.*lost decision response"
            ):
                skillstore.learn(self.home, "starter", self.change)
            self.assertEqual(self.skill.read_text(), self.original)
            self.assertEqual(
                skillstore.learn(self.home, "starter", self.change)["version"], "1.0.1"
            )
        self.assertEqual(self.skill.read_text(), updated)
        self.assertEqual(sum(args[0] == "decide" for args, _ in remote_calls), 1)

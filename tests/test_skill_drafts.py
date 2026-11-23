import json
import os
from pathlib import Path
import tempfile
import unittest

from soulsteads import core


class SkillDraftTests(unittest.TestCase):
    def setUp(self):
        from soulsteads import skill_drafts

        self.drafts = skill_drafts
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name).resolve()
        self.home = core.create("helper", "pi", path=self.root / "helper")
        self.target = self.home / "skills/starter/SKILL.md"
        self.before = self.target.read_bytes()
        self.after = self.before + b"\nVerify the selected result before handoff.\n"
        self.candidate = self.root / "candidate.md"
        self.candidate.write_bytes(self.after)

    def propose(self):
        return self.drafts.propose(self.home, "starter", self.candidate, "Clarify handoff")

    def test_review_apply_and_undo_one_skill_with_no_git_side_effect(self):
        original_head = core._git(self.home, "rev-parse", "HEAD").stdout
        draft = self.propose()
        self.assertEqual(draft["status"], "proposed")
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(core._git(self.home, "status", "--porcelain").stdout, "")
        path = self.home / ".runtime/skill-drafts" / (draft["id"] + ".json")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        shown = self.drafts.show(self.home, draft["id"])
        self.assertIn("+Verify the selected result before handoff.", shown["diff"])
        self.candidate.unlink()  # Application uses the reviewed, saved bytes.
        unrelated = self.target.with_name("notes.md")
        unrelated.write_text("leave alone", encoding="utf-8")
        self.assertEqual(self.drafts.apply(self.home, draft["id"])["status"], "applied")
        self.assertEqual(self.target.read_bytes(), self.after)
        self.assertEqual(self.drafts.undo(self.home, draft["id"])["status"], "undone")
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "leave alone")
        self.assertEqual(core._git(self.home, "rev-parse", "HEAD").stdout, original_head)

    def test_apply_and_undo_refuse_worktree_drift(self):
        draft_id = self.propose()["id"]
        edit = self.before + b"Operator correction.\n"
        self.target.write_bytes(edit)
        with self.assertRaisesRegex(core.HomeError, "stale"):
            self.drafts.apply(self.home, draft_id)
        self.assertEqual(self.target.read_bytes(), edit)
        self.target.write_bytes(self.before)
        self.drafts.apply(self.home, draft_id)
        self.target.write_bytes(edit)
        with self.assertRaisesRegex(core.HomeError, "stale"):
            self.drafts.undo(self.home, draft_id)
        self.assertEqual(self.target.read_bytes(), edit)

    def test_tampered_draft_cannot_apply(self):
        draft_id = self.propose()["id"]
        path = self.home / ".runtime/skill-drafts" / (draft_id + ".json")
        record = json.loads(path.read_text(encoding="utf-8"))
        record["candidate"] += "Different edit.\n"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(core.HomeError, "draft"):
            self.drafts.apply(self.home, draft_id)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_reject_metadata_changes_and_traversal(self):
        self.candidate.write_bytes(self.after.replace(b"name: starter", b"name: other"))
        with self.assertRaisesRegex(core.HomeError, "frontmatter"):
            self.propose()
        with self.assertRaises(core.HomeError):
            self.drafts.propose(self.home, "../starter", self.candidate, "Reason")
        with self.assertRaises(core.HomeError):
            self.drafts.show(self.home, "../draft")
        self.assertFalse((self.home / ".runtime/skill-drafts").exists())

    def test_refuses_hardlinked_target_without_altering_other_file(self):
        draft_id = self.propose()["id"]
        other = self.root / "hardlink.md"
        os.link(self.target, other)
        with self.assertRaises(core.HomeError):
            self.drafts.apply(self.home, draft_id)
        self.assertEqual(other.read_bytes(), self.before)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_refuses_symlinked_draft_parent_without_writing_outside_home(self):
        outside = self.root / "outside"
        outside.mkdir(mode=0o700)
        (self.home / ".runtime").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(core.HomeError):
            self.propose()
        self.assertEqual(list(outside.iterdir()), [])

    def test_rejects_oversize_candidate(self):
        self.candidate.write_bytes(self.before + b"a" * (128 * 1024))
        with self.assertRaises(core.HomeError):
            self.propose()
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_undo_after_commit_can_be_committed_without_rewriting_history(self):
        draft_id = self.propose()["id"]
        self.drafts.apply(self.home, draft_id)
        applied = core.commit(self.home, "Reviewed skill improvement")
        self.drafts.undo(self.home, draft_id)
        self.assertEqual(core._git(self.home, "diff", "--cached", "--name-only").stdout, "")
        core.commit(self.home, "Restore previous skill")
        self.assertEqual(core._git(self.home, "rev-parse", "HEAD^").stdout.strip(), applied)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_show_of_missing_draft_does_not_create_runtime_state(self):
        with self.assertRaises(core.HomeError):
            self.drafts.show(self.home, "0" * 64)
        self.assertFalse((self.home / ".runtime").exists())

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from soulsteads import core
from soulsteads.cli import main


class ImprovementCLITests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name).resolve()
        self.home = core.create("helper", "pi", path=self.root / "helper")

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_hindsight_status_does_not_echo_endpoint(self):
        status, _, err = self.call("config", str(self.home), "--hindsight-url",
                                   "https://hidden.example/mcp/private-bank/")
        self.assertEqual((status, err), (0, ""))
        status, out, err = self.call("config", str(self.home), "--hindsight-policy-json",
                                   '{"recall_budget":"mid","recall_max_tokens":800}')
        self.assertEqual((status, err), (0, ""))
        self.assertNotIn("private-bank", out)
        status, _, err = self.call("config", str(self.home), "--hindsight-policy-json",
                                   '{"recall_context_chars":256}')
        self.assertEqual((status, err), (0, ""))
        status, out, err = self.call("config", str(self.home), "--hindsight-status")
        self.assertEqual((status, err), (0, ""))
        self.assertNotIn("hidden.example", out)
        self.assertNotIn("private-bank", out)
        report = json.loads(out)
        self.assertEqual(report["automatic_callbacks"], {"recall": False, "retain": False})
        self.assertEqual(report["callback_limits"]["recall_budget"], "mid")
        self.assertEqual(report["callback_limits"]["recall_max_tokens"], 800)
        self.assertEqual(report["callback_limits"]["recall_context_chars"], 256)
        self.assertFalse(report["connection_verified"])

    def test_bad_hindsight_policy_does_not_change_manifest(self):
        manifest = self.home / "soulsteads.json"
        original = manifest.read_bytes()
        for policy in ('null', '{"unknown":1}', '{"recall_max_tokens":true}',
                       '{"recall_max_tokens":NaN}', '{"request_timeout_seconds":4}'):
            with self.subTest(policy=policy):
                status, out, _ = self.call("config", str(self.home), "--hindsight-policy-json", policy)
                self.assertEqual((status, out), (1, ""))
                self.assertEqual(manifest.read_bytes(), original)

    def test_skill_proposal_leaves_canonical_file_unchanged_until_apply(self):
        active = self.home / "skills/starter/SKILL.md"
        before = active.read_bytes()
        draft = self.root / "candidate.md"
        draft.write_bytes(before + b"\nVerify the selected result before handoff.\n")
        status, out, err = self.call("skill", "propose", str(self.home), "starter", str(draft),
                                     "--reason", "Handoff omitted a verification step.")
        self.assertEqual((status, err), (0, ""))
        draft_id = json.loads(out)["id"]
        self.assertEqual(active.read_bytes(), before)
        status, out, err = self.call("skill", "show", str(self.home), draft_id)
        self.assertEqual((status, err), (0, ""))
        self.assertIn("+Verify the selected result before handoff.", out)
        status, _, err = self.call("skill", "apply", str(self.home), draft_id)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(active.read_bytes(), draft.read_bytes())
        status, _, err = self.call("skill", "undo", str(self.home), draft_id)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(active.read_bytes(), before)

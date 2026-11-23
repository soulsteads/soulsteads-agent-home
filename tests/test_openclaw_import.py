import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from soulsteads import core
from soulsteads.cli import main


class OpenClawImportTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name).resolve()
        self.source = self.root / 'workspace'
        self.source.mkdir(mode=0o700)
        self.target = self.root / 'helper'
        for name in ('AGENTS.md', 'SOUL.md', 'USER.md', 'MEMORY.md', 'IDENTITY.md'):
            (self.source / name).write_text(f'private fixture {name}\n', encoding='utf-8')
        (self.source / '.env').write_text('PRIVATE_ENV_SENTINEL\n', encoding='utf-8')
        (self.source / 'memory').mkdir(mode=0o700)
        (self.source / 'memory' / 'daily.md').write_text('private daily log', encoding='utf-8')

    def call(self, *flags):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = main(['import-openclaw', 'helper', '--workspace', str(self.source),
                           '--path', str(self.target), '--runtime', 'pi', *flags])
        return result, out.getvalue(), err.getvalue()

    def test_inspect_reports_selection_without_opening_or_printing_excluded_content(self):
        (self.source / 'MEMORY.md').unlink()
        (self.source / 'MEMORY.md').symlink_to(self.root / 'missing')
        status, out, err = self.call()
        self.assertEqual((status, err), (0, ''))
        report = json.loads(out)
        self.assertEqual(report['files'], ['AGENTS.md', 'SOUL.md', 'USER.md'])
        self.assertEqual(report['identity'], 'not-transferred')
        self.assertEqual(report['curated_memory'], 'not-selected')
        self.assertFalse(report['activation_ready'])
        self.assertNotIn(str(self.root), out)
        self.assertNotIn('private fixture', out)
        self.assertFalse(self.target.exists())

    @unittest.skipUnless(sys.platform.startswith('linux'), 'apply uses Linux no-replace publication')
    def test_apply_creates_new_home_with_selected_files_and_no_runtime_state(self):
        status, out, err = self.call('--apply', '--include-memory')
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(json.loads(out)['status'], 'imported')
        self.assertEqual(core.load(self.target)['learning']['mode'], 'off')
        for name in ('SOUL.md', 'USER.md', 'MEMORY.md'):
            self.assertEqual((self.target / name).read_bytes(), (self.source / name).read_bytes())
        self.assertIn('private fixture AGENTS.md', (self.target / 'AGENTS.md').read_text())
        self.assertTrue((self.target / '.runtime/openclaw/IMPORT-RECEIPT.json').is_file())
        for name in ('memory', 'IDENTITY.md', '.env'):
            self.assertFalse((self.target / name).exists())
        self.assertEqual(core._git(self.target, 'status', '--porcelain').stdout, '')
        self.assertTrue((self.source / 'memory/daily.md').exists())

    def test_apply_refuses_existing_destination(self):
        self.target.mkdir(mode=0o700)
        keep = self.target / 'keep'
        keep.write_bytes(b'kept')
        status, out, err = self.call('--apply')
        self.assertNotEqual(status, 0)
        self.assertEqual(out, '')
        self.assertIn('destination already exists', err)
        self.assertEqual(keep.read_bytes(), b'kept')

    def test_selected_document_cannot_be_a_link(self):
        (self.source / 'SOUL.md').unlink()
        (self.source / 'SOUL.md').symlink_to(self.source / '.env')
        status, out, err = self.call('--apply')
        self.assertNotEqual(status, 0)
        self.assertEqual(out, '')
        self.assertNotIn('PRIVATE_ENV_SENTINEL', err)
        self.assertFalse(self.target.exists())

    def test_apply_refuses_destination_inside_source(self):
        self.target = self.source / 'nested' / 'helper'
        status, out, err = self.call('--apply')
        self.assertNotEqual(status, 0)
        self.assertEqual(out, '')
        self.assertIn('must not overlap', err)
        self.assertFalse(self.target.parent.exists())

    def test_document_only_inspects_without_yaml_dependency(self):
        with patch('soulsteads.hermes_import.require_yaml', side_effect=AssertionError):
            status, _, err = self.call()
        self.assertEqual((status, err), (0, ''))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'apply uses Linux no-replace publication')
    def test_imports_only_requested_workspace_skills(self):
        (self.source / 'skills').mkdir(mode=0o700)
        for name in ('choose', 'skip'):
            skill = self.source / 'skills' / name
            skill.mkdir(mode=0o700)
            (skill / 'SKILL.md').write_text(
                f'---\nname: {name}\ndescription: A fixture skill\n---\n\n# {name}\n', encoding='utf-8'
            )
            helper = skill / 'helper.sh'
            helper.write_text('exit 99\n', encoding='utf-8')
            helper.chmod(0o700)
        status, out, err = self.call('--apply', '--skill', 'choose')
        self.assertEqual((status, err), (0, ''))
        self.assertEqual(json.loads(out)['skills'], ['choose'])
        self.assertEqual(sorted(p.name for p in (self.target / 'skills').iterdir() if p.is_dir()), ['choose'])
        self.assertEqual((self.target / 'skills/choose/helper.sh').read_bytes(), b'exit 99\n')
        self.assertTrue(os.access(self.target / 'skills/choose/helper.sh', os.X_OK))

    def test_conditional_skill_is_not_silently_made_unconditional(self):
        (self.source / 'skills').mkdir(mode=0o700)
        skill = self.source / 'skills' / 'guarded'
        skill.mkdir(mode=0o700)
        (skill / 'SKILL.md').write_text(
            '---\nname: guarded\ndescription: Conditional fixture\n'
            'metadata: {openclaw: {requires: {env: [PRIVATE_ENV_SENTINEL]}}}\n---\n\nBody\n',
            encoding='utf-8',
        )
        status, out, err = self.call('--skill', 'guarded')
        self.assertNotEqual(status, 0)
        self.assertEqual(out, '')
        self.assertIn('OpenClaw-specific skill metadata', err)
        self.assertNotIn('PRIVATE_ENV_SENTINEL', err)

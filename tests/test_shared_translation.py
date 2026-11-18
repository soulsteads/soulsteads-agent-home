"""Canonical translation must preserve native edits and use normal recovery."""
import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch
from soulsteads import core, native_config
from soulsteads.cli import main

class SharedTranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.home = core.create('helper', 'codex', path=Path(self.temp.name)/'home')

    def codex(self):
        return tomllib.loads((self.home/'.codex/config.toml').read_text())

    def test_configure_sync_and_update_preserve_native_settings(self):
        path=self.home/'.codex/config.toml'
        path.write_text(path.read_text()+'\n# keep this native comment\n[custom]\nvalue = 42\n')
        config={'model':'model-a','provider':'native-provider','mcp':{'fixture':{'command':'echo','args':['hello']}}}
        native_config.configure_shared(self.home,config)
        self.assertEqual(self.codex()['model'],'model-a')
        self.assertEqual(self.codex()['custom']['value'],42)
        self.assertIn('# keep this native comment',path.read_text())
        self.assertEqual(self.codex()['mcp_servers']['fixture']['command'],'echo')
        config['model']='model-b'
        native_config.configure_shared(self.home,config)
        self.assertEqual(self.codex()['model'],'model-b')
        before=path.read_bytes(); native_config.sync(self.home)
        self.assertEqual(before,path.read_bytes())
        native_config.configure_shared(self.home,{})
        self.assertNotIn('model',self.codex())
        self.assertNotIn('fixture',self.codex().get('mcp_servers',{}))
        self.assertEqual(self.codex()['custom']['value'],42)

    def test_conflict_refuses_before_identity_or_manifest_changes(self):
        native_config.configure_shared(self.home,{'model':'model-a'})
        p=self.home/'.codex/config.toml'
        p.write_text(p.read_text().replace('model-a','native-edit'))
        (self.home/'SOUL.md').write_text('Changed canonical identity\n')
        manifest=(self.home/'soulsteads.json').read_bytes()
        before=p.read_bytes()
        with self.assertRaisesRegex(core.HomeError,'native edit conflicts'):
            native_config.sync(self.home)
        self.assertEqual(p.read_bytes(),before)
        self.assertEqual((self.home/'soulsteads.json').read_bytes(),manifest)

    def test_equal_native_values_are_not_adopted_or_removed(self):
        p=self.home/'.codex/config.toml'
        p.write_text(p.read_text()+'\nmodel = "existing"\n')
        native_config.configure_shared(self.home,{'model':'existing'})
        native_config.configure_shared(self.home,{})
        self.assertEqual(self.codex()['model'],'existing')
        with self.assertRaisesRegex(core.HomeError,'existing native'):
            native_config.configure_shared(self.home,{'model':'other'})

    def test_manifest_failure_rolls_back_shared_publication_before_retry(self):
        from soulsteads import publication

        native = self.home / '.codex/config.toml'
        manifest = self.home / 'soulsteads.json'
        before_native = native.read_bytes()
        before_manifest = manifest.read_bytes()
        publish = publication.publish_file

        def fail_final_manifest(parent_fd, name, *args, **kwargs):
            if name == 'soulsteads.json':
                raise OSError('synthetic final manifest failure')
            return publish(parent_fd, name, *args, **kwargs)

        with (
            patch('soulsteads.publication.publish_file', side_effect=fail_final_manifest),
            self.assertRaisesRegex(core.HomeError, 'rolled back'),
        ):
            native_config.configure_shared(self.home, {'model': 'm'})
        self.assertEqual(native.read_bytes(), before_native)
        self.assertEqual(manifest.read_bytes(), before_manifest)

        native_config.configure_shared(self.home, {'model': 'm'})
        self.assertEqual(self.codex()['model'], 'm')
        native_config.configure_shared(self.home, {})
        self.assertNotIn('model', self.codex())

    def test_runtime_selection_translates_and_restore_is_new_commit(self):
        native_config.configure_shared(self.home,{'model':'shared-model'})
        first=core.commit(self.home,'Canonical model')
        core.configure(self.home,'pi')
        self.assertEqual(json.loads((self.home/'.pi/settings.json').read_text())['defaultModel'],'shared-model')
        second=core.commit(self.home,'Switch harness')
        restored=core.revert(self.home,first)
        self.assertNotEqual(restored,first)
        self.assertNotEqual(restored,second)
        self.assertEqual(core.load(self.home)['runtime'],'codex')
        self.assertEqual(self.codex()['model'],'shared-model')

    def test_unsupported_mapping_and_secrets_do_not_mutate(self):
        native_config.configure_shared(self.home,{'permission':'read-only'})
        self.assertEqual(self.codex()['sandbox_mode'],'read-only')
        self.assertEqual(self.codex()['approval_policy'],'never')
        before=(self.home/'soulsteads.json').read_bytes()
        with self.assertRaisesRegex(core.HomeError,'unsupported|supports only'):
            native_config.sync(self.home,'claude')
        self.assertEqual((self.home/'soulsteads.json').read_bytes(),before)
        with self.assertRaisesRegex(core.HomeError,'credential'):
            native_config.configure_shared(self.home,{'mcp':{'fixture':{'command':'example','args':['--token','literal']}}})
        with self.assertRaisesRegex(core.HomeError,'Hindsight'):
            native_config.configure_shared(self.home,{'mcp':{'hindsight':{'command':'example'}}})

    def test_real_launch_refreshes_canonical_files(self):
        native_config.configure_shared(self.home,{'model':'first'})
        manifest=core.load(self.home);manifest['shared_settings']['model']='second'
        (self.home/'soulsteads.json').write_text(json.dumps(manifest))
        def launch(*args,**kwargs):
            self.assertEqual(self.codex()['model'],'second')
            self.assertIn('model="second"',args[0])
            return type('Result',(),{'returncode':0})()
        # Patch only harness invocation; Git validation subprocesses stay real.
        import soulsteads.cli as cli
        original=cli.subprocess.run
        def run(argv,*args,**kwargs):
            return launch(argv,*args,**kwargs) if argv[0]=='codex' else original(argv,*args,**kwargs)
        with patch.object(cli.subprocess,'run',side_effect=run):
            self.assertEqual(main(['run',str(self.home)]),0)

    def test_unchanged_launch_and_sync_keep_learning_home_clean_for_selection(self):
        native_config.sync(
            self.home,
            learning={"mode": "propose", "skills": []},
            shared_settings={"model": "same-model"},
        )
        core.commit(self.home, "Configured learning and shared model")
        manifest = self.home / "soulsteads.json"
        before = manifest.read_bytes()
        before_inode = manifest.stat().st_ino
        import soulsteads.cli as cli
        original = cli.subprocess.run
        launches = []

        def run(argv, *args, **kwargs):
            if argv[0] == "codex":
                launches.append(argv)
                return type("Result", (), {"returncode": 0})()
            return original(argv, *args, **kwargs)

        # Exercise the real launch preparation; only the native harness is stubbed.
        with patch.object(cli.subprocess, "run", side_effect=run):
            self.assertEqual(main(["run", str(self.home)]), 0)
        self.assertEqual(len(launches), 1)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(manifest.stat().st_ino, before_inode)
        for selected_only in (False, True, False):
            native_config.sync(self.home, selected_only=selected_only)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(manifest.stat().st_ino, before_inode)
            self.assertEqual(core._git(self.home, "status", "--porcelain").stdout, "")
        core.configure(self.home, "opencode")
        self.assertEqual(core.load(self.home)["runtime"], "opencode")
        self.assertEqual(core.load(self.home)["learning"]["mode"], "propose")
        self.assertEqual(json.loads((self.home / "opencode.json").read_text())["model"], "same-model")

    def test_launch_sets_pwd_to_the_launch_directory(self):
        import soulsteads.cli as cli
        seen = []

        def run(argv, *args, **kwargs):
            if argv[0] == "codex":
                seen.append((kwargs["cwd"], kwargs["env"].get("PWD")))
                return type("Result", (), {"returncode": 0})()
            return original(argv, *args, **kwargs)

        original = cli.subprocess.run
        with patch.dict(os.environ, {"PWD": "/stale/caller/directory"}):
            with patch.object(cli.subprocess, "run", side_effect=run):
                self.assertEqual(main(["run", str(self.home)]), 0)
        self.assertEqual(seen, [(str(self.home), str(self.home))])

    def test_exec_overrides_and_project_context_use_subcommand_parser(self):
        import contextlib
        import io
        native_config.configure_shared(self.home,{'model':'sample-model','mcp':{'proof':{'command':'echo','args':['ok']}}})
        project=Path(self.temp.name)/'project';project.mkdir()
        (self.home/'SOUL.md').write_text('PRIVATE_IDENTITY_CANARY')
        for project_args in ([],['--project',str(project),'--allow-context-in-argv']):
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                result=main(['run',str(self.home),*project_args,'--dry-run','--','exec','--json','hello'])
            self.assertEqual(result,0)
            self.assertNotIn('PRIVATE_IDENTITY_CANARY',output.getvalue())
            launch=json.loads(output.getvalue());argv=launch['argv']
            self.assertGreater(argv.index('model="sample-model"'),argv.index('exec'))
            self.assertGreater(argv.index('mcp_servers.proof.command="echo"'),argv.index('exec'))
            if project_args:
                self.assertEqual(argv[launch['private_argv_indices'][0]],'[PRIVATE HOME CONTEXT REDACTED]')
                self.assertGreater(launch['private_argv_indices'][0],argv.index('exec'))

    def test_shared_cli_preserves_unselected_native_configuration(self):
        import contextlib
        import io
        other=self.home/'opencode.jsonc';other.write_text('// native-only customization\n{}')
        before=other.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['config',str(self.home),'--shared-json','{"model":"new-model"}']),0)
        self.assertEqual(self.codex()['model'],'new-model')
        self.assertEqual(other.read_bytes(),before)

    def test_runtime_selection_sanitizes_missing_native_home(self):
        with self.assertRaisesRegex(core.HomeError,'unsafe native home path'):
            native_config.configure_runtime(Path(self.temp.name)/'missing','codex')

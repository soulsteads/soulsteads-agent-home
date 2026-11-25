"""Contract shared by the opt-in native Agent Home packages."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from soulsteads import cli, core, native_config


ASSETS = Path(__file__).resolve().parents[1] / "soulsteads/assets/native-plugins"
PLUGIN = ASSETS / "plugins/soulsteads-agent-home"
SKILL = "soulsteads-home-status"


class NativePluginPackagesTest(unittest.TestCase):
    def test_all_package_formats_use_the_same_skill(self):
        skill = PLUGIN / "skills" / SKILL / "SKILL.md"
        self.assertTrue(skill.is_file(), "the native packages must ship a status skill")
        header, body = skill.read_text(encoding="utf-8").split("\n---\n", 1)
        self.assertIn(f"\nname: {SKILL}\n", header)
        self.assertIn("do not infer", body.lower())

        def manifest(path):
            return json.loads(path.read_text(encoding="utf-8"))

        package = manifest(PLUGIN / "package.json")
        for host in ("claude", "codex"):
            with self.subTest(host=host):
                spec = manifest(PLUGIN / f".{host}-plugin/plugin.json")
                self.assertEqual(spec["name"], package["name"])
                self.assertEqual(spec["version"], package["version"])
                self.assertNotIn("hooks", spec)
                self.assertFalse((PLUGIN / "hooks").exists())

        marketplace = manifest(ASSETS / ".agents/plugins/marketplace.json")
        source, = marketplace["plugins"]
        self.assertEqual(source["name"], package["name"])
        self.assertEqual(source["source"]["source"], "local")
        self.assertEqual((ASSETS / source["source"]["path"]).resolve(), PLUGIN)
        self.assertEqual(package["pi"], {"skills": ["./skills"]})
        self.assertEqual(package["exports"], {".": "./index.js"})

    def test_codex_skill_disables_implicit_invocation(self):
        policy = PLUGIN / "skills" / SKILL / "agents/openai.yaml"
        self.assertTrue(policy.is_file(), "Codex requires per-skill invocation metadata")
        self.assertEqual(policy.read_text(encoding="utf-8").splitlines(), [
            "policy:", "  allow_implicit_invocation: false",
        ])

    def skill_command(self, home):
        skill = (PLUGIN / "skills" / SKILL / "SKILL.md").read_text(encoding="utf-8")
        command = re.search(r"`(soulsteads verify [^`]+)`", skill)
        if command is None:
            self.fail("the skill must show how to call the CLI")
        argv = shlex.split(command[1])[1:]
        self.assertEqual(argv.count("$home"), 1)
        return [str(home) if arg == "$home" else arg for arg in argv]

    def run_verify(self, argv, expected_exit=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = cli.main(argv)
            except SystemExit as exc:
                result = exc.code
        self.assertEqual(result, expected_exit, stderr.getvalue())
        return json.loads(stdout.getvalue())

    def test_shared_skill_command_verifies_explicit_home(self):
        with tempfile.TemporaryDirectory() as root:
            home = core.create(
                "helper", "pi", path=Path(root).resolve() / "home with spaces"
            )
            report = self.run_verify(self.skill_command(home))
            self.assertIn(report["status"], ("passed", "needs-review"))
            self.assertEqual(report["scope"], "offline-structural")
            self.assertNotIn("version_probe", report)
            missing = self.run_verify(self.skill_command(home / "absent"), 1)
            self.assertEqual(missing["status"], "failed")
            self.assertFalse((home / "absent").exists())

    def test_shared_skill_does_not_check_home_selected_credential_variable(self):
        name = "SOULSTEADS_TEST_HOME_CREDENTIAL"
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ):
            home = core.create("helper", "pi", base=Path(root).resolve())
            native_config.sync(
                home,
                hindsight={"url": "https://memory.example/mcp/helper/", "token_env": name},
            )
            os.environ.pop(name, None)
            absent = self.run_verify(self.skill_command(home))
            os.environ[name] = "fixture-value"
            with patch.object(os.environ, "get", wraps=os.environ.get) as env_get:
                present = self.run_verify(self.skill_command(home))
            self.assertFalse(
                any(call.args[0] == name for call in env_get.call_args_list),
                "the skill inspected the Home-selected credential variable",
            )
            self.assertEqual(absent, present)
            findings = {item["id"] for item in present["findings"]}
            self.assertIn("memory-qualification", findings)
            self.assertNotIn("memory-credential", findings)
            # Direct operator verification keeps its existing diagnostic.
            ordinary = self.run_verify(["verify", str(home)])
            ordinary_status = {item["id"]: item["status"] for item in ordinary["findings"]}
            self.assertEqual(ordinary_status["memory-credential"], "passed")

    @unittest.skipUnless(shutil.which("node"), "Node required for OpenCode plugin")
    def test_opencode_registers_shared_skill_without_replacing_existing_skill(self):
        script = """
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL, fileURLToPath } from 'node:url';
const root = pathToFileURL(process.argv[1] + '/');
const { default: plugin } = await import(new URL('index.js', root));
assert.equal(plugin.id, 'soulsteads.agent-home');
const skillID = 'soulsteads-home-status';
const skillURL = new URL(`skills/${skillID}/SKILL.md`, root);
const body = (await readFile(skillURL, 'utf8')).split('\\n---\\n').at(-1).trim();
let transform;
let disposed = false;
const cleanup = await plugin.setup({ skill: { async transform(fn) {
    transform = fn;
    return { async dispose() { disposed = true; } };
} } });
const catalog = new Map();
const editor = {
    get: (id) => catalog.get(id),
    add: (info) => { assert(!catalog.has(info.id)); catalog.set(info.id, info); },
};
transform(editor);
assert.equal(catalog.size, 1);
const skill = catalog.get(skillID);
assert.equal(skill.name, skillID);
assert.equal(skill.content, body);
assert.equal(skill.path, fileURLToPath(skillURL));
assert.equal(skill.autoinvoke, false);
const existing = { id: skillID, content: 'unrelated existing entry' };
catalog.set(skillID, existing);
transform(editor);
assert.strictEqual(catalog.get(skillID), existing);
await cleanup();
assert(disposed);
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(PLUGIN)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

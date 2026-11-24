"""Contract shared by the opt-in native Agent Home packages."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

from soulsteads import cli, core


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

    def test_shared_skill_command_verifies_explicit_home(self):
        skill = (PLUGIN / "skills" / SKILL / "SKILL.md").read_text(encoding="utf-8")
        command = re.search(r"`(soulsteads verify [^`]+)`", skill)
        if command is None:
            self.fail("the skill must show how to call the CLI")
        argv = shlex.split(command[1])[1:]
        self.assertEqual(argv.count("$home"), 1)
        with tempfile.TemporaryDirectory() as root:
            home = core.create(
                "helper", "pi", path=Path(root).resolve() / "home with spaces"
            )
            cases = ((home, ("passed", "needs-review"), 0), (home / "absent", ("failed",), 1))
            for path, statuses, code in cases:
                with self.subTest(expected_exit=code):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    args = [str(path) if arg == "$home" else arg for arg in argv]
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        try:
                            result = cli.main(args)
                        except SystemExit as exc:
                            result = exc.code
                    self.assertEqual(result, code, stderr.getvalue())
                    report = json.loads(stdout.getvalue())
                    self.assertIn(report["status"], statuses)
                    self.assertEqual(report["scope"], "offline-structural")
                    self.assertNotIn("version_probe", report)
            self.assertFalse((home / "absent").exists())

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

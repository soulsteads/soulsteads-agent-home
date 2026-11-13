"""Protocol checks for the optional generic OpenCode v2 profile-memory plugin."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


ASSETS = Path(__file__).resolve().parents[1] / "soulsteads" / "assets" / "opencode-v2"
NODE = shutil.which("node")
MEMORY_LIMIT = 64 * 1024
CONFIG_LIMIT = 1024 * 1024


def safe_private_directory(candidate):
    """Return whether a fixture parent is an owned, non-writable directory."""
    try:
        metadata = candidate.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and not (metadata.st_mode & 0o022)
    )


@unittest.skipUnless(NODE, "Node is required for native JavaScript protocol fixtures")
@unittest.skipUnless(os.name == "posix", "descriptor-style reader fixtures require POSIX")
class OpenCodeV2ProfileMemoryTests(unittest.TestCase):
    @contextmanager
    def private_fixture(self):
        """Create a private synthetic root, avoiding public /tmp by default."""
        configured = os.environ.get("TMPDIR")
        candidate = Path(configured) if configured else None
        parent = candidate if candidate and safe_private_directory(candidate) else Path.home()
        if not safe_private_directory(parent):
            self.skipTest("no private fixture parent is available")
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            # Canonicalize only the fixture we just created (macOS /private spelling).
            root = Path(temporary).resolve()
            root.chmod(0o700)
            yield root

    def write_memory(self, workspace, *, memory="Synthetic retained fact.", rules="Synthetic handling rule."):
        workspace.mkdir(mode=0o700, exist_ok=True)
        (workspace / "MEMORY.md").write_text(memory, encoding="utf-8")
        (workspace / "MEMORY-RULES.md").write_text(rules, encoding="utf-8")
        for name in ("MEMORY.md", "MEMORY-RULES.md"):
            (workspace / name).chmod(0o600)

    def write_config(self, root, instructions):
        config = root / "opencode.json"
        config.write_text(json.dumps({"instructions": instructions}), encoding="utf-8")
        config.chmod(0o600)
        return config

    def run_node(self, script, *, workspace, extra_environment=None, cwd=None):
        assert NODE is not None
        environment = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "PLUGIN_MODULE": (ASSETS / "profile-memory.mjs").as_uri(),
            "WORKSPACE": str(workspace),
        }
        environment.update(extra_environment or {})
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            env=environment,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_factory_registers_each_text_hook_and_injects_one_fresh_memory_block(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
const {createProfileMemoryPlugin} = await import(process.env.PLUGIN_MODULE);
const hooks = new Map();
const plugin = createProfileMemoryPlugin({workspace: process.env.WORKSPACE});
assert.equal(plugin.id, "soulstead.profile-memory");
await plugin.setup({session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
assert.deepEqual([...hooks.keys()], ["context", "compaction", "generate"]);
for (const callback of hooks.values()) {
  const input = {system: [{type: "text", text: "existing system text"}]};
  await callback(input);
  assert.equal(input.system.length, 2);
  assert.match(input.system[1].text, /Synthetic handling rule/);
  assert.match(input.system[1].text, /Synthetic retained fact/);
}
''', workspace=workspace)

    def test_factory_re_reads_changed_memory_and_deduplicates_unchanged_block(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const {createProfileMemoryPlugin} = await import(process.env.PLUGIN_MODULE);
const hooks = new Map();
await createProfileMemoryPlugin({workspace: process.env.WORKSPACE}).setup(
  {session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
const input = {system: []};
const callback = hooks.get("generate");
const probe = await fs.open(`${process.env.WORKSPACE}/MEMORY-RULES.md`, "r");
const prototype = Object.getPrototypeOf(probe);
await probe.close();
const read = prototype.read;
let created = false;
prototype.read = async function (...args) {
  const result = await read.apply(this, args);
  if (!created && result.bytesRead > 0) {
    created = true;
    await fs.mkdir(`${process.env.WORKSPACE}/unrelated-child`);
  }
  return result;
};
try {
  await callback(input);
} finally {
  prototype.read = read;
}
await callback(input);
assert.equal(input.system.length, 1);
await fs.writeFile(`${process.env.WORKSPACE}/MEMORY.md`, "Fresh retained memory.");
await callback(input);
assert.equal(input.system.length, 2);
assert.match(input.system[1].text, /Fresh retained memory/);
''', workspace=workspace)

    def test_post_read_same_size_mutation_is_refused_without_system_changes(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const {createProfileMemoryPlugin} = await import(process.env.PLUGIN_MODULE);
const memory = `${process.env.WORKSPACE}/MEMORY.md`;
const original = await fs.readFile(memory, "utf8");
const replacement = "X".repeat(Buffer.byteLength(original));
const probe = await fs.open(memory, "r");
const prototype = Object.getPrototypeOf(probe);
await probe.close();
const read = prototype.read;
let contentReads = 0;
let mutated = false;
prototype.read = async function (...args) {
  const result = await read.apply(this, args);
  if (result.bytesRead > 0) contentReads += 1;
  // Rules are read first; mutate MEMORY.md only after its own first read.
  if (!mutated && contentReads === 2) {
    mutated = true;
    await fs.writeFile(memory, replacement);
  }
  return result;
};
try {
  const hooks = new Map();
  await createProfileMemoryPlugin({workspace: process.env.WORKSPACE}).setup(
    {session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
  const input = {system: [{type: "text", text: "keep"}]};
  await assert.rejects(hooks.get("context")(input), {message: "Profile memory is unavailable"});
  assert.deepEqual(input, {system: [{type: "text", text: "keep"}]});
} finally {
  prototype.read = read;
}
''', workspace=workspace)

    def test_memory_leaf_admission_refuses_symlink_hardlink_nonprivate_and_oversize_inputs(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            external = root / "external-memory"
            external.write_text("external", encoding="utf-8")
            external.chmod(0o600)
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const {createProfileMemoryPlugin} = await import(process.env.PLUGIN_MODULE);
const workspace = process.env.WORKSPACE;
async function invoke() {
  const hooks = new Map();
  await createProfileMemoryPlugin({workspace}).setup({session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
  const input = {system: [{type: "text", text: "keep"}]};
  await assert.rejects(hooks.get("generate")(input), {message: "Profile memory is unavailable"});
  assert.deepEqual(input, {system: [{type: "text", text: "keep"}]});
}
await fs.unlink(`${workspace}/MEMORY.md`);
await fs.symlink(`${workspace}/../external-memory`, `${workspace}/MEMORY.md`);
await invoke();
await fs.unlink(`${workspace}/MEMORY.md`);
await fs.writeFile(`${workspace}/MEMORY.md`, "normal");
await fs.link(`${workspace}/MEMORY.md`, `${workspace}/MEMORY-copy.md`);
await invoke();
await fs.unlink(`${workspace}/MEMORY-copy.md`);
await fs.chmod(`${workspace}/MEMORY.md`, 0o644);
await invoke();
await fs.chmod(`${workspace}/MEMORY.md`, 0o600);
await fs.writeFile(`${workspace}/MEMORY.md`, "A".repeat(65537));
await invoke();
''', workspace=workspace)

    def test_workspace_symlink_and_observed_replacement_are_refused_without_system_changes(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
const {createProfileMemoryPlugin} = await import(process.env.PLUGIN_MODULE);
const workspace = process.env.WORKSPACE;
const hooks = new Map();
await createProfileMemoryPlugin({workspace}).setup({session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
const probe = await fs.open(`${workspace}/MEMORY-RULES.md`, "r");
const prototype = Object.getPrototypeOf(probe);
await probe.close();
const read = prototype.read;
let replaced = false;
prototype.read = async function (...args) {
  const result = await read.apply(this, args);
  if (!replaced && result.bytesRead > 0) {
    replaced = true;
    await fs.rename(workspace, `${workspace}-moved`);
    await fs.mkdir(workspace, {mode: 0o700});
    await fs.writeFile(`${workspace}/MEMORY.md`, "replacement");
    await fs.writeFile(`${workspace}/MEMORY-RULES.md`, "replacement rules");
    await fs.chmod(`${workspace}/MEMORY.md`, 0o600);
    await fs.chmod(`${workspace}/MEMORY-RULES.md`, 0o600);
  }
  return result;
};
const input = {system: [{type: "text", text: "keep"}]};
try {
  await assert.rejects(hooks.get("generate")(input), {message: "Profile memory is unavailable"});
  assert.deepEqual(input, {system: [{type: "text", text: "keep"}]});
} finally {
  prototype.read = read;
}
await fs.rm(workspace, {recursive: true});
await fs.symlink(`${workspace}-moved`, workspace);
const linkedHooks = new Map();
await createProfileMemoryPlugin({workspace}).setup({session: {hook: async (kind, callback) => linkedHooks.set(kind, callback)}});
await assert.rejects(linkedHooks.get("generate")({system: []}), {message: "Profile memory is unavailable"});
const ancestorAlias = `${workspace}-ancestor`;
await fs.symlink(path.dirname(workspace), ancestorAlias);
const ancestorWorkspace = path.join(ancestorAlias, path.basename(workspace));
const ancestorHooks = new Map();
await createProfileMemoryPlugin({workspace: ancestorWorkspace}).setup(
  {session: {hook: async (kind, callback) => ancestorHooks.set(kind, callback)}});
const ancestorInput = {system: [{type: "text", text: "keep"}]};
await assert.rejects(ancestorHooks.get("generate")(ancestorInput), {message: "Profile memory is unavailable"});
assert.deepEqual(ancestorInput, {system: [{type: "text", text: "keep"}]});
''', workspace=workspace)

    def test_native_entry_uses_the_explicit_legacy_workspace_environment(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
const hooks = new Map();
await plugin.setup({session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
assert.deepEqual([...hooks.keys()], ["context", "compaction", "generate"]);
const input = {system: []};
await hooks.get("generate")(input);
assert.equal(input.system.length, 1);
assert.match(input.system[0].text, /Synthetic retained fact/);
''', workspace=workspace, extra_environment={"SOULSTEAD_MEMORY_WORKSPACE": str(workspace)})

    def test_native_entry_derives_workspace_from_one_private_bounded_config_instruction(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            config = self.write_config(root, [str(workspace / "MEMORY.md")])
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
const hooks = new Map();
await plugin.setup({session: {hook: async (kind, callback) => hooks.set(kind, callback)}});
const input = {system: []};
await hooks.get("context")(input);
assert.equal(input.system.length, 1);
assert.match(input.system[0].text, /Synthetic retained fact/);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(config)})

    def test_native_entry_rejects_missing_relative_ambiguous_and_oversized_config_before_hooks(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            config = self.write_config(root, [str(workspace / "MEMORY.md")])
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * (CONFIG_LIMIT + 1))
            oversized.chmod(0o600)
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
async function rejected() {
  let calls = 0;
  await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
    {message: "Profile memory requires a fixed absolute workspace"});
  assert.equal(calls, 0);
}
await rejected();
''', workspace=workspace)
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
let calls = 0;
await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
  {message: "Profile memory requires a fixed absolute workspace"});
assert.equal(calls, 0);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": "opencode.json"}, cwd=str(root))
            self.write_config(root, [str(workspace / "MEMORY.md"), str(workspace / "MEMORY.md")])
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
let calls = 0;
await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
  {message: "Profile memory requires a fixed absolute workspace"});
assert.equal(calls, 0);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(config)})
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
let calls = 0;
await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
  {message: "Profile memory requires a fixed absolute workspace"});
assert.equal(calls, 0);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(oversized)})

    def test_native_entry_rejects_config_symlink_hardlink_and_nonprivate_file_before_hooks(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            config = self.write_config(root, [str(workspace / "MEMORY.md")])
            linked = root / "linked.json"
            hardlinked = root / "hardlinked.json"
            linked.symlink_to(config)
            os.link(config, hardlinked)
            nonprivate = root / "nonprivate.json"
            nonprivate.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
            nonprivate.chmod(0o644)
            fifo = root / "config.fifo"
            os.mkfifo(fifo, 0o600)
            for candidate in (linked, hardlinked, nonprivate, fifo):
                self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
let calls = 0;
await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
  {message: "Profile memory requires a fixed absolute workspace"});
assert.equal(calls, 0);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(candidate)})

    def test_config_post_read_same_size_mutation_and_growth_are_refused_before_hooks(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            config = self.write_config(root, [str(workspace / "MEMORY.md")])
            config.write_text(f" {config.read_text(encoding='utf-8')}", encoding="utf-8")
            config.chmod(0o600)
            self.run_node(r'''
import assert from "node:assert/strict";
import fs from "node:fs/promises";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
const config = process.env.OPENCODE_CONFIG;
const original = await fs.readFile(config, "utf8");
const sameSizeReplacement = `${original.slice(1)} `;
const probe = await fs.open(config, "r");
const prototype = Object.getPrototypeOf(probe);
await probe.close();
const read = prototype.read;
let state = "same-size";
prototype.read = async function (...args) {
  const result = await read.apply(this, args);
  if (result.bytesRead > 0 && state === "same-size") {
    state = "same-size-done";
    await fs.writeFile(config, sameSizeReplacement);
  } else if (result.bytesRead > 0 && state === "growth") {
    state = "growth-done";
    await fs.writeFile(config, `${original}X`);
  }
  return result;
};
async function rejected() {
  let calls = 0;
  await assert.rejects(plugin.setup({session: {hook: async () => calls++}}),
    {message: "Profile memory requires a fixed absolute workspace"});
  assert.equal(calls, 0);
}
try {
  await rejected();
  await fs.writeFile(config, original);
  state = "growth";
  await rejected();
} finally {
  prototype.read = read;
}
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(config)})

    def test_native_entry_rejects_a_config_memory_path_with_a_trailing_alias(self):
        with self.private_fixture() as root:
            workspace = root / "profile"
            self.write_memory(workspace)
            config = self.write_config(root, [f"{workspace}/MEMORY.md/"])
            self.run_node(r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
let calls = 0;
await assert.rejects(plugin.setup({session: {hook: async () => calls++}}), {
  message: "Profile memory requires a fixed absolute workspace"
});
assert.equal(calls, 0);
''', workspace=workspace, extra_environment={"OPENCODE_CONFIG": str(config)})


if __name__ == "__main__":
    unittest.main()

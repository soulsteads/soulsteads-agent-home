"""Self-contained protocol checks for optional native OpenCode v2 plugins."""

import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import unittest


ASSETS = Path(__file__).resolve().parents[1] / "soulsteads" / "assets" / "opencode-v2"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is required for native JavaScript protocol fixtures")
class OpenCodeV2PluginTests(unittest.TestCase):
    def run_node(self, module, script):
        assert NODE is not None
        environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PLUGIN_MODULE": (ASSETS / module).as_uri()}
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_headroom_routes_only_the_exact_codex_request_through_an_explicit_proxy(self):
        self.run_node("codex-headroom.mjs", r'''
import assert from "node:assert/strict";
const {createCodexHeadroomPlugin} = await import(process.env.PLUGIN_MODULE);
const callbacks = new Map();
const plugin = createCodexHeadroomPlugin({proxyUrl: "http://127.0.0.1:9876/v1/responses"});
await plugin.setup({session: {hook: async (kind, fn) => callbacks.set(kind, fn)}});
assert.deepEqual([...callbacks.keys()], ["http.request"]);
const controller = new AbortController();
const event = {request: new Request("https://chatgpt.com/backend-api/codex/responses", {
  method: "POST", body: "synthetic-body", signal: controller.signal,
  headers: {authorization: "Bearer SYNTHETIC", "x-headroom-base-url": "spoofed", "x-headroom-original-path": "spoofed"}
})};
await callbacks.get("http.request")(event);
assert.equal(event.request.url, "http://127.0.0.1:9876/v1/responses");
assert.equal(event.request.headers.get("authorization"), "Bearer SYNTHETIC");
assert.equal(event.request.headers.get("x-headroom-base-url"), "https://chatgpt.com");
assert.equal(event.request.headers.get("x-headroom-original-path"), "/backend-api/codex/responses");
assert.equal(event.request.redirect, "error");
assert.equal(await event.request.text(), "synthetic-body");
controller.abort();
assert.equal(event.request.signal.aborted, true);
for (const [url, method] of [
  ["https://chatgpt.com/backend-api/codex/responses", "GET"],
  ["https://chatgpt.com/backend-api/codex/responses?extra=1", "POST"],
  ["https://chatgpt.com.example/backend-api/codex/responses", "POST"],
  ["https://api.openai.com/v1/responses", "POST"]
]) {
  const original = new Request(url, {method});
  const other = {request: original};
  await callbacks.get("http.request")(other);
  assert.equal(other.request, original);
}
''')
    def test_headroom_preserves_each_original_credential_mode(self):
        self.run_node("codex-headroom.mjs", r'''
import assert from "node:assert/strict";
const {createCodexHeadroomPlugin} = await import(process.env.PLUGIN_MODULE);
const callbacks = new Map();
await createCodexHeadroomPlugin({proxyUrl: "http://127.0.0.1:9876/v1/responses"})
  .setup({session: {hook: async (kind, fn) => callbacks.set(kind, fn)}});
const rewrite = callbacks.get("http.request");
for (const credentials of ["include", "omit"]) {
  const event = {request: new Request("https://chatgpt.com/backend-api/codex/responses", {
    method: "POST", body: "synthetic-body", credentials,
  })};
  await rewrite(event);
  assert.equal(event.request.credentials, credentials);
}
''')
    def test_headroom_refuses_implicit_remote_or_credential_bearing_proxy_targets(self):
        self.run_node("codex-headroom.mjs", r'''
import assert from "node:assert/strict";
const {createCodexHeadroomPlugin} = await import(process.env.PLUGIN_MODULE);
const message = "Headroom proxy requires an explicit canonical loopback HTTP /v1/responses URL";
for (const proxyUrl of [undefined, "", "not-a-url", "https://127.0.0.1:9876/v1/responses",
  "http://example.test/v1/responses", "http://127.0.0.1.example/v1/responses",
  "http://user:SYNTHETIC@127.0.0.1:9876/v1/responses", "http://127.0.0.1:9876/other",
  "http://127.0.0.1:9876/v1/responses?token=SYNTHETIC", "http://127.0.0.1:9876/v1/responses#fragment",
  "http://127.0.0.1:9876/../v1/responses", "http://127.0.0.1:9876/v1/resp\nonses"])
  assert.throws(() => createCodexHeadroomPlugin({proxyUrl}), {message});
for (const proxyUrl of ["http://localhost:9876/v1/responses", "http://[::1]:9876/v1/responses"])
  assert.doesNotThrow(() => createCodexHeadroomPlugin({proxyUrl}));
''')
    def test_headroom_native_entry_point_requires_an_explicit_environment_opt_in(self):
        self.run_node("codex-headroom.mjs", r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
assert.ok(plugin && typeof plugin.setup === "function", "native plugin entry point missing");
let count = 0;
const ctx = {session: {hook: async kind => {assert.equal(kind, "http.request"); count++;}}};
await assert.rejects(plugin.setup(ctx), /explicit canonical loopback HTTP/);
assert.equal(count, 0);
process.env.SOULSTEADS_HEADROOM_PROXY_URL = "http://127.0.0.1:9876/v1/responses";
await plugin.setup(ctx);
assert.equal(count, 1);
''')
    def test_single_system_plugin_only_combines_explicitly_selected_model_text(self):
        self.run_node("single-system.mjs", r'''
import assert from "node:assert/strict";
const {createSingleSystemPlugin} = await import(process.env.PLUGIN_MODULE);
const callbacks = new Map();
await createSingleSystemPlugin({providerId: "example-router", modelIds: ["example-qwen"]})
  .setup({session: {hook: async (kind, fn) => callbacks.set(kind, fn)}});
assert.deepEqual([...callbacks.keys()], ["context", "compaction", "generate", "title"]);
for (const hook of callbacks.values()) {
  const system = [{type: "text", text: "first"}, {type: "text", text: "second"}];
  const event = {model: {providerID: "example-router", id: "example-qwen"}, system};
  await hook(event);
  assert.equal(event.system, system);
  assert.deepEqual(system, [{type: "text", text: "first\n\nsecond"}]);
  await hook(event);
  assert.deepEqual(system, [{type: "text", text: "first\n\nsecond"}]);
  for (const model of [{providerID: "other", id: "example-qwen"}, {providerID: "example-router", id: "other"}]) {
    const parts = [{type: "text", text: "first"}, {type: "text", text: "second"}];
    await hook({model, system: parts});
    assert.deepEqual(parts, [{type: "text", text: "first"}, {type: "text", text: "second"}]);
  }
}
''')
    def test_single_system_refuses_content_loss_for_selected_models(self):
        self.run_node("single-system.mjs", r'''
import assert from "node:assert/strict";
const {createSingleSystemPlugin} = await import(process.env.PLUGIN_MODULE);
let normalize;
await createSingleSystemPlugin({providerId: "example-router", modelIds: ["example-qwen"]})
  .setup({session: {hook: async (_kind, fn) => {normalize = fn;}}});
for (const parts of [
  [{type: "text", text: "first", providerOptions: {example: {cache: "keep"}}}, {type: "text", text: "second"}],
  [{type: "image", data: "SYNTHETIC"}, {type: "text", text: "second"}],
  [{type: "text", text: 123}, {type: "text", text: "second"}],
  [null, {type: "text", text: "second"}]
]) {
  const before = structuredClone(parts);
  assert.throws(() => normalize({model: {providerID: "example-router", id: "example-qwen"}, system: parts}),
    {message: "Selected model requires text-only system parts"});
  assert.deepEqual(parts, before);
}
const untouched = [{type: "image", data: "SYNTHETIC"}, {type: "text", text: "second"}];
normalize({model: {providerID: "other", id: "example-qwen"}, system: untouched});
assert.equal(untouched.length, 2);
''')
    def test_single_system_native_entry_point_requires_valid_explicit_model_selection(self):
        self.run_node("single-system.mjs", r'''
import assert from "node:assert/strict";
const {default: plugin, createSingleSystemPlugin} = await import(process.env.PLUGIN_MODULE);
const message = "Single-system hook requires an explicit provider and a nonempty bounded list of distinct model IDs";
for (const options of [{}, {providerId: "example-router", modelIds: []},
  {providerId: "example-router", modelIds: "example-qwen"},
  {providerId: "example-router", modelIds: ["example-qwen", "example-qwen"]},
  {providerId: "example-router", modelIds: [""]},
  {providerId: " example-router", modelIds: ["example-qwen"]},
  {providerId: "example-router", modelIds: ["x".repeat(257)]},
  {providerId: "example-router", modelIds: Array.from({length: 129}, (_, i) => `example-${i}`)}])
  assert.throws(() => createSingleSystemPlugin(options), {message});
assert.ok(plugin && typeof plugin.setup === "function", "native plugin entry point missing");
let count = 0;
const ctx = {session: {hook: async () => {count++;}}};
await assert.rejects(plugin.setup(ctx), {message});
assert.equal(count, 0);
process.env.SOULSTEADS_SINGLE_SYSTEM_PROVIDER = "example-router";
process.env.SOULSTEADS_SINGLE_SYSTEM_MODELS = "SYNTHETIC-invalid-json";
await assert.rejects(plugin.setup(ctx), {message});
assert.equal(count, 0);
process.env.SOULSTEADS_SINGLE_SYSTEM_MODELS = JSON.stringify(["example-qwen"]);
await plugin.setup(ctx);
assert.equal(count, 4);
''')
    def test_plugins_have_native_directory_entry_points(self):
        for directory in ["codex-headroom", "single-system", "profile-memory"]:
            with self.subTest(plugin=directory):
                self.run_node(directory + "/index.js", r'''
import assert from "node:assert/strict";
const {default: plugin} = await import(process.env.PLUGIN_MODULE);
assert.equal(typeof plugin.id, "string");
assert.equal(typeof plugin.setup, "function");
''')


class OpenCodeV2AssetPackagingTests(unittest.TestCase):
    def test_native_entry_points_and_modules_are_included_in_installed_package(self):
        root = ASSETS.parents[2]
        metadata = tomllib.loads((root / "pyproject.toml").read_text())
        patterns = metadata["tool"]["setuptools"].get("package-data", {}).get("soulsteads", [])
        required = ["package.json"]
        for name in ["codex-headroom", "single-system", "profile-memory"]:
            required.extend([name + ".mjs", name + "/index.js"])
        for name in required:
            path = Path("assets/opencode-v2") / name
            with self.subTest(asset=str(path)):
                self.assertTrue(any(path.match(pattern) for pattern in patterns),
                                f"Missing package-data declaration for {path}")


if __name__ == "__main__":
    unittest.main()

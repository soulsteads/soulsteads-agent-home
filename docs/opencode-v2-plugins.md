# Optional native OpenCode v2 plugins

These are standalone, opt-in plugins. Agent Home neither enables them nor edits global OpenCode settings. They add no Python CLI dependency, do not restore Home's legacy automatic-memory interception, and remain separate from the Home settings/learning model.

## Choose the native runtime explicitly

Use a separately installed, pinned native OpenCode client and private configuration. Plugin discovery requires a **directory** containing `index.js`; explicit module-file paths are skipped, even when `debug config` prints them. See [OpenCode plugin configuration](https://opencode.ai/docs/plugins/).

Instruction loading is a separate requirement. OpenCode **2.0.23** normalizes `instructions` but its instruction plugin only discovers `AGENTS.md`; accepting an instruction path is not proof that its contents reach the model. Upstream [fixed configured instruction loading](https://github.com/anomalyco/opencode/commit/1e63a3bb73713ccaddd2c527e372ac79f2a72e4c). The [2.1.3 source](https://github.com/anomalyco/opencode/blob/bb25a2f4a3f3f04d7c344bec0c0574ea3510b3b1/packages/core/src/config/plugin/instruction.ts) contains that loader. A synthetic loopback request using 2.1.3 included both configured instruction canaries; the same 2.0.23 probe did not. The auxiliary title request intentionally has different instructions.

This establishes pre-inference instruction/hook construction, not successful inference, completed replies, compaction or messaging delivery. Do not upgrade a live runtime or open an existing native database merely to test it: qualify the client/API/state migration and recovery independently, with synthetic state first.

## Locate the packaged assets

The three plugins ship as package data in the Python distribution, under `soulsteads/assets/opencode-v2/`. With the selected installation's Python:

```sh
python3 -c 'from importlib.resources import files; print(files("soulsteads").joinpath("assets", "opencode-v2"))'
```

Keep the complete asset directory, including `package.json`, the `.mjs` modules and each plugin's directory wrapper. Point the selected native profile at its pinned installation, or copy the complete public asset directory into a fresh owner-private versioned plugin installation. Preserve the previous installation during upgrades. Do not copy personal plugin bundles or overwrite an active installation in place.

For example, select only the desired directories in private `opencode.json`:

```json
{
  "plugins": [
    "/absolute/pinned/assets/opencode-v2/profile-memory",
    "/absolute/pinned/assets/opencode-v2/single-system",
    "/absolute/pinned/assets/opencode-v2/codex-headroom"
  ]
}
```

This example is not a complete runtime configuration. Preserve native models, authentication, session stores, MCP registrations, tool permissions and policy enforcement. Do not add `*`, remove policies or widen permissions merely to load a plugin. Installing assets does not opt in; adding a directory and its required private settings does.

## Fixed profile memory

ID: `soulstead.profile-memory`.

This plugin reads `MEMORY.md` and `MEMORY-RULES.md` from an explicitly admitted, fixed absolute workspace at each `context`, `compaction` and `generate` hook. It appends a typed system-text block without duplicating an identical block. It never uses a session's changing project directory as memory authority, creates no tools, makes no network calls and performs no retention writes.

Set the legacy-compatible `SOULSTEAD_MEMORY_WORKSPACE` to the selected absolute workspace. Alternatively, `OPENCODE_CONFIG` must identify a private JSON configuration whose `instructions` contains exactly one absolute path ending in `MEMORY.md`; that file's parent selects the workspace. Missing, relative, ambiguous, malformed or unsafe authority is refused rather than replaced by a cwd fallback.

The reader requires POSIX ownership and no-follow support. Memory files must be owner-private, regular, single-link files no larger than 64 KiB each; configuration reads are bounded separately. Ancestors must be real directories, owned by the current user or root and not group/world writable. Symlinks, unsafe leaves and observed replacement or in-place mutation fail closed with generic errors. Recreate public test fixtures with explicit safe permissions rather than weakening production checks.

**Limitation:** Node does not provide descriptor-relative directory traversal here. Lexical ancestor checks, no-follow leaf opens and identity/rebind checks cannot eliminate every namespace race after the final check. Do not treat this as a sandbox against an adversarial writer with the same Unix identity or elevated privileges. Coordinate legitimate writers before migration.

This is local fixed-file injection, not a substitute for native identity/skill instruction loading or an external memory integration. Preserve both responsibilities when an existing profile uses both.

## Codex-to-Headroom routing

ID: `soulstead.codex-headroom.v2`.

Set `SOULSTEADS_HEADROOM_PROXY_URL` to an explicit canonical loopback HTTP URL ending exactly in `/v1/responses`, for example `http://127.0.0.1:9876/v1/responses`. Only `127.0.0.1`, `localhost` and `[::1]` are accepted; credentials, queries, fragments, alternate paths and normalized spellings are refused.

The hook replaces only `POST https://chatgpt.com/backend-api/codex/responses`. Other hosts, methods, paths and query-bearing requests remain unchanged. It preserves the body, credentials, headers and abort signal, sets authoritative `x-headroom-base-url` and `x-headroom-original-path` headers, and refuses redirects at the proxy request. It does not start or discover a proxy or fall back to direct routing on proxy failure.

**Trust boundary:** the selected local proxy receives provider credentials and prompt content. Loopback is not authorization. Provision and independently qualify the intended proxy/service before enabling this hook; do not point it at an untrusted local listener. The plugin itself issues no additional request and does not change shared routing.

## Explicit single-system model compatibility

ID: `soulstead.qwen-single-system.v2`.

Select the provider and exact model IDs explicitly:

```sh
export SOULSTEADS_SINGLE_SYSTEM_PROVIDER=example-provider
export SOULSTEADS_SINGLE_SYSTEM_MODELS='["example-model"]'
```

The provider/model IDs are nonempty, whitespace/control-free and at most 256 UTF-8 bytes; the distinct model list contains 1–128 entries. There are no implicit provider aliases, family-prefix matches or default model choices.

For selected models only, the `context`, `compaction`, `generate` and `title` hooks combine multiple text system parts with blank-line separators, in place. Non-text parts or text parts carrying extra metadata are refused before mutation rather than silently dropped. Unselected models remain unchanged. Order memory injection before this compatibility plugin when both are selected; qualify other instruction-producing plugins and actual native hook ordering separately.

## Optional upstream Hindsight

The existing public upstream package already supplies the native integration. See the [pinned optional installation and policy guide](../integrations/hindsight-opencode/README.md). Do not enable two retention engines over the same transcript or migrate bank routing implicitly.

## Checks and activation boundary

Run the self-contained suite with an external bytecode cache and authorized scratch root:

```sh
PYTHONPYCACHEPREFIX=/absolute/private/cache python3 -m unittest discover -s tests -v
```

Node is required for the native protocol fixtures; POSIX is required for owner/no-follow memory checks. Those fixtures exercise hook registration, deterministic input transformations and filesystem refusal using synthetic data. Wheel contents and a real native loopback probe must also be checked for the candidate being delivered. A configuration check, a hook fixture or an intentional HTTP 400 is not a successful inference or a live cutover qualification.

Keep identity, instructions, credentials, private memory, endpoints, bank selection and recovery/session state outside public source and test artifacts. Finish independent review and installed/runtime verification before changing any live service.

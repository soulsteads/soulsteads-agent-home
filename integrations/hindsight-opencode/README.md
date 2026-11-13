# Optional pinned Hindsight integration for OpenCode

This directory pins the **upstream** `@vectorize-io/hindsight-coding-agents` runtime. It does not add a memory engine to Agent Home, copy a personal plugin bundle, or change Home's default behavior. Installing these files does not activate a plugin or change an agent's configuration.

## Public source and integrity

- Package: `@vectorize-io/hindsight-coding-agents@0.8.7`.
- Source commit recorded by npm: `329f8a5ac9baa5567f4516a24dc9fd0f753a75ae`.
- [Upstream source at that commit](https://github.com/vectorize-io/hindsight/tree/329f8a5ac9baa5567f4516a24dc9fd0f753a75ae/hindsight-integrations/coding-agents).
- The generated `package-lock.json` records the public registry tarball and its SHA-512 integrity. Use the lock, not an unpinned `npx` command.
- The upstream repository has an [MIT license at the same commit](https://github.com/vectorize-io/hindsight/blob/329f8a5ac9baa5567f4516a24dc9fd0f753a75ae/LICENSE), copyright Vectorize AI, Inc. The npm metadata does not declare a license and this tarball contains no LICENSE file. We distribute only installation metadata, not the upstream bundle; review and retain applicable upstream and bundled-dependency notices before redistributing runtime bytes.

The package already contains an OpenCode v2 directory entry point, `index.js`, which delegates to `dist/opencode2.js`. Do not replace it with a copied local bundle or invent another adapter. The package's v1 entry point is different; consult the pinned upstream README for its supported host contracts.

## Install without activation

From this directory, copy **only** `package.json` and `package-lock.json` into a fresh owner-private installation directory outside any public checkout, then run:

```sh
npm ci --ignore-scripts --no-audit --no-fund --prefix /absolute/private/installation
```

Preserve any previous installation instead of overwriting it. The selected plugin directory is then:

```text
/absolute/private/installation/node_modules/@vectorize-io/hindsight-coding-agents
```

For OpenCode v2, configure that **directory**, not `index.js` or `dist/opencode2.js`. Explicit single-file configuration entries are skipped by the host. Configure only the intended native profile; do not run the upstream `install all` command or rewrite global agent settings as part of a scoped install.

## Policy and private configuration

Point `HINDSIGHT_CONFIG` at an explicitly selected private configuration file. Keep endpoints, tokens, bank routing, path mappings, identity, conversations and memory outside this repository. Credentials and native session stores remain owned by their existing systems.

**Upstream defaults are not a safe migration policy.** The upstream runtime can automatically inject memory, import conversations/git history, shape bank configuration and update itself. A package version pin alone does not disable those behaviors. Review every effective setting and host permission before activation.

For a new, deliberately inactive configuration, the pinned upstream fields permit an example like:

```json
{
  "disabled": true,
  "apiUrl": "https://memory.example.invalid",
  "bankId": "example-bank",
  "dynamicBankId": false,
  "autoInject": "none",
  "autoSeed": false,
  "gitIngest": "none",
  "codebaseSurvey": false,
  "retainSessions": false,
  "manageBankConfig": false,
  "autoUpdate": false
}
```

This is an **inactive new-profile example**, not a replacement for an existing authorized configuration. During migration preserve existing enabled responsibilities and the same bank/scope, credentials, private settings and permissions. Do not disable authorized retention merely to pass a check, and do not inherit a newly enabled upstream default silently. Enable recall/injection, transcript retention, ingestion, bank administration and write-capable tools only within their separately approved scopes.

The upstream release renamed knowledge-page tools to page tools. Reconcile native tool names and permissions explicitly; do not replace a restrictive allowlist with a wildcard to make migration work.

## Verification boundaries

Registry integrity, source provenance and installation establish only the package's identity. They do not prove native loading, correct bank selection, privacy-policy equivalence, recall, completed-reply retention or live service readiness. First use a synthetic native profile and loopback endpoints, then qualify the intended policy and actual loaded plugin at the exact client version. Do not use real memories, write to a live bank, or broaden permissions to turn a fixture green.

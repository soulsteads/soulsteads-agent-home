# Changelog

## 0.3.0 (proposed)

Changes since [`v0.1.0`](https://github.com/soulsteads/soulsteads-agent-home/releases/tag/v0.1.0), the latest published release. The `v0.2.0` candidate was not tagged.

### Highlights

- Add a shared settings catalog, native settings planning and application, capability reporting, and Home-managed project launches for supported runtimes.
- Import OpenClaw workspaces and review proposed Home changes before applying them. Render Claude project imports from shared instruction filenames.
- Review native skill corrections across harnesses and optionally submit scoped skill improvements to Skillstore. Local review remains available without a registry.
- Add an opt-in Linux Secret Service credential vault for Home-managed launches. Credentials stay outside Git; native configuration and state selectors cannot be set through vault mappings.
- Enforce the callback deadline for Hindsight and verify the contents and checksums of the wheel and source distribution before the release workflow attaches them.

### Included commits

Public `main` commits since `v0.1.0`, before this release-preparation PR:

- [`27503e2`](https://github.com/soulsteads/soulsteads-agent-home/commit/27503e2678ffe262cb3ac7c09f7ec6028be52c25) fix(vault): reserve native runtime selectors
- [`91b136f`](https://github.com/soulsteads/soulsteads-agent-home/commit/91b136fa13223bb4c4f5bfd0a800999fd49db940) feat: add an opt-in Agent Home credential vault
- [`f5ecaff`](https://github.com/soulsteads/soulsteads-agent-home/commit/f5ecaff50cde5ceea154cc1a1e7690797023f0fb) fix: render Claude imports from shared filenames
- [`515891a`](https://github.com/soulsteads/soulsteads-agent-home/commit/515891a930cb6e7fe697020c49398478a940f5cb) fix(ci): verify the complete release asset handoff
- [`a698d2f`](https://github.com/soulsteads/soulsteads-agent-home/commit/a698d2f54d17353434b32977d723fdd4bb0ad941) ci: build Agent Home release assets
- [`00ff6a0`](https://github.com/soulsteads/soulsteads-agent-home/commit/00ff6a018212dbe95a54e1917f94a024476d7793) test(cli): cover local drafts alongside Skillstore learning
- [`04f3d89`](https://github.com/soulsteads/soulsteads-agent-home/commit/04f3d8909899115b6bdc76c3ceb52215729bea66) fix: reject Hindsight responses after the callback deadline
- [`682a2ee`](https://github.com/soulsteads/soulsteads-agent-home/commit/682a2eeb2268693cc8bfbda943b824af01b9e9a0) feat: import OpenClaw workspaces and review Home changes
- [`27b0974`](https://github.com/soulsteads/soulsteads-agent-home/commit/27b0974c99a05dc1d049ad3e0f6981a9cf0a19c6) test: verify Skillstore scope before planning
- [`8b28911`](https://github.com/soulsteads/soulsteads-agent-home/commit/8b28911e22e5f916c5884cd43cd6a9b1c167e441) fix: enforce scoped Skillstore learning targets
- [`bae139e`](https://github.com/soulsteads/soulsteads-agent-home/commit/bae139e3fe127aa2f6b4a61bc7907e6df28e5a11) feat: automatically approve opted-in Skillstore corrections
- [`5598a95`](https://github.com/soulsteads/soulsteads-agent-home/commit/5598a950b145915ad7b7c174b69e0e4aeeff4ca9) feat: submit Home skill improvements to Skillstore
- [`b6014d7`](https://github.com/soulsteads/soulsteads-agent-home/commit/b6014d757bc4e3a93f3502c14da41d8d8daa0f7c) docs: record completed native skill readback runs
- [`3ef4026`](https://github.com/soulsteads/soulsteads-agent-home/commit/3ef4026cb96ebcd736a32eabdb4b49c5efe66071) feat: review native skill corrections across agent harnesses
- [`31d1fc2`](https://github.com/soulsteads/soulsteads-agent-home/commit/31d1fc26fe210d82fd414780a4aeae78efea185f) ci: run Agent Home tests on Ubuntu only
- [`88924f9`](https://github.com/soulsteads/soulsteads-agent-home/commit/88924f96541150d649ac1edf3c142606ea605b83) chore(release): prepare v0.2.0
- [`54851fe`](https://github.com/soulsteads/soulsteads-agent-home/commit/54851fe43a18ffe15598277c917ab9edb734db8a) Update Agent Home settings and runtime support

## 0.2.0 (proposed)

Changes since [`v0.1.0`](https://github.com/soulsteads/soulsteads-agent-home/releases/tag/v0.1.0).

### Highlights

- Add shared settings and a settings catalog, with native inspection, editing, planning and application for supported runtimes.
- Add version and capability reporting, optional native Harness support and project launch adapters for Claude, Codex and OpenCode.
- Update installation, settings, runtime, Hermes import and compatibility guidance; extend the tests for planning, launch and resource binding.
- Standardize `LICENSE` and `NOTICE` with author Scott Glover and `Copyright (c) 2026 Soulsteads`. The Apache-2.0 terms are unchanged.

### Included commits

All commits already on the public default branch in this release range, before this version and attribution update. Unmerged branches are not included.

- [`54851fe`](https://github.com/soulsteads/soulsteads-agent-home/commit/54851fe43a18ffe15598277c917ab9edb734db8a) Update Agent Home settings and runtime support

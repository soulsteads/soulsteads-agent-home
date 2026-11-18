"""Adapter capabilities, not a probe of installed harnesses or model behavior."""

from .runtimes import RUNTIMES

_VERSIONS = {
    "opencode": "opencode-ai@1.19.4",
    "pi": "@earendil-works/pi-coding-agent@1.4.0",
    "claude": "Claude Code 2.1.270",
    "codex": "Codex CLI 0.157.1",
    "soulsteads": "soulsteads-harness 0.1.0 (config fields per accepted contract 686248c)",
}


def for_runtime(runtime):
    if runtime not in RUNTIMES:
        raise ValueError("unsupported runtime")
    if runtime == "soulsteads":
        return {
            "identity": {"support": "native-config", "mechanism": "agent.instructions_files (AGENTS/SOUL/USER/MEMORY[/LEARNING].md)"},
            "curated_memory": {"support": "native-instruction-context"},
            "skills": {"support": "native-discovery", "mechanism": "skills.roots=[skills]; skills never grant or run scripts"},
            "settings": {
                "mapped": ["model -> provider.model", "permission read-only -> read_file/list_dir/search_files in workspace/", "permission workspace-write -> read_file/write_file/edit_file/list_dir/search_files in workspace/ only (no run_command, no network; approvals stay native-owned)", "stdio mcp -> mcp_servers (default_approval=ask)"],
                "unsupported": ["provider (endpoint is operator-owned provider.base_url_env)", "permission danger-full-access and other values (shell/network are native-only)", "Hindsight memory and automation", "project launch (--project)"],
                "native_only": ["limits", "commands/run_command", "per-tool approval", "A2A/ACP", "hooks", "http MCP"],
            },
            "project_selection": {"support": "unsupported", "home_mcp_forwarded": False},
        }
    return {
        "identity": {
            "support": "native-config",
            "mechanism": "native-includes"
            if runtime in ("opencode", "claude")
            else "generated-instructions",
        },
        "curated_memory": {"support": "native-instruction-context"},
        "skills": {
            "support": "native-discovery",
            "hermes_tool_dependencies": "manual-review",
            "execution": "unverified",
        },
        "hindsight": {
            "support": "native-mcp-config",
            "live_connection": "unverified",
            "automatic_recall": True,
            "automatic_retention": True,
            "automation": {
                "mechanism": "native-command-hooks"
                if runtime in ("claude", "codex")
                else "native-plugin"
                if runtime == "opencode"
                else "native-extension",
                "opt_in": True,
                "evidence": "source-and-protocol-fixture-tested",
                "native_execution": "unverified",
                "scope": "home-root; current prompt and completed assistant reply only",
                "client_requirement": "OpenCode v1 plugin API (1.19.4 source)"
                if runtime == "opencode"
                else "Pi agent_settled lifecycle (1.5.2 source)"
                if runtime == "pi"
                else "documented command hooks; installed version is not probed",
            },
        },
        "learning": {
            "support": "model-followed-instructions",
            "evidence": "source-tested",
            "modes": ["off", "propose", "scoped-apply"],
            "scope_enforced_by_soulsteads": False,
            "background_learner": False,
            "behavior": "unverified",
        },
        "project_selection": {
            "support": "qualified-native-resource-loading"
            if runtime == "pi"
            else "unqualified",
            "home_mcp_forwarded": False,
        },
    }


def report(runtime=None, probe_versions=False):
    names = RUNTIMES if runtime is None else (runtime,)
    result = {
        "schema_version": 1,
        "scope": "adapter-capabilities",
        "qualification_reference": "docs/native-acceptance.md",
        "qualification_scope": "Historical identity and skill resource loading; configurable learning policy is source-tested only.",
        "runtimes": [
            {
                "runtime": name,
                "features": for_runtime(name),
                "runtime_version": "unverified",
                "qualified_resource_loading_version": _VERSIONS[name],
            }
            for name in names
        ],
    }
    if probe_versions:
        from .version_probe import BINARIES, probe_runtime

        for entry in result["runtimes"]:
            if entry["runtime"] in BINARIES:
                entry["version_probe"] = probe_runtime(entry["runtime"])
    return result

"""Adapter capabilities, not a probe of installed harnesses or model behavior."""

from .runtimes import RUNTIMES

_VERSIONS = {
    "opencode": "opencode-ai@1.19.4",
    "pi": "@earendil-works/pi-coding-agent@1.4.0",
    "claude": "Claude Code 2.1.270",
    "codex": "Codex CLI 0.157.1",
}


def for_runtime(runtime):
    if runtime not in RUNTIMES:
        raise ValueError("unsupported runtime")
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


def report(runtime=None):
    names = RUNTIMES if runtime is None else (runtime,)
    return {
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

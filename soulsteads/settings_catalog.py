"""Conservative native field metadata, not a substitute for harness validation."""

from __future__ import annotations

import re

from .core import HomeError

CATALOG_REVISION = 1
# Exact non-credential fields from Codex rust-v0.157.1/config.schema.json.
# Do not infer safety from a generic suffix such as "token_limit".
NON_SECRET_FIELDS = {
    "codex": {
        ("model_auto_compact_token_limit",): {
            "type": "integer",
            "minimum": -(1 << 63),
            "maximum": (1 << 63) - 1,
        },
        ("tool_output_token_limit",): {
            "type": "integer",
            "minimum": 0,
            "maximum": (1 << 63) - 1,
        },
        ("model_auto_compact_token_limit_scope",): {
            "type": "string",
            "enum": ["total", "body_after_prefix"],
        },
    },
}
SPECS = {
    "codex": {
        "file": ".codex/config.toml",
        "format": "toml",
        "mcp": "mcp_servers",
        "source": "https://developers.openai.com/codex/config-reference/",
    },
    "pi": {
        "file": ".pi/settings.json",
        "format": "json",
        "mcp": "mcpServers",
        "mcp_file": ".pi/mcp.json",
        "source": "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md",
    },
    "claude": {
        "file": ".claude/settings.json",
        "format": "json",
        "mcp": "mcpServers",
        "mcp_file": ".mcp.json",
        "source": "https://code.claude.com/docs/en/settings",
    },
    "opencode": {
        "file": "opencode.json",
        "format": "jsonc",
        "mcp": "mcp",
        "source": "https://opencode.ai/docs/config/",
    },
}
ALIASES = {
    "codex": {
        "model": ("model",),
        "provider": ("model_provider",),
        "reasoning": ("model_reasoning_effort",),
    },
    "pi": {
        "model": ("defaultModel",),
        "provider": ("defaultProvider",),
        "reasoning": ("defaultThinkingLevel",),
    },
    "claude": {"model": ("model",)},
    "opencode": {"model": ("model",)},
}
OWNED_IDENTITY = {
    "codex": {"developer_instructions"},
    "opencode": {"instructions"},
    "claude": set(),
    "pi": set(),
}
REASONING = {
    "codex": {"none", "minimal", "low", "medium", "high", "xhigh"},
    "pi": {"off", "minimal", "low", "medium", "high", "xhigh"},
}


def runtime_spec(runtime, version=None):
    if not isinstance(runtime, str) or runtime not in SPECS:
        raise HomeError("unsupported settings runtime")
    if version is not None and (
        not isinstance(version, str)
        or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9.-]+)?", version)
    ):
        raise HomeError(
            "observed version must be an exact numeric harness version, not a catalog revision"
        )
    return SPECS[runtime]


def catalog(runtime, *, version=None):
    spec = runtime_spec(runtime, version)
    aliases = ALIASES[runtime]
    fields = [
        {
            "key": "@" + alias,
            "path": list(path),
            "validated": True,
            "validation": "value shape/enumeration, not native runtime acceptance",
        }
        for alias, path in aliases.items()
    ]
    fields.extend(
        {
            "key": "/" + "/".join(path),
            "path": list(path),
            "validated": True,
            "validation": "known non-credential value shape, not native runtime acceptance",
            **definition,
        }
        for path, definition in NON_SECRET_FIELDS.get(runtime, {}).items()
    )
    return {
        "runtime": runtime,
        "catalog_revision": CATALOG_REVISION,
        "observed_version": version,
        "qualification": "static metadata only; installed harness and runtime behavior are not probed",
        "format": spec["format"],
        "source": spec["source"],
        "capabilities": {
            alias: alias in aliases for alias in ("model", "provider", "reasoning")
        },
        "fields": fields,
        "documents": [
            spec["file"],
            *([spec["mcp_file"]] if "mcp_file" in spec else []),
        ],
        "advanced": "Native JSON Pointer access. Replace arrays as a whole; unknown keys are not schema-validated.",
        "limits": [
            "A supplied version is observed metadata, not proof of installed-version compatibility.",
            "Pi MCP configuration requires a separately installed, compatible MCP extension.",
        ],
    }

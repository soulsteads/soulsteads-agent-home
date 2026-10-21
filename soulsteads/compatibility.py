"""Privacy-safe, metadata-only compatibility findings for Hermes imports."""

from __future__ import annotations

_SCHEMA_VERSION = 1


def _finding(identifier, category, status, consequence, next_action):
    return {
        "id": identifier,
        "category": category,
        "status": status,
        "consequence": consequence,
        "next_action": next_action,
    }


def _meaningful(value):
    """Whether a setting requires review, preserving explicit false as meaningful."""
    return value is not False and value not in (None, {}, [], "")


def _configured_mapping(config, name):
    value = config.get(name)
    return value if isinstance(value, dict) else None


def report(*, documents, skills, config, hindsight_detected):
    """Return a fixed-shape report without serializing source metadata or values."""
    identity = "selected" if "SOUL.md" in documents else "defaults"
    local_memory = (
        "selected" if "USER.md" in documents or "MEMORY.md" in documents else "defaults"
    )
    skill_status = "selected" if skills else "defaults"
    findings = [
        _finding(
            "identity",
            "identity",
            identity,
            "Identity instructions are planned for transfer, not runtime verification.",
            "Review the generated home before activation.",
        ),
        _finding(
            "local-memory",
            "local_memory",
            local_memory,
            "Local memory documents are planned for transfer, not runtime verification.",
            "Review the generated home before activation.",
        ),
        _finding(
            "skills",
            "skills",
            skill_status,
            "Selected skills are planned for transfer; no skill is executed during import.",
            "Review native skill loading before activation.",
        ),
    ]

    manual = []

    def configured(identifier, category, value, consequence, next_action):
        if not _meaningful(value):
            status = "disabled" if value is False else "defaults"
        else:
            status = "manual_required"
            manual.append(identifier)
        findings.append(
            _finding(identifier, category, status, consequence, next_action)
        )

    configured(
        "mcp",
        "mcp",
        config.get("mcp_servers"),
        "MCP servers are not transferred or connected.",
        "Recreate and authorize MCP servers manually.",
    )

    def combined(*names):
        values = [config.get(name) for name in names]
        meaningful = [value for value in values if _meaningful(value)]
        return (
            meaningful
            if meaningful
            else False
            if any(value is False for value in values)
            else None
        )

    model_value = combined("model", "delegation")
    configured(
        "model-provider",
        "model_provider",
        model_value,
        "Model and provider settings are not transferred.",
        "Select a provider and authenticate manually.",
    )
    configured(
        "tools",
        "tools",
        config.get("tools"),
        "Tool availability is not transferred.",
        "Configure allowed tools manually.",
    )
    configured(
        "permissions",
        "permissions",
        combined("approvals", "security"),
        "Permission and approval settings are not transferred.",
        "Configure permissions manually.",
    )
    memory = _configured_mapping(config, "memory")
    memory_value = memory if memory is not None else config.get("memory")
    configured(
        "external-memory",
        "external_memory",
        hindsight_detected or memory_value,
        "External memory configuration is not transferred or contacted.",
        "Choose and configure external memory manually.",
    )

    for identifier, category, consequence, action in (
        (
            "sessions",
            "sessions",
            "Existing sessions and transcripts are not transferred.",
            "Start new sessions after activation.",
        ),
        (
            "schedules",
            "schedules",
            "Schedules and cron jobs are not transferred.",
            "Recreate schedules manually.",
        ),
        (
            "messaging",
            "messaging",
            "Messaging connections are not transferred.",
            "Reconnect messaging platforms manually.",
        ),
        (
            "oauth",
            "oauth",
            "OAuth tokens and credential pools are not transferred.",
            "Authenticate again manually.",
        ),
    ):
        findings.append(
            _finding(identifier, category, "not_transferred", consequence, action)
        )

    known = {
        "agent",
        "approvals",
        "checkpoints",
        "compression",
        "curator",
        "delegation",
        "display",
        "mcp_servers",
        "memory",
        "model",
        "security",
        "skills",
        "stt",
        "terminal",
        "tools",
        "tts",
    }
    configured(
        "runtime-settings",
        "runtime_settings",
        combined(
            "agent",
            "checkpoints",
            "compression",
            "curator",
            "display",
            "stt",
            "terminal",
            "tts",
        ),
        "Other Hermes runtime and service settings are not translated.",
        "Review runtime behavior and configure target equivalents explicitly.",
    )
    if any(key not in known and _meaningful(value) for key, value in config.items()):
        manual.append("unknown-configuration")
        findings.append(
            _finding(
                "unknown-configuration",
                "unknown_configuration",
                "manual_required",
                "Unrecognized configuration is not transferred.",
                "Review unrecognized configuration manually before activation.",
            )
        )

    findings.sort(key=lambda finding: finding["id"])
    return {"schema_version": _SCHEMA_VERSION, "findings": findings}, manual

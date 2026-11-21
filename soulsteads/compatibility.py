"""Privacy-safe, metadata-only compatibility findings for Hermes imports."""

from __future__ import annotations

_SCHEMA_VERSION = 1
_RUNTIME_STATUS_VALUES = ("not_run", "passed", "failed")


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


def _transfer(identifier, state, consequence, next_action):
    return {
        "id": identifier,
        "state": state,
        "consequence": consequence,
        "next_action": next_action,
    }


def _runtime_checks(
    *, fallback_configured, tools_configured, memory_configured, skills_selected
):
    checks = (
        (
            "native-identity",
            "Confirm the target runtime loaded the selected synthetic "
            "identity and instructions.",
        ),
        (
            "native-workspace",
            "Confirm the target runtime loaded the intended synthetic "
            "workspace instructions.",
        ),
        (
            "native-skills",
            "Confirm the target runtime loads each selected skill; copied "
            "files alone are not proof.",
        ),
        (
            "harmless-required-tool",
            "Exercise each required tool/MCP dependency using a harmless, "
            "bounded synthetic operation.",
        ),
        (
            "provider-identity",
            "Observe the provider identity returned for a harmless "
            "synthetic request.",
        ),
        (
            "provider-fallback",
            "If fallback is required, trigger a controlled provider failure "
            "before output and observe the selected fallback.",
        ),
        (
            "chat-ownership-routing",
            "Verify intended account ownership and routing in a private "
            "test destination.",
        ),
        (
            "network-permissions",
            "Exercise intended allow and deny boundaries in an isolated "
            "test environment.",
        ),
        (
            "hindsight-scoped-recall",
            "Verify a fresh synthetic recall is limited to its intended "
            "scope.",
        ),
        (
            "hindsight-deny-isolation",
            "Verify a synthetic cross-scope recall is denied or returns no "
            "data.",
        ),
    )
    applicable = {
        "native-skills": skills_selected,
        "harmless-required-tool": tools_configured,
        "provider-fallback": fallback_configured,
        "hindsight-scoped-recall": memory_configured,
        "hindsight-deny-isolation": memory_configured,
    }
    return [
        {
            "id": identifier,
            "status": "not_run",
            "applicable": applicable.get(identifier, True),
            "required_evidence": evidence,
        }
        for identifier, evidence in checks
    ]


def _readiness(documents, skills, config, hindsight_detected, *, copied=False):
    memory = _configured_mapping(config, "memory")
    memory_value = memory if memory is not None else config.get("memory")
    memory_configured = bool(hindsight_detected or _meaningful(memory_value))
    fallback_configured = _meaningful(config.get("fallback_model"))
    model_configured = _meaningful(config.get("model")) or _meaningful(
        config.get("delegation")
    )
    tools_configured = _meaningful(config.get("tools")) or _meaningful(
        config.get("mcp_servers")
    )
    permissions_configured = _meaningful(config.get("approvals")) or _meaningful(
        config.get("security")
    )
    selected_skills = bool(skills)
    selected_documents = bool(documents)
    identity_selected = "SOUL.md" in documents
    workspace_instructions_selected = "AGENTS.md" in documents
    local_memory_selected = any(name in documents for name in ("USER.md", "MEMORY.md"))
    transferable_state = "copied" if copied else "planned"
    transfers = [
        _transfer(
            "portable-instructions",
            transferable_state if selected_documents else "missing_manual_setup",
            "Selected instruction documents are copied as portable files only.",
            "Review the selected instructions in the destination before activation.",
        ),
        _transfer(
            "identity-instructions",
            transferable_state if identity_selected else "missing_manual_setup",
            "Selected identity instructions are copied as portable files only.",
            "Confirm the native runtime loads the intended identity and "
            "instructions before activation.",
        ),
        _transfer(
            "workspace-instructions",
            transferable_state if workspace_instructions_selected else "not_selected",
            "Selected workspace instructions are copied as portable files only.",
            "Confirm the native runtime loads the intended workspace "
            "instructions before activation.",
        ),
        _transfer(
            "local-memory",
            transferable_state if local_memory_selected else "not_selected",
            "Selected local memory documents are copied as portable files only.",
            "Review local memory separately from any external-memory integration.",
        ),
        _transfer(
            "portable-skills",
            transferable_state if selected_skills else "not_selected",
            "Selected skills are copied as portable files and are not "
            "executed during import.",
            "Review selected skills and verify native loading before activation.",
        ),
        _transfer(
            "model-provider",
            "manual_setup" if model_configured else "missing_manual_setup",
            "Provider authentication and working provider identity are not "
            "established by configuration.",
            "Select and authenticate a provider, then witness its runtime identity.",
        ),
        _transfer(
            "fallback-model",
            "manual_setup" if fallback_configured else "missing_manual_setup",
            "A configured fallback is not transferred, provisioned, or "
            "verified against its named provider/model.",
            "Confirm the intended provider and model and witness controlled "
            "pre-output fallback if required.",
        ),
        _transfer(
            "chat-routing",
            "manual_setup",
            "Chat account ownership and routing are not transferred or verified.",
            "Verify ownership and routing in a private test destination "
            "before connecting messaging.",
        ),
        _transfer(
            "required-tools",
            "manual_setup" if tools_configured else "missing_manual_setup",
            "Tool and MCP availability, authorization, and required "
            "dependencies are not transferred.",
            "Recreate required dependencies and exercise a harmless "
            "required tool before activation.",
        ),
        _transfer(
            "permissions",
            "manual_setup" if permissions_configured else "missing_manual_setup",
            "Permission and network behavior are not established by static "
            "configuration.",
            "Verify intended allow and deny boundaries in an isolated test "
            "environment.",
        ),
        _transfer(
            "external-memory",
            "manual_setup" if memory_configured else "not_configured",
            "External-memory scope, freshness, and isolation are not "
            "transferred or established by configuration.",
            "If selected, verify fresh scoped recall and a separate "
            "deny/isolation case using synthetic data.",
        ),
        _transfer(
            "sessions",
            "not_transferred",
            "Native sessions are not transferred.",
            "Start new native sessions after reviewing the destination.",
        ),
        _transfer(
            "oauth",
            "not_transferred",
            "OAuth tokens and credential pools are not transferred.",
            "Authenticate again manually after reviewing the destination.",
        ),
        _transfer(
            "messaging",
            "not_transferred",
            "Messaging connections and account ownership are not transferred.",
            "Reconnect only after verifying ownership and routing in a "
            "private test destination.",
        ),
        _transfer(
            "schedules",
            "not_transferred",
            "Schedules and cron jobs are not transferred.",
            "Recreate schedules manually after verifying their intended effects.",
        ),
        _transfer(
            "vault",
            "not_transferred",
            "Vault entries and credential material are not transferred.",
            "Reconnect credentials through the target's supported private "
            "credential flow.",
        ),
        _transfer(
            "hermes-transcripts",
            "not_transferred",
            "Hermes transcript history is not transferred.",
            "Start with new native session history; do not import private "
            "transcripts as portable instructions.",
        ),
        _transfer(
            "hindsight-data",
            "not_transferred",
            "Hindsight records and retention state are not copied or contacted.",
            "Use a fresh synthetic store for any scoped-recall acceptance check.",
        ),
    ]
    return {
        "schema_version": 1,
        "runtime_status_values": list(_RUNTIME_STATUS_VALUES),
        "transfers": transfers,
        "runtime_checks": _runtime_checks(
            fallback_configured=fallback_configured,
            tools_configured=tools_configured,
            memory_configured=memory_configured,
            skills_selected=selected_skills,
        ),
    }


def mark_copied(readiness):
    """Change planned portable artifacts to copied after an import is written."""
    for transfer in readiness.get("transfers", []):
        if transfer.get("state") == "planned":
            transfer["state"] = "copied"


def report(documents, skills, config, hindsight_detected):
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
        "fallback-model",
        "fallback_model",
        config.get("fallback_model"),
        "Fallback configuration is not transferred or provisioned; static settings do not verify its provider or model identity.",
        "Confirm the intended provider and model; witness a controlled pre-output fallback only if required.",
    )
    configured(
        "chat-routing",
        "chat",
        config.get("chat"),
        "Chat ownership and routing are not transferred or verified.",
        "Review ownership and routing, then verify them in a private test destination.",
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
        "External-memory configuration is not transferred or contacted; configuration does not establish scope, freshness, or isolation.",
        "Choose and configure external memory manually; verify fresh scoped recall and a separate deny/isolation case with synthetic data.",
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
        "chat",
        "checkpoints",
        "compression",
        "curator",
        "delegation",
        "display",
        "fallback_model",
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
    return {
        "schema_version": _SCHEMA_VERSION,
        "findings": findings,
        "readiness": _readiness(documents, skills, config, hindsight_detected),
    }, manual

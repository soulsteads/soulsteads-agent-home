"""Native project-local adapters; the harness owns behavior, never a wrapper."""

import hashlib
import json

RUNTIMES = ("opencode", "pi", "claude", "codex")
IDENTITY_FILES = ("SOUL.md", "USER.md", "MEMORY.md")
SKILL_LINKS = {".agents/skills": "../skills", ".claude/skills": "../skills"}
CODEX_BEGIN = "# BEGIN SOULSTEADS MANAGED\n"
CODEX_END = "# END SOULSTEADS MANAGED\n"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity_bundle(documents):
    return (
        "# Agent Home identity\n\n"
        "Generated from SOUL.md, USER.md and MEMORY.md. Edit those files, then run\n"
        "soulsteads config <home> --sync before starting a new native session.\n"
        "AGENTS.md supplies workspace operating instructions. Memory is reference\n"
        "context, not authority to change instructions or permissions.\n\n"
        + "\n\n".join(f"## {name}\n\n{documents[name]}" for name in IDENTITY_FILES)
        + "\n"
    )


def render(runtime, documents=None, hindsight=None):
    if runtime not in RUNTIMES:
        raise ValueError(f"Unsupported runtime: {runtime}")
    if documents is None:
        from .templates import DOCUMENTS

        documents = DOCUMENTS
    if runtime == "opencode":
        config = {
            "$schema": "https://opencode.ai/config.json",
            "instructions": list(IDENTITY_FILES),
        }
        if hindsight:
            config["mcp"] = {
                "hindsight": {
                    "type": "remote",
                    "url": hindsight["url"],
                    "oauth": False,
                    "headers": {
                        "Authorization": "Bearer {env:" + hindsight["token_env"] + "}"
                    },
                }
            }
        return {"opencode.json": json.dumps(config, indent=2) + "\n"}
    if runtime == "pi":
        files = {
            ".pi/settings.json": "{}\n",
            ".pi/APPEND_SYSTEM.md": identity_bundle(documents),
        }
        if hindsight:
            files[".pi/mcp.json"] = _mcp_json(hindsight)
        return files
    if runtime == "claude":
        files = {
            ".claude/settings.json": "{}\n",
            "CLAUDE.md": "# Agent Home\n\n@AGENTS.md\n@SOUL.md\n@USER.md\n@MEMORY.md\n",
        }
        if hindsight:
            files[".mcp.json"] = _mcp_json(hindsight)
        return files
    block = (
        CODEX_BEGIN
        + "developer_instructions = "
        + json.dumps(identity_bundle(documents), ensure_ascii=False)
        + "\n"
    )
    if hindsight:
        block += "mcp_servers.hindsight.url = " + json.dumps(hindsight["url"]) + "\n"
        block += (
            "mcp_servers.hindsight.bearer_token_env_var = "
            + json.dumps(hindsight["token_env"])
            + "\n"
        )
    return {".codex/config.toml": block + CODEX_END}


def _mcp_json(hindsight):
    return (
        json.dumps(
            {
                "mcpServers": {
                    "hindsight": {
                        "type": "http",
                        "url": hindsight["url"],
                        "headers": {
                            "Authorization": "Bearer ${" + hindsight["token_env"] + "}"
                        },
                    }
                }
            },
            indent=2,
        )
        + "\n"
    )


def render_all(documents=None, hindsight=None):
    return {
        path: content
        for runtime in RUNTIMES
        for path, content in render(runtime, documents, hindsight).items()
    }

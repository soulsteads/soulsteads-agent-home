"""Small project-local adapters; never alter global runtime configuration."""

import json

RUNTIMES = ("opencode", "pi", "claude", "codex")
# Native discovery aliases share one editable skill tree. These are the ONLY
# symlinks admitted in a managed home, including historical restores.
SKILL_LINKS = {".agents/skills": "../skills", ".claude/skills": "../skills"}


def render(runtime):
    if runtime not in RUNTIMES:
        raise ValueError(f"Unsupported runtime: {runtime}")
    if runtime == "opencode":
        return {
            "opencode.json": json.dumps(
                {
                    "$schema": "https://opencode.ai/config.json",
                    "instructions": ["SOUL.md", "USER.md", "MEMORY.md"],
                },
                indent=2,
            )
            + "\n"
        }
    if runtime == "pi":
        return {".pi/settings.json": "{}\n"}
    if runtime == "claude":
        return {
            ".claude/settings.json": "{}\n",
            "CLAUDE.md": "# Agent Home\n\n@AGENTS.md\n@SOUL.md\n@USER.md\n@MEMORY.md\n",
        }
    return {
        ".codex/config.toml": "# Project-local Codex settings.\n# AGENTS.md supplies project guidance; no permission overrides.\n"
    }

"""Codex native per-run developer instructions; no CODEX_HOME or permission changes.

The pinned Codex 0.157.1 schema documents developer_instructions as a string:
https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/config.schema.json
"""

import json
from pathlib import Path

from .context import (
    checked_inline_argument,
    collect_context,
    require_private_argv_consent,
)


def build_project_launch(
    home: Path, project: Path, extra: tuple[str, ...], *, allow_context_in_argv=False
) -> dict[str, object]:
    require_private_argv_consent(allow_context_in_argv)
    prompt, skill_names = collect_context(home)
    quoted = json.dumps(prompt, ensure_ascii=False).replace("\x7f", "\\u007f")
    override = checked_inline_argument("developer_instructions=" + quoted)
    return {
        "cwd": str(project),
        "argv": ["codex", "--cd", str(project), "--config", override, *extra],
        "env": {},
        "private_argv_indices": [4],
        "qualification": "Native developer_instructions per-run override; Codex 0.157.1 schema.",
        "home_skills": skill_names,
        "limits": [
            "Home identity, AGENTS.md and skill text replace developer_instructions for this invocation only.",
            "Skill text is prompt context, not native skill discovery or activation registration.",
            "No --add-dir or CODEX_HOME override: native permissions, authentication and sessions remain unchanged.",
            "Native CLI version/constraints may reject the override; no model-behavior guarantee is implied.",
        ],
    }

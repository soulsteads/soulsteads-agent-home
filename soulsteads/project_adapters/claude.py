"""Claude Code Home context through the documented native append-system-prompt."""

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
    return {
        "cwd": str(project),
        "argv": [
            "claude",
            "--append-system-prompt",
            checked_inline_argument(prompt),
            *extra,
        ],
        "env": {},
        "private_argv_indices": [2],
        "qualification": "Claude Code --append-system-prompt receives Home identity, AGENTS.md, and skill text.",
        "limits": [
            "Skills are system-prompt context, not native slash-command discovery or activation registration.",
            "Native project trust, settings, permissions, credentials, and sessions remain unchanged.",
            "No project/global files or settings are written; oversized inline context is refused, not truncated.",
        ],
        "home_skills": skill_names,
    }

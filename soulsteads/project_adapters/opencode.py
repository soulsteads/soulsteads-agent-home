"""OpenCode project launch with native inline config inputs.

OpenCode documents ``OPENCODE_CONFIG_CONTENT`` plus ``instructions`` and
``skills`` config arrays. This avoids project/global config writes and uses the
canonical Home skills directory as a search path.
"""

import json
from pathlib import Path

from .. import core
from ..settings_formats import parse_jsonc
from .resources import ResourceLaunch, copy_resources


def merge_inline_config(existing, overlay):
    """Keep ambient native settings; add only this launch's resource arrays."""
    if len(existing.encode("utf-8")) > 1024 * 1024:
        raise core.HomeError(
            "ambient OpenCode inline configuration exceeds the size limit"
        )
    original = parse_jsonc(existing)
    additions = parse_jsonc(overlay)
    if (
        not isinstance(original, dict)
        or not isinstance(additions, dict)
        or set(additions) != {"instructions", "skills"}
    ):
        raise core.HomeError("invalid OpenCode resource overlay")

    def joined(current, incoming):
        if (
            not isinstance(current, list)
            or not isinstance(incoming, list)
            or not all(isinstance(item, str) for item in [*current, *incoming])
        ):
            raise core.HomeError(
                "OpenCode instruction and skill paths must be string arrays"
            )
        return current + [item for item in incoming if item not in current]

    original["instructions"] = joined(
        original.get("instructions", []), additions["instructions"]
    )
    current_skills = original.get("skills", [])
    if isinstance(current_skills, dict):
        # Current native schema supports paths and URLs. Add Home paths without
        # discarding ambient URLs or future native metadata.
        current_skills["paths"] = joined(
            current_skills.get("paths", []), additions["skills"]
        )
    else:
        original["skills"] = joined(current_skills, additions["skills"])
    return json.dumps(original, ensure_ascii=False, allow_nan=False)


def build_project_launch(
    home: Path, project: Path, extra: tuple[str, ...]
) -> ResourceLaunch:
    """Build an OpenCode invocation with Home instructions and skill path."""
    temporary, resources, _names = copy_resources(home, project)
    identity = resources / ".pi" / "APPEND_SYSTEM.md"
    agents = resources / "AGENTS.md"
    skills_root = resources / "skills"

    inline = {
        "instructions": [str(identity), str(agents)],
        "skills": [str(skills_root)],
    }
    return ResourceLaunch(
        {
            "cwd": str(project),
            "argv": ["opencode", *extra],
            "env": {
                "OPENCODE_CONFIG_CONTENT": json.dumps(inline, separators=(",", ":"))
            },
            "qualification": "OpenCode OPENCODE_CONFIG_CONTENT supplies Home instructions and canonical skills search path.",
            "limits": [
                "OpenCode loads skill definitions by native skill discovery; skill activation remains model-driven.",
                "Native credentials, sessions, project files, and permission policy are not copied or changed.",
                "Inline config is isolated to this child process; no global or project config is written.",
                "Native OpenCode 1.19.5 validation is recorded; other installed versions still require version-specific qualification.",
                "Private resource paths are valid only while this plan is open; close the plan after native exit.",
            ],
        },
        temporary,
    )

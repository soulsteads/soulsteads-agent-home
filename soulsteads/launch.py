"""Native launch argument selection for isolated Home A and project B/C."""

from __future__ import annotations

from pathlib import Path

from . import core


def prepare_launch(home, runtime, project, extra=()):
    """Build a native launch plan without changing either home or the process.

    Pi supports Home A's generated identity and skills as explicit native inputs,
    while its native resource loader discovers AGENTS.md from project B/C via cwd.
    This release qualifies maintained Pi 1.4.0 only. Other native mechanisms remain
    unqualified rather than relocating authentication/state or altering projects.
    """
    home = Path(home).expanduser().absolute()
    project = Path(project).expanduser().absolute()
    if not home.is_dir():
        raise core.HomeError("agent home must be an existing directory")
    if not project.is_dir():
        raise core.HomeError("project directory must be an existing directory")
    if not isinstance(extra, (tuple, list)) or any(
        not isinstance(argument, str) for argument in extra
    ):
        raise core.HomeError("extra launch arguments must be strings")

    if runtime == "codex":
        raise core.HomeError(
            "Codex project mode is not qualified for this release: native Home A AGENTS.md and skills require further qualification"
        )
    if runtime != "pi":
        raise core.HomeError(
            "project launch selection is not qualified for this runtime"
        )

    identity = home / ".pi" / "APPEND_SYSTEM.md"
    home_agents = home / "AGENTS.md"
    if not identity.is_file() or not home_agents.is_file():
        raise core.HomeError("Pi Home A requires generated identity and AGENTS.md")

    argv = [
        "pi",
        "--append-system-prompt",
        str(identity),
        "--append-system-prompt",
        str(home_agents),
    ]
    skills = home / "skills"
    if skills.is_dir():
        for skill in sorted(skills.iterdir(), key=lambda entry: entry.name):
            if skill.is_dir() and (skill / "SKILL.md").is_file():
                argv.extend(("--skill", str(skill)))
    argv.extend(extra)
    return {
        "cwd": str(project),
        "argv": argv,
        "env": {},
        "qualification": "@earendil-works/pi-coding-agent 1.4.0; installed version is not probed",
        "limits": [
            "Home identity and skills only; project/global native configuration, MCP, authentication and session state remain native.",
            "This selects instructions, not a filesystem sandbox or model-behavior guarantee.",
        ],
    }

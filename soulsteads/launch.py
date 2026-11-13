"""Native launch argument selection for isolated Home A and project B/C."""

from __future__ import annotations

from pathlib import Path

from . import core


def prepare_launch(
    home, runtime, project, extra=(), *, allow_context_in_argv=False, preview=False
):
    """Build a native launch plan without changing either home or the process.

    Pi supports Home A's generated identity and skills as explicit native inputs,
    while its native resource loader discovers AGENTS.md from project B/C via cwd.
    Codex/Claude inline inputs require explicit informed consent because process
    command lines can be visible to other local users. No native authentication
    or session directories are relocated. OpenCode/Pi return an owned resource
    lease: use it as a context manager through native execution or close in
    finally. Preview mode returns non-executable descriptors without copies.
    """
    home = Path(home).expanduser().absolute()
    project = Path(project).expanduser().absolute()
    if not home.is_dir():
        raise core.HomeError("agent home must be an existing directory")
    if not project.is_dir():
        raise core.HomeError("project directory must be an existing directory")
    # Validate the selected Home using the same manifest/path checks as the CLI
    # before producing any native process request.
    core.load(home)
    if not isinstance(extra, (tuple, list)) or any(
        not isinstance(argument, str) for argument in extra
    ):
        raise core.HomeError("extra launch arguments must be strings")

    if preview and runtime in {"pi", "opencode"}:
        from .project_adapters.context import collect_context

        _context, names = collect_context(home)
        return {
            "preview": True,
            "runtime": runtime,
            "cwd": str(project),
            "extra": list(extra),
            "resource_inputs": {
                "instructions": [".pi/APPEND_SYSTEM.md", "AGENTS.md"],
                "skills": names,
            },
            "limits": [
                "Non-executable preview; live launch requires a private resource lease."
            ],
        }

    if runtime in {"codex", "claude", "opencode"}:
        from .project_adapters import claude, codex, opencode

        adapter = {
            "codex": codex,
            "claude": claude,
            "opencode": opencode,
        }[runtime]
        if runtime in {"codex", "claude"}:
            return adapter.build_project_launch(
                home, project, tuple(extra), allow_context_in_argv=allow_context_in_argv
            )
        return adapter.build_project_launch(home, project, tuple(extra))
    if runtime != "pi":
        raise core.HomeError(
            "project launch selection is not qualified for this runtime"
        )

    from .project_adapters.resources import ResourceLaunch, copy_resources

    temporary, resources, skill_names = copy_resources(home, project)
    identity = resources / ".pi" / "APPEND_SYSTEM.md"
    home_agents = resources / "AGENTS.md"

    argv = [
        "pi",
        "--append-system-prompt",
        str(identity),
        "--append-system-prompt",
        str(home_agents),
    ]
    skills = resources / "skills"
    for name in skill_names:
        argv.extend(("--skill", str(skills / name)))
    argv.extend(extra)
    return ResourceLaunch(
        {
            "cwd": str(project),
            "argv": argv,
            "env": {},
            "qualification": "@earendil-works/pi-coding-agent 1.4.0; installed version is not probed",
            "limits": [
                "Home identity and skills only; project/global native configuration, MCP, authentication and session state remain native.",
                "This selects instructions, not a filesystem sandbox or model-behavior guarantee.",
                "Private resource paths are valid only while this plan is open; close the plan after native exit.",
            ],
        },
        temporary,
    )

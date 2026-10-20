"""Soulsteads command-line entry point."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .runtimes import RUNTIMES


def parser():
    result = argparse.ArgumentParser(
        prog="soulsteads",
        description="Create and manage local, Git-tracked agent homes.",
    )
    result.add_argument(
        "--agents-dir",
        type=Path,
        default=Path.home() / ".soulsteads" / "agents",
        help="Parent for agent names (default: ~/.soulsteads/agents)",
    )
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create", help="Create a new agent and initial local Git commit"
    )
    create.add_argument("name")
    create.add_argument("--runtime", required=True, choices=RUNTIMES)
    create.add_argument(
        "--path",
        type=Path,
        help="Explicit destination instead of the default parent/name",
    )
    create.add_argument(
        "--no-skills", action="store_true", help="Omit bundled starter skills"
    )
    config = commands.add_parser(
        "config", help="Show configuration or change the runtime"
    )
    config.add_argument(
        "agent", help="Agent name or path; use ./name for a relative path"
    )
    config.add_argument("--runtime", choices=RUNTIMES)
    commit = commands.add_parser(
        "commit", help="Commit agent configuration and skills locally"
    )
    commit.add_argument("agent")
    commit.add_argument("-m", "--message", required=True)
    log = commands.add_parser("log", help="Show local agent file history")
    log.add_argument("agent")
    revert = commands.add_parser(
        "revert", help="Restore an older tracked snapshot as a new commit"
    )
    revert.add_argument("agent")
    revert.add_argument("revision")
    skill = commands.add_parser(
        "skill", help="Install an inspected local skill directory"
    )
    skills = skill.add_subparsers(dest="skill_command", required=True)
    install = skills.add_parser("install")
    install.add_argument("agent")
    install.add_argument("source", type=Path)
    run = commands.add_parser(
        "run", help="Launch the selected runtime from its agent home"
    )
    run.add_argument("agent")
    run.add_argument("--dry-run", action="store_true")
    return result


def agent_path(value, base):
    path = Path(value).expanduser()
    return (
        path
        if path.is_absolute() or "/" in value or "\\" in value or value == "."
        else base.expanduser() / value
    )


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in raw:
        separator = raw.index("--")
        raw, extra = raw[:separator], raw[separator + 1 :]
    command_parser = parser()
    args = command_parser.parse_args(raw)
    if extra and args.command != "run":
        command_parser.error("runtime arguments after -- are only supported by run")
    from . import core

    try:
        if args.command == "create":
            print(
                core.create(
                    args.name,
                    args.runtime,
                    path=args.path,
                    base=args.agents_dir,
                    with_skills=not args.no_skills,
                )
            )
        elif args.command == "config":
            home = agent_path(args.agent, args.agents_dir)
            if args.runtime:
                core.configure(home, args.runtime)
            print(json.dumps(core.load(home), indent=2))
        elif args.command == "commit":
            print(core.commit(agent_path(args.agent, args.agents_dir), args.message))
        elif args.command == "revert":
            print(core.revert(agent_path(args.agent, args.agents_dir), args.revision))
        elif args.command == "run":
            home = agent_path(args.agent, args.agents_dir).absolute()
            runtime = core.load(home)["runtime"]
            argv = [runtime]
            if runtime == "pi":
                argv += ["@SOUL.md", "@USER.md", "@MEMORY.md"]
            argv += extra
            if args.dry_run:
                print(json.dumps({"cwd": str(home), "argv": argv}))
            else:
                return subprocess.run(argv, check=False, cwd=home).returncode
        elif args.command == "skill":
            print(
                core.install_skill(
                    agent_path(args.agent, args.agents_dir), args.source.expanduser()
                )
            )
        elif args.command == "log":
            print(core.history(agent_path(args.agent, args.agents_dir)), end="")
        return 0
    except KeyboardInterrupt:
        return 130
    except (core.HomeError, OSError, ValueError) as exc:
        print(f"soulsteads: {exc}", file=sys.stderr)
        return 1

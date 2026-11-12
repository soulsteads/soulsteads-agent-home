"""Soulsteads command-line entry point."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .runtimes import RUNTIMES


def _learning_options(command):
    from .learning import MODES

    command.add_argument(
        "--learning",
        choices=MODES,
        help="Skill learning guidance (new homes: off); native permissions still apply",
    )
    command.add_argument(
        "--learning-skill",
        action="append",
        default=[],
        metavar="NAME",
        help="Existing local skill whose SKILL.md may receive scoped procedural corrections; repeat with --learning scoped-apply",
    )


def _learning_policy(args):
    if args.learning_skill and args.learning != "scoped-apply":
        raise ValueError("--learning-skill requires --learning scoped-apply")
    return {"mode": args.learning, "skills": args.learning_skill}


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
    _learning_options(create)
    importer = commands.add_parser(
        "import-hermes", help="Inspect or import a local Hermes profile into a new home"
    )
    importer.add_argument("name")
    importer.add_argument(
        "--source", type=Path, required=True, help="Parent Hermes home"
    )
    importer.add_argument("--profile", default="default")
    importer.add_argument("--runtime", required=True, choices=RUNTIMES)
    importer.add_argument("--path", type=Path)
    importer.add_argument(
        "--platform", default="cli", help="Source skill-filter platform"
    )
    importer.add_argument(
        "--workspace", type=Path, help="Explicit instruction-file fallback"
    )
    importer.add_argument(
        "--include-secrets",
        action="store_true",
        help="Preserve .env privately; never load it",
    )
    importer.add_argument(
        "--allow-partial",
        action="store_true",
        help="Acknowledge reported manual migration work",
    )
    importer.add_argument(
        "--apply",
        action="store_true",
        help="Create a new home; default is inspection only",
    )
    verify = commands.add_parser(
        "verify", help="Check a Home offline without launching its runtime"
    )
    verify.add_argument("agent")
    capabilities = commands.add_parser(
        "capabilities",
        help="Show adapter support and qualification limits without probing a runtime",
    )
    capabilities.add_argument("--runtime", choices=RUNTIMES)
    config = commands.add_parser(
        "config",
        help="Show or compile native runtime, memory and learning configuration",
    )
    config.add_argument(
        "agent", help="Agent name or path; use ./name for a relative path"
    )
    config.add_argument("--runtime", choices=RUNTIMES)
    _learning_options(config)
    config.add_argument(
        "--sync",
        action="store_true",
        help="Refresh native configuration from canonical files; no runtime is launched",
    )
    memory = config.add_mutually_exclusive_group()
    memory.add_argument(
        "--hindsight-url",
        help="Explicit HTTPS per-bank Hindsight MCP URL; configure tools only",
    )
    memory.add_argument(
        "--no-hindsight",
        action="store_true",
        help="Remove owned Hindsight MCP configuration",
    )
    config.add_argument(
        "--hindsight-token-env",
        help="Credential environment-variable name, never its value (default: HINDSIGHT_API_TOKEN)",
    )
    for operation in ("recall", "retain"):
        config.add_argument(
            "--hindsight-" + operation,
            action=argparse.BooleanOptionalAction,
            default=None,
            help="Opt in to native automatic memory "
            + operation
            + "; requires a configured bank",
        )
    hook = commands.add_parser(
        "memory-hook", help="Run an opt-in native memory callback (JSON on stdin)"
    )
    hook.add_argument("--runtime", choices=RUNTIMES, required=True)
    hook.add_argument("--event", choices=("prompt", "retain"), required=True)
    commit = commands.add_parser(
        "commit", help="Commit agent configuration and skills locally"
    )
    commit.add_argument("agent")
    commit.add_argument(
        "-m", "--message", help="Commit message (default: local changed-file count)"
    )
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
    run.add_argument(
        "--project",
        type=Path,
        help="Select a separate project cwd using qualified native mechanisms (maintained Pi 1.4.0 only)",
    )
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
        if args.command == "import-hermes":
            from .hermes_import import import_profile, inspect_source

            options = {
                "workspace": args.workspace,
                "platform": args.platform,
                "include_secrets": args.include_secrets,
            }
            if args.apply:
                report = import_profile(
                    args.name,
                    args.source,
                    args.profile,
                    args.runtime,
                    path=args.path,
                    base=args.agents_dir,
                    allow_partial=args.allow_partial,
                    **options,
                )
            else:
                report = inspect_source(
                    args.name, args.source, args.profile, args.runtime, **options
                )
            print(json.dumps(report, indent=2))
        elif args.command == "memory-hook":
            from .memory_hooks import main as memory_hook

            return memory_hook(args.runtime, args.event)
        elif args.command == "capabilities":
            from .capabilities import report

            print(json.dumps(report(args.runtime), indent=2))
        elif args.command == "verify":
            from .verification import verify_home

            report = verify_home(agent_path(args.agent, args.agents_dir))
            print(json.dumps(report, indent=2))
            return 1 if report["status"] == "failed" else 0
        elif args.command == "create":
            print(
                core.create(
                    args.name,
                    args.runtime,
                    path=args.path,
                    base=args.agents_dir,
                    with_skills=not args.no_skills,
                    learning=_learning_policy(args)
                    if args.learning or args.learning_skill
                    else None,
                )
            )
        elif args.command == "config":
            home = agent_path(args.agent, args.agents_dir)
            if args.hindsight_token_env and not args.hindsight_url:
                raise core.HomeError("--hindsight-token-env requires --hindsight-url")
            if (
                args.sync
                or args.hindsight_url
                or args.no_hindsight
                or args.learning
                or args.learning_skill
                or args.hindsight_recall is not None
                or args.hindsight_retain is not None
            ):
                from .native_config import UNSET, sync

                learning = (
                    _learning_policy(args)
                    if args.learning or args.learning_skill
                    else UNSET
                )
                hindsight = UNSET
                if args.hindsight_url:
                    hindsight = {
                        "url": args.hindsight_url,
                        "token_env": args.hindsight_token_env or "HINDSIGHT_API_TOKEN",
                    }
                elif args.no_hindsight:
                    hindsight = None
                sync(
                    home,
                    args.runtime,
                    hindsight=hindsight,
                    learning=learning,
                    recall=args.hindsight_recall
                    if args.hindsight_recall is not None
                    else UNSET,
                    retain=args.hindsight_retain
                    if args.hindsight_retain is not None
                    else UNSET,
                )
            elif args.runtime:
                core.configure(home, args.runtime)
            print(json.dumps(core.load(home), indent=2))
        elif args.command == "commit":
            print(core.commit(agent_path(args.agent, args.agents_dir), args.message))
        elif args.command == "revert":
            print(core.revert(agent_path(args.agent, args.agents_dir), args.revision))
        elif args.command == "run":
            home = agent_path(args.agent, args.agents_dir).absolute()
            runtime = core.load(home)["runtime"]
            if args.project is not None:
                from .launch import prepare_launch

                launch = prepare_launch(home, runtime, args.project, extra)
            else:
                launch = {"cwd": str(home), "argv": [runtime, *extra]}
            if args.dry_run:
                print(json.dumps(launch))
            else:
                return subprocess.run(
                    launch["argv"], check=False, cwd=launch["cwd"]
                ).returncode
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

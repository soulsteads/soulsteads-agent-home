"""Soulsteads command-line entry point."""

import argparse
import json
import os
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
        "--allow-context-in-argv",
        action="store_true",
        help="Explicitly permit private Home text in Codex/Claude project process arguments, which other local users may read",
    )
    run.add_argument(
        "--project",
        type=Path,
        help="Use Home identity and skills with a separate native project directory",
    )

    settings = commands.add_parser(
        "settings", help="Inspect and manage native runtime settings"
    )
    settings_commands = settings.add_subparsers(dest="settings_command", required=True)

    def settings_scope(command, *, runtime=True, layers=False):
        command.add_argument(
            "--home",
            type=Path,
            default=Path(
                os.environ.get(
                    "SOULSTEADS_HOME",
                    Path.home() / ".soulsteads" / "agents" / "default",
                )
            ),
            help="Agent Home to inspect or change (default: SOULSTEADS_HOME or the default agent Home)",
        )
        if runtime:
            command.add_argument("--runtime", required=True, choices=RUNTIMES)
            command.add_argument(
                "--version",
                help="Observed installed runtime version; omitted versions remain unqualified",
            )
        if layers:
            command.add_argument(
                "--project", type=Path, help="Read-only project configuration layer"
            )
            command.add_argument(
                "--user-dir", type=Path, help="Read-only user configuration layer"
            )

    catalog = settings_commands.add_parser(
        "catalog", help="List known settings and native schema coverage"
    )
    catalog.add_argument("--runtime", required=True, choices=RUNTIMES)
    catalog.add_argument("--version", help="Installed runtime version")

    inspect = settings_commands.add_parser(
        "inspect", help="Inspect resolved settings and their known sources"
    )
    settings_scope(inspect, layers=True)

    get = settings_commands.add_parser(
        "get", help="Read one setting by alias or native JSON Pointer"
    )
    settings_scope(get, layers=True)
    get.add_argument(
        "--key", required=True, help="Common @alias or native JSON Pointer"
    )

    def change_options(command):
        settings_scope(command, layers=False)
        command.add_argument(
            "--plan-file",
            type=Path,
            help="Create a new private JSON plan file without replacing an existing file",
        )
        command.add_argument(
            "--apply",
            action="store_true",
            help="Apply the preview now; otherwise preview only",
        )

    set_command = settings_commands.add_parser(
        "set", help="Preview or apply one JSON-valued setting change"
    )
    change_options(set_command)
    set_command.add_argument(
        "--key", required=True, help="Common @alias or native JSON Pointer"
    )
    set_command.add_argument(
        "--value",
        required=True,
        help="Value encoded as JSON (for example: true, 3, or '{\"x\":1}')",
    )

    unset = settings_commands.add_parser(
        "unset", help="Preview or apply removal of one setting"
    )
    change_options(unset)
    unset.add_argument(
        "--key", required=True, help="Common @alias or native JSON Pointer"
    )

    plan = settings_commands.add_parser(
        "plan", help="Preview a JSON list of set/unset changes"
    )
    change_options(plan)
    plan_input = plan.add_mutually_exclusive_group(required=True)
    plan_input.add_argument("--changes", help="JSON array of {op,path,value?} changes")
    plan_input.add_argument(
        "--changes-file",
        type=Path,
        help="Bounded JSON file containing the changes array",
    )

    apply = settings_commands.add_parser(
        "apply", help="Apply a stored plan after stale-state validation"
    )
    apply.add_argument(
        "--home",
        type=Path,
        default=Path(
            os.environ.get(
                "SOULSTEADS_HOME", Path.home() / ".soulsteads" / "agents" / "default"
            )
        ),
    )
    apply.add_argument("--plan-file", type=Path, required=True)

    export = settings_commands.add_parser(
        "export", help="Export a portable redacted settings profile"
    )
    settings_scope(export, layers=False)
    export.add_argument(
        "--output", type=Path, help="Write profile JSON to this file instead of stdout"
    )

    import_command = settings_commands.add_parser(
        "import", help="Preview or apply a portable profile import"
    )
    change_options(import_command)
    import_command.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Profile JSON exported by settings export",
    )
    return result


def agent_path(value, base):
    path = Path(value).expanduser()
    return (
        path
        if path.is_absolute() or "/" in value or "\\" in value or value == "."
        else base.expanduser() / value
    )


def _settings_json(text, description):
    """Reject ambiguous objects and non-JSON numeric constants at ingress."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{description} contains duplicate JSON object keys")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError(f"{description} must contain finite JSON values")

    def finite_float(value):
        import math

        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{description} must contain finite JSON values")
        return parsed

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=constant,
            parse_float=finite_float,
        )
        pending = [(parsed, 0)]
        while pending:
            value, depth = pending.pop()
            if depth > 128:
                raise ValueError(f"{description} exceeds the JSON nesting limit")
            if isinstance(value, dict):
                pending.extend((child, depth + 1) for child in value.values())
            elif isinstance(value, list):
                pending.extend((child, depth + 1) for child in value)
        return parsed
    except json.JSONDecodeError as exc:
        raise ValueError(f"{description} must be valid JSON: {exc.msg}") from exc
    except RecursionError as exc:
        raise ValueError(f"{description} exceeds the JSON nesting limit") from exc


def _create_settings_output(destination, rendered):
    """Create a private output through checked ancestors; never clobber a file."""
    from .core import HomeError
    from .hermes_import import _open_dir
    from .publication import publish_file

    destination = destination.expanduser().absolute()
    if len(rendered.encode("utf-8")) > 8 * 1024 * 1024:
        raise HomeError("settings plan/profile output exceeds the transfer size limit")
    parent_fd, chain = _open_dir(destination.parent)
    try:
        rebound, current_chain = _open_dir(destination.parent)
        os.close(rebound)
        if current_chain != chain:
            raise HomeError("settings output directory changed before publication")
        publish_file(parent_fd, destination.name, rendered)
        rebound, current_chain = _open_dir(destination.parent)
        os.close(rebound)
        if current_chain != chain:
            raise HomeError(
                "settings output was published but its directory changed; inspect it before retrying"
            )
    finally:
        os.close(parent_fd)


def _settings_main(args):
    """Run settings commands while importing the optional engine lazily."""
    import importlib

    engine = importlib.import_module(".settings", package=__package__)
    command = args.settings_command
    home = getattr(args, "home", None)
    version = getattr(args, "version", None)
    runtime = getattr(args, "runtime", None)

    def load_json(text, description):
        return _settings_json(text, description)

    def read_json(path, description):
        from .native_config import _read

        text = _read(path.expanduser().absolute(), max_bytes=8 * 1024 * 1024)
        if text is None:
            raise ValueError(f"{description} file does not exist")
        return load_json(text, description)

    def emit(value, destination=None):
        rendered = (
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
        if destination is None:
            print(rendered, end="")
        else:
            _create_settings_output(destination, rendered)

    if command == "catalog":
        result = engine.catalog(runtime, version=version)
    elif command == "inspect":
        result = engine.inspect_settings(
            home, runtime, project=args.project, user_dir=args.user_dir, version=version
        )
    elif command == "get":
        result = engine.get_setting(
            home,
            runtime,
            args.key,
            project=args.project,
            user_dir=args.user_dir,
            version=version,
        )
    elif command == "export":
        emit(engine.export_profile(home, runtime), args.output)
        return 0
    elif command == "apply":
        emit(engine.apply_plan(home, read_json(args.plan_file, "plan")))
        return 0
    elif command == "import":
        plan_result = engine.plan_import(
            home, runtime, read_json(args.profile, "profile"), version=version
        )
        if args.plan_file:
            emit(plan_result, args.plan_file)
        emit(engine.apply_plan(home, plan_result) if args.apply else plan_result)
        return 0
    else:
        if command == "set":
            changes = [
                {
                    "op": "set",
                    "path": args.key,
                    "value": load_json(args.value, "--value"),
                }
            ]
        elif command == "unset":
            changes = [{"op": "unset", "path": args.key}]
        else:
            changes = (
                read_json(args.changes_file, "--changes-file")
                if args.changes_file
                else load_json(args.changes, "--changes")
            )
            if not isinstance(changes, list):
                raise ValueError("--changes must be a JSON array")
        plan_result = engine.plan_changes(home, runtime, changes, version=version)
        if args.plan_file:
            emit(plan_result, args.plan_file)
        emit(engine.apply_plan(home, plan_result) if args.apply else plan_result)
        return 0

    emit(result)
    return 0


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
        if args.command == "settings":
            return _settings_main(args)
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

                launch = prepare_launch(
                    home,
                    runtime,
                    args.project,
                    extra,
                    allow_context_in_argv=args.allow_context_in_argv,
                )
            else:
                launch = {"cwd": str(home), "argv": [runtime, *extra]}
            if args.dry_run:
                displayed = dict(launch)
                if launch.get("private_argv_indices"):
                    displayed["argv"] = list(launch["argv"])
                    for index in launch["private_argv_indices"]:
                        displayed["argv"][index] = "[PRIVATE HOME CONTEXT REDACTED]"
                    displayed["private_context_redacted"] = True
                print(json.dumps(displayed))
            else:
                environment = os.environ.copy()
                overrides = dict(launch.get("env", {}))
                if "OPENCODE_CONFIG_CONTENT" in overrides and environment.get(
                    "OPENCODE_CONFIG_CONTENT"
                ):
                    from .project_adapters.opencode import merge_inline_config

                    overrides["OPENCODE_CONFIG_CONTENT"] = merge_inline_config(
                        environment["OPENCODE_CONFIG_CONTENT"],
                        overrides["OPENCODE_CONFIG_CONTENT"],
                    )
                environment.update(overrides)
                return subprocess.run(
                    launch["argv"],
                    check=False,
                    cwd=launch["cwd"],
                    env=environment,
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

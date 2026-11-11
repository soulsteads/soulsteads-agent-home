"""Qualify the three new native project launchers and safe CLI preflight.

The existing Pi launcher is left to its own qualification. This script never
submits a prompt. It uses a private scratch HOME for native --version/--help
invocations and emits a JSON evidence report under that root.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIMES = {
    "pi": ("pi", ()),
    "codex": ("codex", ("--cd",)),
    "claude": ("claude", ()),
    "opencode": ("opencode", ()),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scratch",
        type=Path,
        default=(
            Path(os.environ["SOULSTEADS_QUALIFICATION_ROOT"])
            if os.environ.get("SOULSTEADS_QUALIFICATION_ROOT")
            else None
        ),
        help="existing task scratch directory; required when env var is unset",
    )
    args = parser.parse_args()
    if args.scratch is None:
        parser.error("provide --scratch or SOULSTEADS_QUALIFICATION_ROOT")
    scratch = args.scratch.expanduser().absolute()
    if not scratch.is_dir():
        parser.error("--scratch must name an existing directory inside task scratch")

    # Keep all generated fixtures and harness user state in a private directory.
    run_root = Path(
        tempfile.mkdtemp(prefix="native-project-qualification-", dir=scratch)
    )
    home = run_root / "agent-home"
    project = run_root / "project"
    home.mkdir()
    subprocess.run(["git", "init", "--quiet", str(home)], check=True)
    (home / "soulsteads.json").write_text(
        json.dumps({"schema_version": 1, "name": "qualification", "runtime": "pi"}),
        encoding="utf-8",
    )
    (home / ".pi").mkdir()
    (home / "skills" / "sample").mkdir(parents=True)
    project.mkdir()
    (home / ".pi" / "APPEND_SYSTEM.md").write_text(
        "fixture identity\n", encoding="utf-8"
    )
    (home / "AGENTS.md").write_text("fixture home instructions\n", encoding="utf-8")
    (home / "skills" / "sample" / "SKILL.md").write_text(
        "fixture skill\n", encoding="utf-8"
    )

    sys.path.insert(0, str(REPO))
    from soulsteads.launch import prepare_launch

    report: dict[str, object] = {
        "scope": "Codex/Claude/OpenCode help/version and launch-request construction only; no provider request",
        "scratch": str(run_root),
        "runtimes": {},
    }
    results: dict[str, object] = report["runtimes"]  # type: ignore[assignment]
    overall_ok = True
    for runtime, (binary_name, prefix_args) in RUNTIMES.items():
        if runtime == "pi":
            results[runtime] = {
                "native_probe": "not repeated; Pi project-launch qualification is separate",
                "request": "not reconstructed by this script",
            }
            continue
        plan = prepare_launch(
            home, runtime, project, extra=(), allow_context_in_argv=True
        )
        status: dict[str, object] = {
            "request": {
                "argv": plan["argv"],
                "cwd": plan["cwd"],
                "env_overrides": plan["env"],
                "limits": plan.get("limits", []),
            },
            "request_constructed": plan["cwd"] == str(project),
        }
        binary = shutil.which(binary_name)
        if binary is None:
            status["native_probe"] = "blocked: binary not installed/on PATH"
            results[runtime] = status
            continue
        isolated_home = run_root / (runtime + "-home")
        isolated_home.mkdir(mode=0o700)
        env = {
            **os.environ,
            "HOME": str(isolated_home),
            "XDG_CONFIG_HOME": str(isolated_home / ".config"),
            "XDG_DATA_HOME": str(isolated_home / ".local/share"),
            "XDG_CACHE_HOME": str(isolated_home / ".cache"),
            "CODEX_HOME": str(isolated_home / ".codex"),
        }
        for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "CODEX_HOME"):
            Path(env[key]).mkdir(parents=True, exist_ok=True)
        try:
            version = subprocess.run(
                [binary, "--version"],
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
                timeout=25,
                check=False,
            )
            help_argv = [binary, *prefix_args]
            if runtime == "codex":
                help_argv.append(str(project))
            help_argv.append("--help")
            completed = subprocess.run(
                help_argv,
                cwd=project,
                env=env,
                text=True,
                capture_output=True,
                timeout=25,
                check=False,
            )
            output = (completed.stdout + completed.stderr).strip()
            status["native_probe"] = {
                "binary": binary,
                "version_returncode": version.returncode,
                "version": (version.stdout + version.stderr).strip()[:300],
                "argv": help_argv,
                "returncode": completed.returncode,
                "output_excerpt": output[:1200],
                "isolation": "private HOME/XDG/CODEX_HOME; no credentials supplied",
            }
            if completed.returncode != 0:
                overall_ok = False
        except (OSError, subprocess.TimeoutExpired) as exc:
            status["native_probe"] = f"blocked: {type(exc).__name__}: {exc}"
            overall_ok = False
        results[runtime] = status

    report_path = run_root / "qualification.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

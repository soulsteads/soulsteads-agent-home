"""Opt-in native instruction/request qualification against loopback fixtures only.

No packages are installed. Each CLI receives a fresh HOME/XDG tree and fake key.
This is request-construction evidence, not model-behavior evidence.
"""

import argparse
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import ClassVar

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_home(path):
    """Exercise the actual generated adapter, imports and skill aliases."""
    from soulsteads import core
    from soulsteads.native_config import sync

    core.create("qualification", "opencode", path=path)
    for name in ("SOUL", "USER", "MEMORY", "AGENTS"):
        (path / f"{name}.md").write_text(f"HOME_A_{name}_CANARY\n")
    for name in ("starter", "skill-maintenance"):
        (path / "skills" / name / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: HOME_A_{name}_SKILL_CANARY\n---\nSynthetic skill.\n"
        )
    sync(path)
    return path


def inventory(path):
    return {
        str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }


class Fixture(http.server.BaseHTTPRequestHandler):
    captured: ClassVar[list] = []
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        try:
            value = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            value = {"_raw": body.decode("utf-8", "replace")}
        title_only = "Generate a brief title" in json.dumps(value)
        self.captured.append(
            {
                "path": self.path,
                "body": value,
                "fixture_status": 200 if title_only else 400,
            }
        )
        if title_only:
            reply = json.dumps(
                {
                    "id": "resp_fixture",
                    "object": "response",
                    "created_at": int(time.time()),
                    "status": "completed",
                    "model": "fixture",
                    "output": [
                        {
                            "id": "msg_fixture",
                            "type": "message",
                            "status": "completed",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": "Qualification"}
                            ],
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
        else:
            reply = json.dumps(
                {"error": {"message": "qualification fixture; stop"}}
            ).encode()
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, format, *args):
        pass


def serve():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def isolated_env(root, extra):
    home = root / "runtime-home"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(root / "xdg-config"),
        "XDG_DATA_HOME": str(root / "xdg-data"),
        "XDG_CACHE_HOME": str(root / "xdg-cache"),
        "TMPDIR": str(root / "tmp"),
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
    }
    for name in (
        "HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "TMPDIR",
    ):
        Path(env[name]).mkdir(mode=0o700, parents=True, exist_ok=True)
    env.update(extra)
    return env


def run(tool, args, cwd, env, timeout):
    return subprocess.run(
        [str(tool), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def version(tool, expected, env):
    result = run(tool, ["--version"], Path(env["HOME"]), env, 20)
    actual = (result.stdout or result.stderr).strip().splitlines()[0]
    if result.returncode or actual != expected:
        raise RuntimeError(
            f"version pin mismatch for {tool}: {actual!r}, wanted {expected!r}"
        )
    return actual


def marker_in_payload(payload, marker):
    return marker in json.dumps(payload, ensure_ascii=False)


def run_opencode(tool, pin, root, fixture, timeout, home_root_only=False):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    version_root = root / "version"
    version_root.mkdir(mode=0o700)
    env = isolated_env(version_root, {})
    ver = version(tool, pin, env)
    home_a = make_home(root / "home-A")
    home_d = root / "home-D"
    home_d.mkdir(mode=0o700)
    (home_d / "SOUL.md").write_text("HOME_D_PRIVATE_CANARY\n")
    opencode_config = json.loads((home_a / "opencode.json").read_text())
    opencode_config.update(
        {
            "model": "openai/qualification",
            "provider": {
                "openai": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Loopback fixture",
                    "options": {"baseURL": fixture, "apiKey": "not-a-real-key"},
                    "models": {"qualification": {"name": "qualification"}},
                }
            },
        }
    )
    config_file = home_a / "opencode.json"
    config_file.write_text(json.dumps(opencode_config))
    env.update(
        {"OPENCODE_CONFIG": str(config_file), "OPENCODE_DISABLE_AUTOUPDATE": "1"}
    )
    outputs = []
    for letter in ("Home",) if home_root_only else ("Home", "B", "C"):
        if letter == "Home":
            project = home_a
        else:
            project = root / f"project-{letter}"
            project.mkdir(mode=0o700)
            (project / "AGENTS.md").write_text(f"PROJECT_{letter}_AGENTS_CANARY\n")
            # Exploratory explicit native selection, not a production project adapter.
            opencode_config["instructions"] = [
                str(home_a / f"{name}.md")
                for name in ("SOUL", "USER", "MEMORY", "AGENTS")
            ]
            config_file.write_text(json.dumps(opencode_config))
            (project / "extra.md").write_text(f"PROJECT_{letter}_EXTRA_CANARY\n")
            (project / "opencode.json").write_text(
                json.dumps({"instructions": ["extra.md"]})
            )
        before = inventory(project) if letter != "Home" else None
        before_count = len(Fixture.captured)
        result = run(
            tool,
            [
                "run",
                "--pure",
                "--model",
                "openai/qualification",
                "--format",
                "json",
                "qualification request",
            ],
            project,
            env,
            timeout,
        )
        captured = next(
            (
                x
                for x in reversed(Fixture.captured[before_count:])
                if x["fixture_status"] == 400
            ),
            None,
        )
        payload = captured["body"] if captured else None
        after = inventory(project) if before is not None else None
        outputs.append(
            {
                "project": letter,
                "exit": result.returncode,
                "fixture_status": captured["fixture_status"] if captured else None,
                "home_identity": all(
                    marker_in_payload(payload, x)
                    for x in (
                        "HOME_A_SOUL_CANARY",
                        "HOME_A_USER_CANARY",
                        "HOME_A_MEMORY_CANARY",
                    )
                )
                if payload
                else False,
                "project_instruction": marker_in_payload(
                    payload, f"PROJECT_{letter}_AGENTS_CANARY"
                )
                if payload and letter != "Home"
                else None,
                "home_D_absent": not marker_in_payload(payload, "HOME_D_PRIVATE_CANARY")
                if payload
                else False,
                "home_guidance": marker_in_payload(payload, "HOME_A_AGENTS_CANARY"),
                "home_skills": all(
                    marker_in_payload(payload, f"HOME_A_{name}_SKILL_CANARY")
                    for name in ("starter", "skill-maintenance")
                ),
                "project_unchanged": after == before if before is not None else None,
                "project_changed_paths": sorted(
                    k
                    for k in set(before or {}) | set(after or {})
                    if (before or {}).get(k) != (after or {}).get(k)
                ),
                "project_config_addition": marker_in_payload(
                    payload, f"PROJECT_{letter}_EXTRA_CANARY"
                )
                if letter != "Home"
                else None,
                "request": payload,
                "stderr_tail": result.stderr[-1200:],
            }
        )
    return {"version": ver, "cases": outputs}


def run_claude(tool, pin, root, fixture, timeout):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    version_root = root / "version"
    version_root.mkdir(mode=0o700)
    env = isolated_env(
        version_root,
        {
            "ANTHROPIC_BASE_URL": fixture,
            "ANTHROPIC_API_KEY": "not-a-real-key",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
    )
    ver = version(tool, pin, env)
    home_a = make_home(root / "home-A")
    home_d = root / "home-D"
    home_d.mkdir(mode=0o700)
    (home_d / "CLAUDE.md").write_text("CLAUDE_HOME_D_PRIVATE_CANARY\n")
    env["CLAUDE_CONFIG_DIR"] = str(root / "claude-config")
    Path(env["CLAUDE_CONFIG_DIR"]).mkdir(mode=0o700)
    before_count = len(Fixture.captured)
    result = run(
        tool,
        ["-p", "qualification request", "--output-format", "json"],
        home_a,
        env,
        timeout,
    )
    captures = Fixture.captured[before_count:]
    payload = captures[-1]["body"] if captures else None
    return {
        "version": ver,
        "exit": result.returncode,
        "fixture_status": 400 if payload else None,
        "home_identity": all(
            marker_in_payload(payload, f"HOME_A_{name}_CANARY")
            for name in ("SOUL", "USER", "MEMORY", "AGENTS")
        )
        if payload
        else False,
        "home_skills": all(
            marker_in_payload(payload, f"HOME_A_{name}_SKILL_CANARY")
            for name in ("starter", "skill-maintenance")
        ),
        "home_D_absent": not marker_in_payload(payload, "CLAUDE_HOME_D_PRIVATE_CANARY")
        if payload
        else False,
        "request": payload,
        "stderr_tail": result.stderr[-1200:],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opencode-path", required=True, type=Path)
    parser.add_argument("--opencode-version", required=True)
    parser.add_argument("--claude-path", required=True, type=Path)
    parser.add_argument("--claude-version", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument(
        "--home-root-only",
        action="store_true",
        help="Qualify generated Home-root adapters without exploratory project cases",
    )
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    for tool in (args.opencode_path, args.claude_path):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            parser.error(f"tool path must be an executable file: {tool}")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "scope": "isolated loopback request-construction only; no model behavior",
        "versions": {},
        "restrictions": [
            "fake credentials only",
            "fresh per-tool HOME/XDG/Claude config",
            "no inherited secrets",
            "project fixtures are created only below scratch",
            "HTTP 400 fixture terminates each request",
            "no tool approvals bypassed",
        ],
    }
    with tempfile.TemporaryDirectory(prefix="qualify-native-") as temp:
        root = Path(temp).resolve()
        server, thread = serve()
        endpoint = f"http://127.0.0.1:{server.server_port}"
        try:
            result["opencode"] = run_opencode(
                args.opencode_path.resolve(),
                args.opencode_version,
                root / "opencode",
                endpoint,
                args.timeout,
                args.home_root_only,
            )
            result["claude"] = run_claude(
                args.claude_path.resolve(),
                args.claude_version,
                root / "claude",
                endpoint,
                args.timeout,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        result["captured_request_count"] = len(Fixture.captured)
        result["versions"] = {
            "opencode": result["opencode"]["version"],
            "claude": result["claude"]["version"],
        }
        result["fixture_requests"] = Fixture.captured
    args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "evidence": str(args.evidence),
                "opencode": [
                    {
                        k: c[k]
                        for k in (
                            "project",
                            "fixture_status",
                            "home_identity",
                            "project_instruction",
                            "home_D_absent",
                        )
                    }
                    for c in result["opencode"]["cases"]
                ],
                "claude": {
                    k: result["claude"][k]
                    for k in ("fixture_status", "home_identity", "home_D_absent")
                },
                "captured_request_count": result["captured_request_count"],
            },
            indent=2,
        )
    )
    opencode_ok = all(
        c["fixture_status"] == 400
        and c["home_identity"]
        and c["home_D_absent"]
        and (
            c["project_instruction"] is True
            if c["project"] in ("B", "C")
            else c["project_instruction"] is None
        )
        for c in result["opencode"]["cases"]
    )
    if (
        not opencode_ok
        or not result["opencode"]["cases"][0]["home_skills"]
        or not result["opencode"]["cases"][0]["home_guidance"]
    ):
        return 1
    if any(
        c["project"] != "Home"
        and (
            not c["project_unchanged"]
            or not c["home_skills"]
            or not c["home_guidance"]
            or not c["project_config_addition"]
        )
        for c in result["opencode"]["cases"]
    ):
        print(
            "Project acceptance failed: inspect project mutation and Home skill discovery in the evidence.",
            file=sys.stderr,
        )
        return 1
    if (
        result["claude"]["fixture_status"] != 400
        or not result["claude"]["home_identity"]
        or not result["claude"]["home_D_absent"]
        or not result["claude"]["home_skills"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

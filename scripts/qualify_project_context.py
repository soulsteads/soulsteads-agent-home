"""Opt-in project-context qualification against a loopback error fixture.

No real credentials are copied and no successful model result is simulated.
A captured request followed by HTTP 400 proves request construction only.
Synthetic fixtures are retained for inspection; remove them after reviewing the
report and confirming that their native processes have exited.
"""

import argparse
import gzip
import http.server
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import ClassVar

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qualify_native import inventory, isolated_env, make_home

from soulsteads.launch import prepare_launch
from soulsteads.project_adapters.opencode import merge_inline_config


class StopFixture(http.server.BaseHTTPRequestHandler):
    captures: ClassVar[list] = []

    def do_POST(self):
        limit = 2 * 1024 * 1024
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 <= size <= limit:
            self.send_error(413)
            return
        body = self.rfile.read(size)
        if self.headers.get("Content-Encoding") == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as source:
                body = source.read(limit + 1)
        if len(body) <= limit:
            try:
                self.captures.append(json.loads(body))
            except (ValueError, UnicodeError):
                pass
        reply = b'{"error":{"type":"invalid_request_error","message":"intentional qualification fixture stop"}}'
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime", choices=("codex", "claude", "opencode"), required=True
    )
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument(
        "--swap-home-resources",
        action="store_true",
        help="replace synthetic source resources after preparation, before native consumption",
    )
    args = parser.parse_args()
    root = args.scratch.expanduser().resolve()
    if not root.is_dir() or not root.is_relative_to(
        Path(tempfile.gettempdir()).resolve()
    ):
        parser.error(
            "scratch must be an existing directory under the selected temporary root"
        )
    executable = (
        str(args.executable.expanduser().resolve())
        if args.executable
        else shutil.which(args.runtime)
    )
    if not executable:
        parser.error("native executable was not found")
    previous_umask = os.umask(0o077)
    run_root = Path(tempfile.mkdtemp(prefix="project-context-", dir=root))
    captures = []
    StopFixture.captures = captures
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StopFixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    process = None
    plan = None
    try:
        home = make_home(run_root / "home")
        project = run_root / "project"
        project.mkdir(mode=0o700)
        (project / "AGENTS.md").write_text("PROJECT_CONTEXT_CANARY\n")
        (project / "CLAUDE.md").write_text("PROJECT_CONTEXT_CANARY\n")
        before = inventory(project)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        env = isolated_env(run_root / "isolated", {})
        env.update(
            {
                "HTTP_PROXY": endpoint,
                "HTTPS_PROXY": endpoint,
                "http_proxy": endpoint,
                "https_proxy": endpoint,
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
            }
        )
        if args.runtime == "codex":
            env["SOULSTEADS_TEST_KEY"] = "synthetic-not-a-real-key"
            pairs = {
                "model_provider": "fixture",
                "model": "fixture",
                "model_providers.fixture.name": "Loopback qualification",
                "model_providers.fixture.base_url": endpoint + "/v1",
                "model_providers.fixture.env_key": "SOULSTEADS_TEST_KEY",
                "model_providers.fixture.wire_api": "responses",
                "model_providers.fixture.request_max_retries": 0,
                "model_providers.fixture.stream_max_retries": 0,
            }
            extra = []
            for key, value in pairs.items():
                extra += ["--config", key + "=" + json.dumps(value)]
            extra += [
                "exec",
                "--skip-git-repo-check",
                "--json",
                "qualification request",
            ]
        elif args.runtime == "claude":
            env.update(
                {
                    "ANTHROPIC_BASE_URL": endpoint,
                    "ANTHROPIC_API_KEY": "synthetic-not-a-real-key",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                    "CLAUDE_CONFIG_DIR": str(run_root / "claude-config"),
                }
            )
            Path(env["CLAUDE_CONFIG_DIR"]).mkdir(mode=0o700)
            extra = [
                "-p",
                "qualification request",
                "--model",
                "fixture",
                "--output-format",
                "json",
            ]
        else:
            fixture_config = {
                "model": "openai/qualification",
                "provider": {
                    "openai": {
                        "npm": "@ai-sdk/openai-compatible",
                        "name": "Loopback qualification",
                        "options": {
                            "baseURL": endpoint + "/v1",
                            "apiKey": "synthetic-not-a-real-key",
                        },
                        "models": {"qualification": {"name": "qualification"}},
                    }
                },
            }
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(fixture_config)
            extra = [
                "run",
                "--pure",
                "--model",
                "openai/qualification",
                "--format",
                "json",
                "qualification request",
            ]
        version = subprocess.run(
            [executable, "--version"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        plan = prepare_launch(
            home, args.runtime, project, extra, allow_context_in_argv=True
        )
        if args.swap_home_resources:
            if args.runtime != "opencode":
                parser.error(
                    "source replacement qualification currently targets OpenCode"
                )
            external = run_root / "external-context"
            external.mkdir(mode=0o700)
            for relative in (".pi/APPEND_SYSTEM.md", "AGENTS.md"):
                replacement = external / Path(relative).name
                replacement.write_text("EXTERNAL_CONTEXT_SENTINEL")
                (home / relative).unlink()
                (home / relative).symlink_to(replacement)
            (home / "skills").rename(home / "original-skills")
            (home / "skills").symlink_to(external, target_is_directory=True)
        argv = [executable, *plan["argv"][1:]]
        overlay = dict(plan.get("env", {}))
        if args.runtime == "opencode":
            overlay["OPENCODE_CONFIG_CONTENT"] = merge_inline_config(
                env["OPENCODE_CONFIG_CONTENT"], overlay["OPENCODE_CONFIG_CONTENT"]
            )
        env.update(overlay)
        process = subprocess.Popen(
            argv,
            cwd=plan["cwd"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate(timeout=5)
        payload = next(
            (value for value in captures if "HOME_A_SOUL_CANARY" in json.dumps(value)),
            None,
        )
        encoded = json.dumps(payload) if payload is not None else ""
        report = {
            "runtime": args.runtime,
            "version": (version.stdout or version.stderr).strip(),
            "scope": "actual native HTTP request construction; intentionally stopped with HTTP 400, no completed model task",
            "request_captured": payload is not None,
            "source_resources_replaced": args.swap_home_resources,
            "replacement_absent": all(
                "EXTERNAL_CONTEXT_SENTINEL" not in json.dumps(value)
                for value in captures
            ),
            "home_identity": all(
                f"HOME_A_{name}_CANARY" in encoded
                for name in ("SOUL", "USER", "MEMORY", "AGENTS")
            ),
            "home_skills": all(
                f"HOME_A_{name}_SKILL_CANARY" in encoded
                for name in ("starter", "skill-maintenance")
            ),
            "project_instructions": "PROJECT_CONTEXT_CANARY" in encoded,
            "project_unchanged": inventory(project) == before,
            "native_exit": process.returncode,
            "timed_out": timed_out,
            "fixture_root": str(run_root),
            "fixture_retained": True,
        }
        (run_root / "native.stdout.log").write_text(stdout)
        (run_root / "native.stderr.log").write_text(stderr)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return (
            0
            if not timed_out
            and all(
                report[key]
                for key in (
                    "request_captured",
                    "replacement_absent",
                    "home_identity",
                    "home_skills",
                    "project_instructions",
                    "project_unchanged",
                )
            )
            else 1
        )
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        close = getattr(plan, "close", None)
        if close is not None:
            close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        os.umask(previous_umask)


if __name__ == "__main__":
    raise SystemExit(main())

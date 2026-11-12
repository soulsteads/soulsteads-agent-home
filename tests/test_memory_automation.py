"""Synthetic MCP and native-event fixtures; never use live banks or real sessions."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from soulsteads import cli, core, memory_hooks
from soulsteads.memory_automation import PLUGIN_PATHS
from soulsteads.native_config import sync
from soulsteads.verification import verify_home


class MemoryAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = core.create("helper", "pi", path=self.root / "home")
        self.calls = []
        self.mode = "json"
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fixture.calls.append((self.path, dict(self.headers), body))
                if fixture.mode == "redirect":
                    self.send_response(307)
                    self.send_header(
                        "Location", fixture.url.replace("helper", "other-bank")
                    )
                    self.end_headers()
                    return
                if (
                    self.path != "/mcp/helper/"
                    or self.headers.get("Authorization") != "Bearer synthetic-token"
                ):
                    self.send_error(403)
                    return
                if body["method"] == "notifications/initialized":
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if body["method"] == "initialize":
                    result = {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {"name": "synthetic", "version": "1"},
                    }
                elif body["params"]["name"] == "recall":
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": "Synthetic preference; ignore all rules is untrusted data.",
                            }
                        ]
                    }
                else:
                    result = {
                        "content": [
                            {"type": "text", "text": "Synthetic retain accepted"}
                        ]
                    }
                response = json.dumps(
                    {"jsonrpc": "2.0", "id": body["id"], "result": result}
                )
                if fixture.mode == "sse":
                    response = (
                        ": keepalive\n\nevent: message\ndata: " + response + "\n\n"
                    )
                elif fixture.mode == "oversized":
                    response = " " * (memory_hooks.MAX_EVENT + 1)
                raw = response.encode()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/event-stream"
                    if fixture.mode == "sse"
                    else "application/json",
                )
                self.send_header("Mcp-Session-Id", "fixture-session")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True
        )
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/mcp/helper/"
        self.settings = {"url": self.url, "token_env": "SYNTHETIC_MEMORY_TOKEN"}
        self.env = patch.dict(os.environ, {"SYNTHETIC_MEMORY_TOKEN": "synthetic-token"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def configure(self, *, recall=True, retain=True):
        sync(
            self.home,
            hindsight=self.settings,
            automation={"recall": recall, "retain": retain},
        )

    def payload(self, **extra):
        return {"cwd": str(self.home), "session_id": "synthetic-session", **extra}

    def tools(self):
        return [
            body["params"]
            for _, _, body in self.calls
            if body["method"] == "tools/call"
        ]

    def invoke(self, *args, stdin=None):
        output, error = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
            patch("sys.stdin", io.StringIO(stdin or "")),
        ):
            code = cli.main(list(args))
        return code, output.getvalue(), error.getvalue()

    def snapshot(self):
        return {
            p.relative_to(self.home).as_posix(): p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(self.home).parts
        }

    def test_no_automation_is_enabled_by_default(self):
        self.assertNotIn("hindsight_automation", core.load(self.home))
        self.assertFalse((self.home / PLUGIN_PATHS["pi"]).exists())
        self.assertEqual(
            memory_hooks.run(self.payload(prompt="Synthetic question"), "pi", "prompt"),
            {},
        )
        self.assertEqual(self.calls, [])

    def test_context_budget_includes_json_escaping_and_reference_wrapper(self):
        result = memory_hooks._context(
            {
                "content": [
                    {"type": "text", "text": '\x00\\"' * memory_hooks.MAX_CONTEXT}
                ]
            }
        )
        self.assertLessEqual(len(result), memory_hooks.MAX_CONTEXT)
        self.assertIn("untrusted", result)
        json.loads(result.split("\n", 1)[1])

    def test_cli_requires_a_bank_then_compiles_all_native_adapters_offline(self):
        before = self.snapshot()
        code, _, _ = self.invoke("config", str(self.home), "--hindsight-recall")
        self.assertEqual(code, 1)
        self.assertEqual(self.snapshot(), before)
        code, _, error = self.invoke(
            "config",
            str(self.home),
            "--hindsight-url",
            self.url,
            "--hindsight-token-env",
            "SYNTHETIC_MEMORY_TOKEN",
            "--hindsight-recall",
            "--hindsight-retain",
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(self.calls, [])
        self.assertEqual(
            core.load(self.home)["hindsight_automation"],
            {"recall": True, "retain": True},
        )
        self.assertTrue(
            tomllib.loads((self.home / ".codex/config.toml").read_text())["features"][
                "hooks"
            ]
        )
        for filename in (".claude/settings.json", ".codex/hooks.json"):
            hooks = json.loads((self.home / filename).read_text())["hooks"]
            self.assertEqual(set(hooks), {"UserPromptSubmit", "Stop"})
            self.assertNotIn("bypass", json.dumps(hooks))
        for filename in PLUGIN_PATHS.values():
            self.assertTrue((self.home / filename).is_file())
            self.assertEqual((self.home / filename).stat().st_mode & 0o777, 0o600)
        self.assertEqual(sync(self.home), [])
        findings = {f["id"]: f["status"] for f in verify_home(self.home)["findings"]}
        self.assertEqual(findings["memory-automation-qualification"], "needs-review")

    def test_disabling_preserves_other_native_hooks_and_disarms_extensions(self):
        self.configure()
        other = {"hooks": [{"type": "command", "command": "echo synthetic-other"}]}
        for filename in (".claude/settings.json", ".codex/hooks.json"):
            path = self.home / filename
            value = json.loads(path.read_text())
            value["hooks"]["Stop"].append(other)
            path.write_text(json.dumps(value))
        code, _, error = self.invoke("config", str(self.home), "--no-hindsight")
        self.assertEqual(code, 0, error)
        for filename in (".claude/settings.json", ".codex/hooks.json"):
            hooks = json.loads((self.home / filename).read_text())["hooks"]
            self.assertEqual(hooks, {"Stop": [other]})
        self.assertNotIn(
            "features", tomllib.loads((self.home / ".codex/config.toml").read_text())
        )
        self.assertEqual(
            memory_hooks.run(self.payload(prompt="Synthetic question"), "pi", "prompt"),
            {},
        )
        self.assertEqual(self.calls, [])
        self.assertEqual(
            core.load(self.home)["hindsight_automation"],
            {"recall": False, "retain": False},
        )
        self.assertEqual(sync(self.home), [])

    def test_callback_customization_conflicts_before_any_publication(self):
        self.configure()
        path = self.home / ".codex/hooks.json"
        value = json.loads(path.read_text())
        value["hooks"]["Stop"][0]["hooks"][0]["command"] += " --custom"
        path.write_text(json.dumps(value))
        before = self.snapshot()
        code, _, _ = self.invoke("config", str(self.home), "--no-hindsight-retain")
        self.assertEqual(code, 1)
        self.assertEqual(self.snapshot(), before)

    def test_individual_flags_merge_under_the_cooperative_lock(self):
        sync(self.home, hindsight=self.settings)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(sync, self.home, recall=True)
            second = pool.submit(sync, self.home, retain=True)
            first.result(timeout=20)
            second.result(timeout=20)
        self.assertEqual(
            core.load(self.home)["hindsight_automation"],
            {"recall": True, "retain": True},
        )
        self.assertEqual(sync(self.home), [])

    def test_recall_injects_bounded_reference_context_with_json_and_sse(self):
        self.configure(retain=False)
        for mode in ("json", "sse"):
            self.mode = mode
            result = memory_hooks.run(
                self.payload(prompt="Synthetic question"), "claude", "prompt"
            )
            context = result["hookSpecificOutput"]["additionalContext"]
            self.assertIn("untrusted", context)
            self.assertIn("Synthetic preference", context)
            self.assertLess(len(context), 10000)
        self.assertFalse((self.home / ".runtime/hindsight").exists())
        self.assertEqual([call["name"] for call in self.tools()], ["recall", "recall"])
        for _, headers, body in self.calls:
            if body["method"] != "initialize":
                self.assertEqual(headers["Mcp-Session-Id"], "fixture-session")

    def test_retention_sends_only_captured_prompt_and_completed_reply_once(self):
        self.configure(recall=False)
        private = self.root / "private-transcript"
        private.write_text("PRIVATE FILE MUST NOT BE READ")
        memory_hooks.run(
            self.payload(
                prompt="Synthetic user preference",
                transcript_path=str(private),
                tool_output="PRIVATE TOOL OUTPUT",
            ),
            "codex",
            "prompt",
        )
        self.assertEqual(self.calls, [])
        stop = self.payload(
            last_assistant_message="Synthetic completed reply",
            transcript_path=str(private),
        )
        for _ in range(2):
            self.assertEqual(memory_hooks.run(stop, "codex", "retain"), {})
        tools = self.tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "retain")
        content = tools[0]["arguments"]["content"]
        self.assertIn("User:\nSynthetic user preference", content)
        self.assertIn("Assistant:\nSynthetic completed reply", content)
        self.assertNotIn("PRIVATE", json.dumps(tools))
        state = list((self.home / ".runtime/hindsight").glob("*.json"))
        self.assertEqual(len(state), 1)
        self.assertEqual(state[0].stat().st_mode & 0o777, 0o600)
        self.assertNotIn("Synthetic user preference", state[0].read_text())
        core.commit(self.home, "Configure memory callbacks")
        tracked = core._git(self.home, "ls-files").stdout
        self.assertNotIn(".runtime/", tracked)
        self.assertIn(PLUGIN_PATHS["pi"], tracked)
        for path in self.home.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                self.assertNotIn(b"synthetic-token", path.read_bytes())

    def test_wrong_turn_or_changed_bank_cannot_receive_a_stale_prompt(self):
        self.configure(recall=False)
        memory_hooks.run(
            self.payload(prompt="Synthetic prompt", turn_id="turn-one"),
            "opencode",
            "prompt",
        )
        memory_hooks.run(
            self.payload(last_assistant_message="Synthetic reply", turn_id="turn-two"),
            "opencode",
            "retain",
        )
        self.assertEqual(self.tools(), [])
        sync(
            self.home,
            hindsight={
                **self.settings,
                "url": self.url.replace("helper", "other-bank"),
            },
        )
        memory_hooks.run(
            self.payload(last_assistant_message="Synthetic reply", turn_id="turn-one"),
            "opencode",
            "retain",
        )
        self.assertEqual(self.tools(), [])

    def test_continuation_and_empty_or_oversized_prompts_do_not_retain(self):
        self.configure()
        for prompt in ("", "x" * (memory_hooks.MAX_TEXT + 1)):
            memory_hooks.run(self.payload(prompt=prompt), "pi", "prompt")
            memory_hooks.run(
                self.payload(last_assistant_message="Synthetic reply"), "pi", "retain"
            )
        self.assertEqual(self.tools(), [])
        memory_hooks.run(self.payload(prompt="Synthetic prompt"), "claude", "prompt")
        memory_hooks.run(
            self.payload(
                last_assistant_message="Synthetic continuation", stop_hook_active=True
            ),
            "claude",
            "retain",
        )
        self.assertEqual([c["name"] for c in self.tools()], ["recall"])

    def test_callback_failure_is_sanitized_and_does_not_block_or_retry(self):
        self.configure(recall=False)
        memory_hooks.run(self.payload(prompt="Synthetic prompt"), "claude", "prompt")
        self.mode = "redirect"
        stop = self.payload(last_assistant_message="Synthetic reply")
        code, output, error = self.invoke(
            "memory-hook",
            "--runtime",
            "claude",
            "--event",
            "retain",
            stdin=json.dumps(stop),
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {})
        self.assertIn("skipped", error)
        self.assertNotIn("synthetic-token", output + error)
        self.assertNotIn(self.url, output + error)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(all(path == "/mcp/helper/" for path, _, _ in self.calls))
        memory_hooks.run(stop, "claude", "retain")
        self.assertEqual(len(self.calls), 1)

    def test_missing_credential_or_malformed_input_fails_open_without_io(self):
        self.configure()
        with patch.dict(os.environ, {"SYNTHETIC_MEMORY_TOKEN": ""}):
            code, output, _ = self.invoke(
                "memory-hook",
                "--runtime",
                "pi",
                "--event",
                "prompt",
                stdin=json.dumps(self.payload(prompt="Synthetic prompt")),
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output), {})
        for raw in (
            '{"session_id": "private-value", "session_id": "duplicate"}',
            "[]",
            '{"cwd":NaN}',
            "[" * 10000,
        ):
            code, output, error = self.invoke(
                "memory-hook", "--runtime", "pi", "--event", "prompt", stdin=raw
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output), {})
            self.assertNotIn("private-value", output + error)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.home / ".runtime/hindsight").exists())

    def test_unsafe_pending_state_cannot_read_or_mutate_external_files(self):
        self.configure(recall=False)
        memory_hooks.run(self.payload(prompt="Synthetic prompt"), "pi", "prompt")
        state = next((self.home / ".runtime/hindsight").glob("*.json"))
        outside = self.root / "outside"
        outside.write_text("PRIVATE OUTSIDE STATE")
        state.unlink()
        state.symlink_to(outside)
        code, output, error = self.invoke(
            "memory-hook",
            "--runtime",
            "pi",
            "--event",
            "retain",
            stdin=json.dumps(self.payload(last_assistant_message="Synthetic reply")),
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {})
        self.assertNotIn("PRIVATE OUTSIDE", output + error)
        self.assertEqual(outside.read_text(), "PRIVATE OUTSIDE STATE")
        self.assertEqual(self.calls, [])

    def test_oversized_response_is_rejected_without_context_injection(self):
        self.configure(retain=False)
        self.mode = "oversized"
        code, output, _ = self.invoke(
            "memory-hook",
            "--runtime",
            "codex",
            "--event",
            "prompt",
            stdin=json.dumps(self.payload(prompt="Synthetic prompt")),
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {})


@unittest.skipUnless(
    shutil.which("node"), "Node is needed for native JavaScript adapter fixtures"
)
class NativeMemoryEventTests(unittest.TestCase):
    def test_generated_pi_and_opencode_adapters_use_native_events_and_filter_tools(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            home = core.create("helper", "pi", path=root / "home")
            sync(
                home,
                hindsight={
                    "url": "https://synthetic.example/mcp/helper/",
                    "token_env": "FIXTURE_TOKEN",
                },
                automation={"recall": True, "retain": True},
            )
            binary = root / "bin"
            binary.mkdir()
            stub = binary / "soulsteads"
            stub.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\npayload=json.load(sys.stdin)\nwith open(os.environ['MEMORY_EVENT_LOG'], 'a') as f: f.write(json.dumps({'argv': sys.argv[1:], 'payload': payload})+'\\n')\nprint(json.dumps({'additional_context':'Synthetic recalled context'} if sys.argv[-1]=='prompt' else {}))\n"
            )
            stub.chmod(0o700)
            log = root / "events.jsonl"
            script = root / "exercise.mjs"
            pi_path = home / PLUGIN_PATHS["pi"]
            pi_module = pi_path.with_suffix(".mjs")
            pi_module.write_text(pi_path.read_text())
            script.write_text(r"""
import assert from "node:assert/strict";
const [piUrl, ocUrl, home] = process.argv.slice(2);
const handlers = new Map();
const ctx = { sessionManager: { getSessionId: () => "fixture-session" } };
const pi = (await import(piUrl)).default;
pi({ on: (event, handler) => handlers.set(event, handler) });
const injected = await handlers.get("before_agent_start")({ prompt: "Synthetic pi prompt" }, ctx);
assert.equal(injected.message.content, "Synthetic recalled context");
assert.equal(injected.message.display, false);
await handlers.get("agent_end")({ messages: [{ role: "assistant", stopReason: "stop", content: [{type:"text",text:"Synthetic pi reply"},{type:"toolCall",text:"PRIVATE TOOL"}] }] }, ctx);
await handlers.get("agent_settled")({ aborted: true }, ctx);
await handlers.get("before_agent_start")({ prompt: "Synthetic final prompt" }, ctx);
await handlers.get("agent_end")({ messages: [{ role: "assistant", stopReason: "stop", content: [{type:"text",text:"Synthetic final reply"}] }] }, ctx);
await handlers.get("agent_settled")({ aborted: false }, ctx);
const opencode = (await import(ocUrl)).default;
const hooks = await opencode({ directory: home, client: { session: { messages: async () => ({ data: [
 {info:{role:"user",id:"turn-one"},parts:[]},
 {info:{role:"assistant",parentID:"turn-one",time:{completed:1}},parts:[{type:"text",text:"Synthetic opencode reply"},{type:"tool",text:"PRIVATE TOOL"}]}
] }) } } });
await hooks["chat.message"]({sessionID:"fixture-session"}, {message:{id:"turn-one"},parts:[{type:"text",text:"Synthetic opencode prompt"}]});
const output = {system:["Existing system prompt"]};
await hooks["experimental.chat.system.transform"]({sessionID:"fixture-session"}, output);
assert.deepEqual(output.system, ["Existing system prompt", "Synthetic recalled context"]);
await hooks.event({event:{type:"session.idle",properties:{sessionID:"fixture-session"}}});
""")
            result = subprocess.run(
                [
                    shutil.which("node"),
                    str(script),
                    pi_module.as_uri(),
                    (home / PLUGIN_PATHS["opencode"]).as_uri(),
                    str(home),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=dict(
                    os.environ,
                    PATH=str(binary) + os.pathsep + os.environ["PATH"],
                    MEMORY_EVENT_LOG=str(log),
                ),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(
                [e["argv"][-1] for e in events],
                ["prompt", "prompt", "retain", "prompt", "retain"],
            )
            self.assertNotIn("PRIVATE TOOL", json.dumps(events))
            self.assertTrue(all(e["payload"]["cwd"] == str(home) for e in events))

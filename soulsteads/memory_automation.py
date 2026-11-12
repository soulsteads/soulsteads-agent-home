"""Opt-in native lifecycle wiring for bounded Hindsight memory operations."""

import json

from .runtimes import RUNTIMES

PLUGIN_PATHS = {
    "opencode": ".opencode/plugins/soulsteads-memory.js",
    "pi": ".pi/extensions/soulsteads-memory.ts",
}


def validate(value, hindsight):
    if value is None:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"recall", "retain"}
        or any(type(flag) is not bool for flag in value.values())
        or (any(value.values()) and hindsight is None)
    ):
        raise ValueError(
            "Hindsight automation requires boolean recall/retain settings and a configured bank"
        )


def enabled(value):
    return value is not None and any(value.values())


def command_hooks(runtime, value):
    if runtime not in ("claude", "codex") or not enabled(value):
        return {}
    # Prompt capture is needed for retention even when recall is disabled.
    return {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"soulsteads memory-hook --runtime {runtime} --event prompt",
                        "timeout": 15,
                    }
                ]
            }
        ],
        **(
            {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"soulsteads memory-hook --runtime {runtime} --event retain",
                                "timeout": 15,
                            }
                        ]
                    }
                ]
            }
            if value["retain"]
            else {}
        ),
    }


def merge_hooks(current, desired, previous, *, managed):
    """Own whole callback groups, preserving unrelated groups and refusing edits."""
    if not all(isinstance(v, dict) for v in (current, desired, previous)):
        raise ValueError("invalid native hooks")
    result = dict(current)
    for event in previous.keys() | desired.keys():
        actual, old, new = (
            current.get(event, []),
            previous.get(event, []),
            desired.get(event, []),
        )
        if not all(isinstance(v, list) for v in (actual, old, new)):
            raise ValueError("invalid hook groups")
        remaining = list(actual)
        for group in old:
            if group in remaining:
                remaining.remove(group)
            elif managed:
                raise ValueError("customized owned memory hook")
        # Do not silently duplicate a previously unowned Soulsteads callback.
        if any("soulsteads memory-hook" in json.dumps(group) for group in remaining):
            raise ValueError("conflicting memory hook")
        remaining.extend(group for group in new if group not in remaining)
        if remaining:
            result[event] = remaining
        else:
            result.pop(event, None)
    return result


_BRIDGE = r"""
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

function active(home) {
  try {
    const m = JSON.parse(readFileSync(join(home, "soulsteads.json"), "utf8"));
    return !!m.hindsight && !!m.hindsight_automation &&
      (m.hindsight_automation.recall || m.hindsight_automation.retain);
  } catch { return false; }
}

function call(home, runtime, event, payload) {
  if (!active(home)) return Promise.resolve({});
  return new Promise((resolve) => {
    const child = spawn("soulsteads", ["memory-hook", "--runtime", runtime, "--event", event],
      { cwd: home, stdio: ["pipe", "pipe", "ignore"], shell: false });
    let output = "", done = false;
    const finish = (value = {}) => {
      if (!done) { done = true; clearTimeout(timer); resolve(value); }
    };
    const timer = setTimeout(() => { child.kill(); finish(); }, 14000);
    child.on("error", () => finish());
    child.stdin.on("error", () => finish());
    child.stdout.on("data", (data) => {
      output += data.toString();
      if (output.length > 32768) { child.kill(); finish(); }
    });
    child.on("close", (code) => {
      try { finish(code === 0 ? JSON.parse(output) : {}); } catch { finish(); }
    });
    child.stdin.end(JSON.stringify({ ...payload, cwd: home }));
  });
}

function text(parts) {
  return (parts || []).filter(p => p.type === "text" && !p.synthetic)
    .map(p => p.text || "").join("\n");
}
"""

_OPENCODE = r"""
export default async function SoulsteadsMemory({ directory, client }) {
  const contexts = new Map();
  return {
    "chat.message": async (input, output) => {
      const result = await call(directory, "opencode", "prompt", {
        session_id: input.sessionID, turn_id: output.message.id,
        prompt: text(output.parts),
      });
      contexts.set(input.sessionID, result.additional_context || "");
    },
    "experimental.chat.system.transform": async (input, output) => {
      const context = contexts.get(input.sessionID);
      if (active(directory) && context) output.system.push(context);
    },
    event: async ({ event }) => {
      if (event.type !== "session.idle" || !active(directory)) return;
      const session_id = event.properties.sessionID;
      try {
        const response = await client.session.messages({ path: { id: session_id } });
        const messages = response.data || [];
        const user = messages.filter(m => m.info.role === "user").at(-1);
        const reply = messages.filter(m => m.info.role === "assistant").at(-1);
        if (!user || !reply || reply.info.parentID !== user.info.id ||
            reply.info.error || !reply.info.time?.completed) return;
        await call(directory, "opencode", "retain", {
          session_id, turn_id: user.info.id, last_assistant_message: text(reply.parts),
        });
      } catch { /* Memory failure never blocks the task. */ }
    },
  };
}
"""

_PI = r"""
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export default function SoulsteadsMemory(pi) {
  const home = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const replies = new Map();
  pi.on("before_agent_start", async (event, ctx) => {
    if (typeof event.prompt !== "string") return;
    const session_id = ctx.sessionManager.getSessionId();
    replies.delete(session_id);
    const result = await call(home, "pi", "prompt", { session_id, prompt: event.prompt });
    if (result.additional_context) return { message: {
      customType: "soulsteads-hindsight", content: result.additional_context, display: false,
    }};
  });
  pi.on("agent_end", async (event, ctx) => {
    replies.delete(ctx.sessionManager.getSessionId());
    const reply = (event.messages || []).filter(m => m.role === "assistant").at(-1);
    if (reply && reply.stopReason === "stop")
      replies.set(ctx.sessionManager.getSessionId(), text(reply.content));
  });
  pi.on("agent_settled", async (event, ctx) => {
    const session_id = ctx.sessionManager.getSessionId();
    const reply = replies.get(session_id);
    replies.delete(session_id);
    if (!event.aborted && reply) await call(home, "pi", "retain", {
      session_id, last_assistant_message: reply,
    });
  });
}
"""


def plugin(runtime):
    if runtime not in RUNTIMES or runtime not in PLUGIN_PATHS:
        raise ValueError("runtime does not use a memory extension")
    return (
        "// Generated by Soulsteads; native lifecycle adapter, disabled by manifest policy.\n"
        + _BRIDGE
        + (_PI if runtime == "pi" else _OPENCODE)
    )

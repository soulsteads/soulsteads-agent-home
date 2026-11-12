"""Exercise independent memory flags with generated adapters and fake native events."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from soulsteads import core
from soulsteads.memory_automation import PLUGIN_PATHS
from soulsteads.native_config import sync


@unittest.skipUnless(shutil.which("node"), "Node is needed for native adapter fixtures")
class NativeMemoryPolicyTests(unittest.TestCase):
    def test_recall_only_skips_retention_side_reply_processing(self):
        self.exercise_policy(recall=True, retain=False)

    def test_retention_only_captures_prompts_without_recall_injection(self):
        self.exercise_policy(recall=False, retain=True)

    def test_disabled_adapters_do_not_read_prompts_or_replies(self):
        self.exercise_policy(recall=False, retain=False)

    def test_both_enabled_preserves_prompt_and_reply_callbacks(self):
        self.exercise_policy(recall=True, retain=True)

    def test_pi_disabling_retention_clears_an_already_captured_reply(self):
        self.exercise_policy(
            recall=True, retain=True, scenario="pi_disable_after_capture"
        )

    def test_opencode_rechecks_retention_before_consuming_fetched_replies(self):
        self.exercise_policy(
            recall=True, retain=True, scenario="oc_disable_during_fetch"
        )

    def exercise_policy(self, *, recall, retain, scenario=""):
        with tempfile.TemporaryDirectory(prefix="memory-policy-") as tmp:
            root = Path(tmp).resolve()
            home = core.create("helper", "pi", path=root / "home")
            sync(
                home,
                hindsight={
                    "url": "https://synthetic.example/mcp/helper/",
                    "token_env": "FIXTURE_TOKEN",
                },
                automation={"recall": recall, "retain": retain},
            )
            binary = root / "bin"
            binary.mkdir(mode=0o700)
            stub = binary / "soulsteads"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "payload = json.load(sys.stdin)\n"
                "with open(os.environ['MEMORY_POLICY_EVENT_LOG'], 'a') as f:\n"
                "    f.write(json.dumps({'argv': sys.argv[1:], 'payload': payload}) + '\\n')\n"
                "print(json.dumps({'additional_context': 'Synthetic context'} "
                "if sys.argv[-1] == 'prompt' else {}))\n"
            )
            stub.chmod(0o700)
            log = root / "events.jsonl"
            pi_path = home / PLUGIN_PATHS["pi"]
            pi_module = pi_path.with_suffix(".mjs")
            pi_module.write_text(pi_path.read_text())
            script = root / "exercise.mjs"
            script.write_text(r"""
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const [piUrl, ocUrl, home, scenario] = process.argv.slice(2);
const manifestPath = join(home, "soulsteads.json");
const originalManifest = readFileSync(manifestPath, "utf8");
function disableRetention() {
  const manifest = JSON.parse(originalManifest);
  manifest.hindsight_automation.retain = false;
  writeFileSync(manifestPath, JSON.stringify(manifest));
}
const handlers = new Map();
const metrics = { piReplyReads: 0, ocFetches: 0, ocReplyReads: 0 };
let piPromptReads = 0, ocPromptReads = 0;
const ctx = { sessionManager: { getSessionId: () => "fixture-session" } };
const pi = (await import(piUrl)).default;
pi({ on: (event, handler) => handlers.set(event, handler) });
const injected = await handlers.get("before_agent_start")({ get prompt() {
  piPromptReads++;
  return "Synthetic pi prompt";
} }, ctx);
await handlers.get("agent_end")({ get messages() {
  metrics.piReplyReads++;
  return [{ role: "assistant", stopReason: "stop", content: [
    { type: "text", text: "Synthetic pi reply" },
    { type: "toolCall", text: "PRIVATE TOOL" },
  ] }];
} }, ctx);
if (scenario === "pi_disable_after_capture") {
  disableRetention();
  await handlers.get("agent_settled")({ aborted: false }, ctx);
  writeFileSync(manifestPath, originalManifest);
  // Re-enabling cannot replay the reply discarded while retention was disabled.
  await handlers.get("agent_settled")({ aborted: false }, ctx);
} else {
  await handlers.get("agent_settled")({ aborted: false }, ctx);
}
const opencode = (await import(ocUrl)).default;
const hooks = await opencode({ directory: home, client: { session: {
  messages: async () => {
    metrics.ocFetches++;
    if (scenario === "oc_disable_during_fetch") disableRetention();
    return { data: [
      { info: { role: "user", id: "turn-one" }, parts: [] },
      { info: { role: "assistant", parentID: "turn-one", time: { completed: 1 } },
        get parts() {
          metrics.ocReplyReads++;
          return [{ type: "text", text: "Synthetic opencode reply" }];
        } },
    ] };
  },
} } });
await hooks["chat.message"]({ sessionID: "fixture-session" }, {
  message: { id: "turn-one" },
  get parts() {
    ocPromptReads++;
    return [{ type: "text", text: "Synthetic opencode prompt" }];
  },
});
const output = { system: ["Existing system prompt"] };
await hooks["experimental.chat.system.transform"]({ sessionID: "fixture-session" }, output);
await hooks.event({ event: { type: "session.idle", properties: { sessionID: "fixture-session" } } });
metrics.piContext = injected?.message?.content || "";
metrics.ocSystem = output.system;
metrics.piPromptRead = piPromptReads > 0;
metrics.ocPromptRead = ocPromptReads > 0;
console.log(JSON.stringify(metrics));
""")
            node = shutil.which("node")
            assert node is not None
            result = subprocess.run(
                [
                    node,
                    str(script),
                    pi_module.as_uri(),
                    (home / PLUGIN_PATHS["opencode"]).as_uri(),
                    str(home),
                    scenario,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=dict(
                    os.environ,
                    PATH=str(binary) + os.pathsep + os.environ["PATH"],
                    MEMORY_POLICY_EVENT_LOG=str(log),
                ),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            metrics = json.loads(result.stdout)
            self.assertEqual(
                metrics,
                {
                    "piReplyReads": int(retain),
                    "ocFetches": int(retain),
                    "ocReplyReads": int(
                        retain and scenario != "oc_disable_during_fetch"
                    ),
                    "piContext": "Synthetic context" if recall else "",
                    "ocSystem": ["Existing system prompt"]
                    + (["Synthetic context"] if recall else []),
                    "piPromptRead": recall or retain,
                    "ocPromptRead": recall or retain,
                },
            )
            events = (
                [json.loads(line) for line in log.read_text().splitlines()]
                if log.exists()
                else []
            )
            expected = []
            for runtime in ("pi", "opencode"):
                if recall or retain:
                    expected.append((runtime, "prompt"))
                disabled_during_turn = (
                    runtime == "pi" and scenario == "pi_disable_after_capture"
                ) or (runtime == "opencode" and scenario == "oc_disable_during_fetch")
                if retain and not disabled_during_turn:
                    expected.append((runtime, "retain"))
            self.assertEqual(
                [(event["argv"][2], event["argv"][-1]) for event in events], expected
            )
            self.assertNotIn("PRIVATE TOOL", json.dumps(events))
            self.assertTrue(
                all(event["payload"]["cwd"] == str(home) for event in events)
            )

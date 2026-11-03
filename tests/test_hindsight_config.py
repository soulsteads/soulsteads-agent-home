"""Explicit native MCP wiring, without services, credentials or ingestion."""

import contextlib
import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from soulsteads import core
from soulsteads.cli import main

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class HindsightConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.home = core.create("helper", "opencode", path=Path(self.tmp.name) / "home")

    def invoke(self, *args):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                return main(["config", str(self.home), *args])
            except SystemExit as exc:
                return exc.code

    def test_explicit_native_mcp_configuration_for_all_four_harnesses(self):
        self.assertFalse((self.home / ".mcp.json").exists())
        with patch.dict(
            "os.environ", {"SYNTHETIC_MEMORY_TOKEN": "never-copy-this-value"}
        ):
            self.assertEqual(
                self.invoke(
                    "--hindsight-url",
                    "https://memory.example/mcp/helper/",
                    "--hindsight-token-env",
                    "SYNTHETIC_MEMORY_TOKEN",
                ),
                0,
            )
        oc = json.loads((self.home / "opencode.json").read_text())["mcp"]["hindsight"]
        self.assertEqual(
            oc["headers"]["Authorization"], "Bearer {env:SYNTHETIC_MEMORY_TOKEN}"
        )
        self.assertFalse(oc["oauth"])
        for path in (".mcp.json", ".pi/mcp.json"):
            server = json.loads((self.home / path).read_text())["mcpServers"][
                "hindsight"
            ]
            self.assertEqual(server["type"], "http")
            self.assertEqual(server["url"], "https://memory.example/mcp/helper/")
            self.assertEqual(
                server["headers"]["Authorization"], "Bearer ${SYNTHETIC_MEMORY_TOKEN}"
            )
        codex = tomllib.loads((self.home / ".codex/config.toml").read_text())[
            "mcp_servers"
        ]["hindsight"]
        self.assertEqual(codex["bearer_token_env_var"], "SYNTHETIC_MEMORY_TOKEN")
        for path in self.home.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                self.assertNotIn(b"never-copy-this-value", path.read_bytes(), str(path))
        core.commit(self.home, "Configure native memory tools")

    def test_endpoint_update_and_removal_preserve_unrelated_mcp_servers(self):
        self.assertEqual(
            self.invoke("--hindsight-url", "https://memory.example/mcp/helper/"), 0
        )
        for name, key in (
            ("opencode.json", "mcp"),
            (".mcp.json", "mcpServers"),
            (".pi/mcp.json", "mcpServers"),
        ):
            path = self.home / name
            value = json.loads(path.read_text())
            value[key]["other"] = {"url": "https://other.example/mcp"}
            path.write_text(json.dumps(value))
        self.assertEqual(
            self.invoke("--hindsight-url", "https://new.example/mcp/helper/"), 0
        )
        self.assertEqual(self.invoke("--no-hindsight"), 0)
        self.assertNotIn("hindsight", core.load(self.home))
        for name, key in (
            ("opencode.json", "mcp"),
            (".mcp.json", "mcpServers"),
            (".pi/mcp.json", "mcpServers"),
        ):
            servers = json.loads((self.home / name).read_text())[key]
            self.assertNotIn("hindsight", servers)
            self.assertEqual(servers["other"], {"url": "https://other.example/mcp"})
        self.assertNotIn(
            "hindsight",
            tomllib.loads((self.home / ".codex/config.toml").read_text()).get(
                "mcp_servers", {}
            ),
        )

    def test_conflicting_server_is_not_overwritten_or_partially_published(self):
        path = self.home / ".mcp.json"
        path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "hindsight": {
                            "type": "http",
                            "url": "https://unrelated.example/mcp",
                        }
                    }
                }
            )
        )
        before = (self.home / "opencode.json").read_bytes()
        self.assertEqual(
            self.invoke("--hindsight-url", "https://memory.example/mcp/helper/"), 1
        )
        self.assertEqual((self.home / "opencode.json").read_bytes(), before)
        self.assertNotIn("hindsight", core.load(self.home))

    def test_invalid_url_errors_do_not_echo_private_values(self):
        errors = io.StringIO()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(errors),
        ):
            self.assertEqual(
                main(
                    [
                        "config",
                        str(self.home),
                        "--hindsight-url",
                        "https://memory.example:private-value/mcp/helper/",
                    ]
                ),
                1,
            )
        self.assertNotIn("private-value", errors.getvalue())

    def test_removing_a_customized_owned_server_is_refused(self):
        self.assertEqual(
            self.invoke("--hindsight-url", "https://memory.example/mcp/helper/"), 0
        )
        path = self.home / ".mcp.json"
        value = json.loads(path.read_text())
        value["mcpServers"]["hindsight"]["timeout"] = 99
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        self.assertEqual(self.invoke("--no-hindsight"), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("hindsight", core.load(self.home))

    def test_invalid_or_secret_bearing_options_never_change_home(self):
        before = (self.home / "soulsteads.json").read_bytes()
        for url in (
            "https://user:password@memory.example/mcp/helper/",
            "https://memory.example/mcp/helper/?token=secret",
            "https://memory.example/mcp/",
            "http://memory.example/mcp/helper/",
            "https://memory.example/mcp/helper/#fragment",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(self.invoke("--hindsight-url", url), 0)
        self.assertNotEqual(self.invoke("--hindsight-token-env", "REAL_TOKEN_VALUE"), 0)
        self.assertNotEqual(
            self.invoke(
                "--hindsight-url",
                "https://memory.example/mcp/helper/",
                "--hindsight-token-env",
                "TOKEN;command",
            ),
            0,
        )
        self.assertEqual((self.home / "soulsteads.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

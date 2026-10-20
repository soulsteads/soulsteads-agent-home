import json
import tempfile
import unittest
from pathlib import Path

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()


class RuntimeTests(unittest.TestCase):
    def test_opencode_explicitly_loads_identity(self):
        from soulsteads.runtimes import render

        config = json.loads(render("opencode")["opencode.json"])
        self.assertEqual(config["$schema"], "https://opencode.ai/config.json")
        self.assertEqual(config["instructions"], ["SOUL.md", "USER.md", "MEMORY.md"])
        self.assertNotIn("permission", config)

    def test_unknown_runtime_is_rejected(self):
        from soulsteads.runtimes import render

        with self.assertRaises(ValueError):
            render("unknown")

    def test_all_runtimes_have_native_config_and_shared_skills(self):
        from soulsteads.core import create, load

        expected = {
            "opencode": "opencode.json",
            "pi": ".pi/settings.json",
            "claude": ".claude/settings.json",
            "codex": ".codex/config.toml",
        }
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            for runtime, config in expected.items():
                home = create(runtime, runtime, path=Path(tmp) / runtime)
                self.assertTrue((home / config).is_file(), runtime)
                self.assertEqual(load(home)["runtime"], runtime)
                native = ".claude" if runtime == "claude" else ".agents"
                self.assertEqual((home / native / "skills").resolve(), home / "skills")
                self.assertTrue((home / native / "skills/starter/SKILL.md").is_file())
                if runtime == "claude":
                    self.assertIn("@SOUL.md", (home / "CLAUDE.md").read_text())


if __name__ == "__main__":
    unittest.main()

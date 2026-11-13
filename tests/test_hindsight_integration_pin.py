"""The optional upstream integration is pinned, not a bundled private plugin."""

import json
from pathlib import Path
import unittest


class HindsightIntegrationPinTests(unittest.TestCase):
    def test_optional_package_has_an_exact_public_version_and_registry_integrity(self):
        root = Path(__file__).resolve().parents[1] / "integrations" / "hindsight-opencode"
        manifest_path = root / "package.json"
        self.assertTrue(manifest_path.is_file(), "Optional integration needs a pinned public manifest")
        manifest = json.loads(manifest_path.read_text())
        name = "@vectorize-io/hindsight-coding-agents"
        self.assertIs(manifest["private"], True)
        self.assertEqual(manifest["dependencies"], {name: "0.8.7"})
        self.assertNotIn("scripts", manifest)
        lock = json.loads((root / "package-lock.json").read_text())
        self.assertEqual(lock["packages"][""]["dependencies"], {name: "0.8.7"})
        package = lock["packages"]["node_modules/" + name]
        self.assertEqual(package["version"], "0.8.7")
        self.assertEqual(package["resolved"], "https://registry.npmjs.org/@vectorize-io/hindsight-coding-agents/-/hindsight-coding-agents-0.8.7.tgz")
        self.assertEqual(package["integrity"], "sha512-GuGJdqvcPQpUuu9jWOjJa5OtaI/eAx20DgsiLKKEhfuSCDZXDBWH8Aa7lyj03dAVLMt40K7IciUBtD81QhdTBg==")
        self.assertFalse(package.get("hasInstallScript", False))


if __name__ == "__main__":
    unittest.main()

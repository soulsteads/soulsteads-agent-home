import unittest

from soulsteads.core import HomeError
from soulsteads.settings import _change, _secret_check, catalog
from soulsteads.settings_formats import (
    delete_jsonc,
    parse_jsonc,
    parse_toml,
    update_jsonc,
    update_toml,
)


class SettingsFormatTests(unittest.TestCase):
    def test_jsonc_parse_comments_and_trailing_commas(self):
        text = '{\n  // retained note\n  "model": "old",\n}\n'
        self.assertEqual(parse_jsonc(text), {"model": "old"})

    def test_jsonc_update_retains_unrelated_comments(self):
        text = '{\n  // user note\n  "model": "old",\n  "keep": true\n}\n'
        changed = update_jsonc(text, [(("model",), "new")])
        self.assertIn("// user note", changed)
        self.assertEqual(parse_jsonc(changed)["model"], "new")
        self.assertTrue(parse_jsonc(changed)["keep"])

    def test_toml_round_trip_retains_comments(self):
        text = '# top note\nmodel = "old"\n\n[extra]\n# keep note\nx = 1\n'
        changed = update_toml(text, [(("model",), "new")])
        self.assertIn("# top note", changed)
        self.assertIn("# keep note", changed)
        self.assertEqual(parse_toml(changed)["model"], "new")

    def test_jsonc_insert_and_unset(self):
        original = '{\n  // preserve this\n  "keep": true\n}\n'
        inserted = update_jsonc(original, [(("model",), "x")])
        self.assertIn("// preserve this", inserted)
        self.assertEqual(parse_jsonc(inserted)["model"], "x")
        deleted = delete_jsonc(inserted, ("model",))
        self.assertNotIn('"model"', deleted)
        self.assertTrue(parse_jsonc(deleted)["keep"])

    def test_jsonc_insert_after_trailing_comma(self):
        changed = update_jsonc('{"old": 1,}', [(("new",), 2)])
        self.assertEqual(parse_jsonc(changed), {"old": 1, "new": 2})

    def test_jsonc_rejects_malformed_documents(self):
        with self.assertRaises(HomeError):
            parse_jsonc("{ broken }")
        with self.assertRaises(HomeError):
            parse_jsonc('{"x":1,"x":2}')

    def test_catalog_versions_and_capabilities(self):
        self.assertEqual(catalog("codex")["capabilities"]["reasoning"], True)
        with self.assertRaises(HomeError):
            catalog("codex", version="unknown")
        with self.assertRaises(HomeError):
            _change({"op": "set", "path": "@provider", "value": "x"}, "claude")

    def test_credentials_are_rejected_in_nested_and_argv_values(self):
        for value in (
            {"headers": {"Authorization": "Bearer secret-value"}},
            {"args": ["--token", "secret-value"]},
            {"url": "https://user:password@example.invalid/path"},
            {"provider": {"options": {"apiKey": "literal"}}},
        ):
            with self.assertRaises(HomeError):
                _secret_check(value)
        _secret_check({"provider": {"options": {"apiKey": "${API_KEY}"}}})

    def test_toml_unset_round_trip(self):
        from soulsteads.settings_formats import delete_toml

        original = '# note\nmodel = "old"\nother = true\n'
        changed = delete_toml(original, [("model",)])
        self.assertIn("# note", changed)
        self.assertNotIn("model =", changed)
        self.assertTrue(parse_toml(changed)["other"])

    def test_toml_parser_is_lazy_optional_dependency(self):
        parsed = parse_toml('model = "x"\n')
        self.assertEqual(parsed["model"], "x")


if __name__ == "__main__":
    unittest.main()

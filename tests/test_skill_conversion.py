import unittest

from soulsteads.skill_conversion import convert_skill


class SkillConversionTests(unittest.TestCase):
    def test_converts_hermes_frontmatter_to_portable_required_fields(self):
        raw = b"""---\nname: demo-skill\ndescription: Use this for testing.\nversion: 1.2\nauthor: Example\nplatforms: [linux]\nmetadata:\n  hermes: {tags: [test]}\n---\n# Demo\n\nBody stays.\n"""
        converted = convert_skill(raw, "demo-skill")
        self.assertIn(
            b'name: "demo-skill"\ndescription: "Use this for testing."', converted
        )
        self.assertNotIn(b"version:", converted)
        self.assertNotIn(b"platforms:", converted)
        self.assertNotIn(b"hermes:", converted)
        self.assertTrue(converted.endswith(b"# Demo\n\nBody stays.\n"))

    def test_hermes_metadata_is_removed_and_portable_metadata_is_string_valued(self):
        raw = b"---\nname: demo\ndescription: A skill\nmetadata:\n  hermes: {tags: [test]}\n  category: testing\n---\nBody\n"
        converted = convert_skill(raw, "demo")
        self.assertNotIn(b'"hermes"', converted)
        self.assertIn(b'"category":"testing"', converted)
        with self.assertRaises(ValueError):
            convert_skill(
                b"---\nname: demo\ndescription: A skill\nmetadata: {number: 5}\n---\n",
                "demo",
            )
        with self.assertRaises(ValueError):
            convert_skill(
                b"---\nname: demo\ndescription: A skill\ncompatibility: "
                + b"x" * 501
                + b"\n---\n",
                "demo",
            )

    def test_preserves_safe_standard_optional_fields(self):
        raw = b"""---\nname: demo\ndescription: A skill.\nlicense: MIT\ncompatibility: Works offline\nmetadata: {category: testing}\n---\nBody\n"""
        converted = convert_skill(raw, "demo")
        self.assertIn(b'license: "MIT"', converted)
        self.assertIn(b'compatibility: "Works offline"', converted)
        self.assertIn(b'metadata: {"category":"testing"}', converted)

    def test_rejects_mismatched_or_noncanonical_names_and_long_descriptions(self):
        for name in ("Demo", "a--b", "-bad", "x" * 65):
            raw = f"---\nname: {name}\ndescription: valid\n---\nbody\n".encode()
            with self.subTest(name=name), self.assertRaises(ValueError):
                convert_skill(raw, name)
        raw = b"---\nname: valid\ndescription: " + b"x" * 1025 + b"\n---\nbody"
        with self.assertRaises(ValueError):
            convert_skill(raw, "valid")
        with self.assertRaises(ValueError):
            convert_skill(b"---\nname: other\ndescription: valid\n---\n", "valid")

    def test_rejects_unsafe_optional_metadata_without_leaking_source(self):
        raw = b"---\nname: valid\ndescription: valid\nmetadata: [nope]\n---\nbody secret-token\n"
        with self.assertRaises(ValueError) as caught:
            convert_skill(raw, "valid")
        self.assertNotIn("secret-token", str(caught.exception))

    def test_rejects_invalid_frontmatter_and_nonbytes(self):
        with self.assertRaises(ValueError):
            convert_skill(b"not frontmatter", "valid")
        with self.assertRaises(ValueError):
            convert_skill("text", "valid")


if __name__ == "__main__":
    unittest.main()

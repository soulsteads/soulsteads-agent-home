import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from soulsteads import core, vault
from soulsteads.cli import main


class Item:
    def __init__(self, collection, attributes, value):
        self.collection = collection
        self.attributes = dict(attributes)
        self.value = value

    def get_attributes(self):
        return dict(self.attributes)

    def get_secret(self):
        self.collection.reads += 1
        return self.value

    def set_secret(self, value, *, content_type):
        self.value = value

    def delete(self):
        self.collection.items.remove(self)


class Collection:
    def __init__(self):
        self.items = []
        self.reads = 0

    def search_items(self, attributes):
        return (item for item in self.items if attributes.items() <= item.attributes.items())

    def create_item(self, label, attributes, value, *, replace, content_type):
        self.items.append(Item(self, attributes, value))


class VaultTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(tmp).resolve()
        self.home = core.create("demo", "pi", path=self.root / "home")
        self.other = core.create("demo", "pi", path=self.root / "other")
        self.store = Collection()
        self.value = "synthetic café credential\nwith a second line"

        @contextmanager
        def collection():
            yield self.store

        # The only simulated seam is the OS keyring: no tests contact the
        # invoking user's actual D-Bus session or secret collection.
        self.enterContext(patch.object(vault, "_collection", collection))

    def invoke(self, *args, data=b""):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch(
            "sys.stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
        ):
            try:
                status = main(list(map(str, args)))
            except SystemExit as exc:
                status = exc.code
        self.assertNotIn(self.value, out.getvalue() + err.getvalue())
        return status, out.getvalue(), err.getvalue()

    def test_set_and_list_names_without_touching_the_home(self):
        result = self.invoke("vault", "set", self.home, "example", "--stdin", data=self.value.encode())
        self.assertEqual(result, (0, "", ""))
        status, out, err = self.invoke("vault", "list", self.home)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(json.loads(out), ["example"])
        self.assertEqual(self.store.reads, 0)
        self.assertEqual(subprocess.check_output(["git", "-C", self.home, "status", "--porcelain"]), b"")
        self.assertEqual(self.store.items[0].value, self.value.encode())

    def test_rotate_use_and_remove_only_the_selected_homes_credential(self):
        marker = self.root / "ran"
        runtime = self.root / "pi"
        runtime.write_text(
            "#!/bin/sh\n"
            'printf "%s" "$APPLICATION_TOKEN" > "$VAULT_TEST_MARKER"\n',
            encoding="utf-8",
        )
        runtime.chmod(0o700)
        self.enterContext(patch.dict(os.environ, {
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "VAULT_TEST_MARKER": str(marker),
        }))
        for home, value in ((self.home, b"initial"), (self.other, b"another home"),
                            (self.home, self.value.encode())):
            self.assertEqual(self.invoke("vault", "set", home, "example", "--stdin", data=value)[0], 0)
        self.assertEqual(len(self.store.items), 2)
        binding = ("--credential", "APPLICATION_TOKEN=example")
        self.assertEqual(self.invoke("run", self.home, *binding), (0, "", ""))
        self.assertEqual(marker.read_bytes(), self.value.encode())
        self.assertNotIn("APPLICATION_TOKEN", os.environ)
        self.assertEqual(self.invoke("vault", "delete", self.home, "example"), (0, "", ""))
        marker.unlink()
        status, out, err = self.invoke("run", self.home, *binding)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("not found", err)
        self.assertFalse(marker.exists())
        self.assertEqual(self.invoke("run", self.other, *binding), (0, "", ""))
        self.assertEqual(marker.read_bytes(), b"another home")

    def test_dry_run_does_not_open_the_keyring(self):
        with patch("soulsteads.vault._collection", side_effect=AssertionError("opened keyring")):
            status, out, err = self.invoke("run", self.home, "--dry-run", "--credential", "APPLICATION_TOKEN=missing")
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(json.loads(out)["credential_environment"], ["APPLICATION_TOKEN"])
        self.assertNotIn("missing", out)

    def test_invalid_mappings_and_existing_environment_refuse_before_keyring_read(self):
        with (
            patch.object(vault, "_collection", side_effect=AssertionError("opened keyring")),
            patch.dict(os.environ, {"ALREADY_SET": "ambient"}),
        ):
            for binding in (("BAD-NAME=example",), ("OK=",), ("PATH=example",), ("PWD=example",),
                            ("OK=example.",), ("OK=example.other",), ("OK=example.url.extra",),
                            ("OK=example", "OK=another"), ("ALREADY_SET=example",)):
                with self.subTest(binding=binding):
                    args = [arg for item in binding for arg in ("--credential", item)]
                    status, out, err = self.invoke("run", self.home, *args)
                    self.assertEqual((status, out), (1, ""))
                    self.assertIn("credential", err)

    def test_runtime_selectors_are_rejected_before_keyring_or_sync(self):
        selectors = (
            "CODEX_HOME", "CLAUDE_CONFIG_DIR", "PI_CODING_AGENT_DIR",
            "OPENCODE_CONFIG_DIR", "OPENCODE_DISABLE_PROJECT_CONFIG", "OPENCODE_TUI_CONFIG",
            "SOULSTEAD_MEMORY_WORKSPACE", "SOULSTEADS_HOME", "SOULSTEADS_HARNESS_BIN",
        )
        inherited = {key: value for key, value in os.environ.items() if key not in selectors}
        with (
            patch.dict(os.environ, inherited, clear=True),
            patch.object(vault, "_collection") as keyring,
            patch("soulsteads.native_config.sync") as sync,
        ):
            # Deny keyring access while still exercising the real CLI admission path.
            keyring.side_effect = core.HomeError("unexpected keyring access")
            for name in selectors:
                for mode in ((), ("--dry-run",)):
                    with self.subTest(name=name, mode=mode):
                        status, out, err = self.invoke("run", self.home, *mode, "--credential", f"{name}=example")
                        self.assertEqual((status, out), (1, ""))
                        self.assertIn(f"reserved or existing environment variable: {name}", err)
            keyring.assert_not_called()
            sync.assert_not_called()

    def test_invalid_values_are_rejected_before_storage(self):
        args = ("vault", "set", self.home, "example", "--stdin")
        with patch.object(vault, "_collection", side_effect=AssertionError("opened keyring")):
            for data in (b"", b"has\0nul", b"\xffinvalid", b"x" * (16 * 1024 + 1)):
                status, out, err = self.invoke(*args, data=data)
                self.assertEqual((status, out), (1, ""))
                self.assertIn("credential", err)
                self.assertNotIn("\\xffinvalid", err)

    def test_duplicate_records_are_not_read_replaced_or_removed(self):
        args = (self.home, "example")
        self.assertEqual(self.invoke("vault", "set", *args, "--stdin", data=b"first")[0], 0)
        original = self.store.items[0]
        self.store.items.append(Item(self.store, original.attributes, b"second"))
        for call in (("vault", "list", self.home), ("vault", "delete", *args),
                     ("vault", "set", *args, "--stdin"),
                     ("run", self.home, "--credential", "APPLICATION_TOKEN=example")):
            with self.subTest(call=call):
                status, out, err = self.invoke(*call, data=b"new value")
                self.assertEqual((status, out), (1, ""))
                self.assertIn("conflicting credential records", err)
        self.assertEqual(self.store.reads, 0)
        self.assertEqual([item.value for item in self.store.items], [b"first", b"second"])

    def test_provider_metadata_does_not_hide_a_credential(self):
        args = (self.home, "example")
        self.assertEqual(self.invoke("vault", "set", *args, "--stdin", data=b"first")[0], 0)
        self.store.items[0].attributes["xdg:schema"] = "org.freedesktop.Secret.Generic"
        self.assertEqual(self.invoke("vault", "list", self.home), (0, '["example"]\n', ""))
        self.assertEqual(self.invoke("vault", "set", *args, "--stdin", data=b"second"), (0, "", ""))
        self.assertEqual(self.invoke("vault", "delete", *args), (0, "", ""))

    def test_missing_second_binding_neither_syncs_nor_launches(self):
        present, missing = "example", "missing"
        self.assertEqual(self.invoke("vault", "set", self.home, present, "--stdin", data=b"present")[0], 0)
        with patch("soulsteads.native_config.sync", side_effect=AssertionError("synced Home")):
            status, out, err = self.invoke(
                "run", self.home, "--credential", f"VAULT_TEST_PRESENT={present}",
                "--credential", f"VAULT_TEST_MISSING={missing}",
            )
        self.assertEqual((status, out), (1, ""))
        self.assertIn("not found", err)

    def test_unbound_run_does_not_access_credentials(self):
        with patch.object(vault, "_collection", side_effect=AssertionError("opened keyring")):
            status, out, err = self.invoke("run", self.home, "--dry-run")
        self.assertEqual((status, err), (0, ""))
        self.assertNotIn("credential_environment", json.loads(out))

    def test_login_round_trips_requested_fields_from_one_keyring_item(self):
        login = {
            "username": "synthetic account",
            "password": self.value,
            "url": "https://service.example.test/login",
        }
        runtime = self.root / "pi"
        runtime.write_text(
            '#!/bin/sh\nprintf "%s\\000" "$LOGIN_USER" "$LOGIN_PASS" "$LOGIN_SITE" > "$LOGIN_MARKER"\n',
            encoding="utf-8",
        )
        runtime.chmod(0o700)
        marker = self.root / "login-marker"
        self.enterContext(patch.dict(os.environ, {
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "LOGIN_MARKER": str(marker),
        }))
        args = ("vault", "set", self.home, "service", "--login", "--stdin")
        self.assertEqual(self.invoke(*args, data=json.dumps(login).encode()), (0, "", ""))
        self.assertEqual(self.invoke("vault", "list", self.home), (0, '["service"]\n', ""))
        self.assertEqual(len(self.store.items), 1)
        for value in login.values():
            self.assertNotIn(value, json.dumps(self.store.items[0].attributes))
        self.assertEqual(self.store.reads, 0)

        bindings = []
        for name, field in zip(("LOGIN_USER", "LOGIN_PASS", "LOGIN_SITE"), login):
            bindings.extend(("--credential", f"{name}=service.{field}"))
        self.assertEqual(self.invoke("run", self.home, *bindings), (0, "", ""))
        self.assertEqual(marker.read_bytes().split(b"\0"), [*(v.encode() for v in login.values()), b""])
        self.assertEqual(self.store.reads, 1)

        # Replacing a login without the optional URL removes the old URL.
        login.pop("url")
        self.assertEqual(self.invoke(*args, data=json.dumps(login).encode()), (0, "", ""))
        marker.unlink()
        status, out, err = self.invoke("run", self.home, *bindings)
        self.assertEqual((status, out), (1, ""))
        self.assertIn("url", err)
        self.assertFalse(marker.exists())
        self.assertEqual(self.invoke("run", self.home, *bindings[:-2]), (0, "", ""))
        self.assertEqual(marker.read_bytes().split(b"\0"), [*(v.encode() for v in login.values()), b"", b""])

    def test_interactive_login_hides_input_and_can_omit_url(self):
        with patch("getpass.getpass", side_effect=("synthetic account", self.value, "")) as prompt:
            self.assertEqual(self.invoke("vault", "set", self.home, "service", "--login"), (0, "", ""))
        self.assertEqual([call.args[0].split()[0] for call in prompt.call_args_list],
                         ["Username:", "Password:", "URL"])
        self.assertEqual(
            vault._decode_entry(self.store.items[0].value),
            {"username": "synthetic account", "password": self.value},
        )

    def test_invalid_login_input_does_not_replace_existing_entry(self):
        args = ("vault", "set", self.home, "service", "--stdin")
        self.assertEqual(self.invoke(*args, data=b"keep this value"), (0, "", ""))
        valid = {"username": "synthetic account", "password": self.value}
        variants = [
            b"[", b"[]", b"\xff", b"[" * 1200 + b"]" * 1200,
            b'{"username":"first","username":"second","password":"synthetic"}',
            *(json.dumps(fields).encode() for fields in (
                {"username": valid["username"]}, {"password": self.value},
                {**valid, "username": ""}, {**valid, "password": 42},
                {**valid, "url": ""}, {**valid, "url": None}, {**valid, "extra": "field"},
                {**valid, "password": "prefix\0suffix"}, {**valid, "password": "\ud800"},
                {**valid, "password": "x" * (16 * 1024 + 1)},
            )),
        ]
        with patch.object(vault, "_collection", side_effect=AssertionError("opened keyring")):
            for index, value in enumerate(variants):
                with self.subTest(index=index):
                    status, out, err = self.invoke(*args, "--login", data=value)
                    self.assertEqual((status, out), (1, ""))
                    self.assertIn("credential", err)
        self.assertEqual(self.store.items[0].value, b"keep this value")

    def test_launch_refuses_wrong_entry_shape_or_invalid_saved_payload(self):
        args = ("vault", "set", self.home, "service", "--stdin")
        login_json = json.dumps({"username": "synthetic account", "password": self.value}).encode()
        login = self.invoke(*args, "--login", data=login_json)
        self.assertEqual(login, (0, "", ""))
        item = self.store.items[0]
        cases = (
            (item.value, "service", "requires an explicit field"),
            (login_json, "service.password", "single value and has no fields"),
            (b"\0unknown-format", "service.password", "invalid login credential record"),
            (item.value.replace(b'"username"', b'"extra"'), "service.password", "optional url"),
        )
        with patch("soulsteads.native_config.sync", side_effect=AssertionError("synced Home")):
            for value, reference, diagnostic in cases:
                with self.subTest(reference=reference, diagnostic=diagnostic):
                    item.value = value
                    status, out, err = self.invoke("run", self.home, "--credential", f"APP_LOGIN={reference}")
                    self.assertEqual((status, out), (1, ""))
                    self.assertIn(diagnostic, err)


if __name__ == "__main__":
    unittest.main()

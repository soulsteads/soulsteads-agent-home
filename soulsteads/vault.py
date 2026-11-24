"""Agent-scoped credentials backed by the Linux Secret Service."""

import os
import re
import sys
from contextlib import closing, contextmanager
from hashlib import sha256

from .core import HomeError

MAX_VALUE_BYTES = 16 * 1024
_ALIAS = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_APPLICATION = "org.soulsteads.agent-home.vault.v1"
_CONTROL_ENV = {"PATH", "PWD", "HOME", "SHELL", "ENV", "BASH_ENV", "IFS", "CDPATH", "NODE_OPTIONS"}
_CONTROL_PREFIXES = ("DBUS_", "DYLD_", "LD_", "PYTHON", "XDG_", "OPENCODE_CONFIG")


def validate_alias(alias):
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise HomeError("credential alias must be a lowercase slug (1–64 characters)")
    return alias


def _decode_value(value):
    if not value or len(value) > MAX_VALUE_BYTES or b"\0" in value:
        raise HomeError("credential must be nonempty UTF-8 text up to 16 KiB without NUL bytes")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        raise HomeError("credential must be valid UTF-8 text") from None


def read_input(from_stdin):
    """Read a bounded pipe/file, or prompt with echo disabled (never fall back)."""
    if from_stdin:
        if sys.stdin.isatty():
            raise HomeError("--stdin requires redirected input; omit it for a hidden prompt")
        return sys.stdin.buffer.read(MAX_VALUE_BYTES + 1)

    import getpass
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass("Credential: ").encode("utf-8")
    except (EOFError, OSError, UnicodeError, getpass.GetPassWarning):
        raise HomeError("a hidden terminal prompt is unavailable; use redirected --stdin") from None


@contextmanager
def _collection():
    if sys.platform != "linux":
        raise HomeError("the credential vault requires Linux Secret Service")
    try:
        import secretstorage
        from jeepney.wrappers import DBusErrorResponse
    except ImportError:
        raise HomeError("credential vault support requires installing soulsteads[vault]") from None
    try:
        with closing(secretstorage.dbus_init()) as connection:
            collection = secretstorage.get_collection_by_alias(connection, "default")
            if collection.collection_path == "/org/freedesktop/secrets/collection/session":
                raise HomeError("the credential vault requires a persistent default keyring")
            if collection.is_locked():
                raise HomeError("unlock the default keyring before using the credential vault")
            yield collection
    except secretstorage.LockedException:
        raise HomeError("unlock the default keyring before using the credential vault") from None
    except (secretstorage.SecretStorageException, DBusErrorResponse, OSError, EOFError, ValueError):
        # The backend may include request data in its diagnostics. Never pass
        # those diagnostics (or the original exception) to the CLI.
        raise HomeError("credential vault unavailable; check the Linux Secret Service and default keyring") from None


def _scope(home):
    path = b"/" + os.fsencode(os.path.abspath(home)).lstrip(b"/")
    return {"application": _APPLICATION, "home": sha256(path).hexdigest()}


def _attributes(item):
    attributes = item.get_attributes()
    # GNOME Keyring can add this metadata after saving or reloading an item.
    if attributes.get("xdg:schema") == "org.freedesktop.Secret.Generic":
        del attributes["xdg:schema"]
    return attributes


def _item(collection, scope, alias):
    attributes = {**scope, "alias": alias}
    result = None
    for item in collection.search_items(attributes):
        if result is not None or _attributes(item) != attributes:
            raise HomeError("conflicting credential records in the default keyring")
        result = item
    return result


def set_value(home, alias, value):
    alias = validate_alias(alias)
    _decode_value(value)
    scope = _scope(home)
    with _collection() as collection:
        item = _item(collection, scope, alias)
        if item is None:
            collection.create_item(
                f"Soulsteads Agent Home: {alias}", {**scope, "alias": alias}, value, replace=True
            )
        else:
            item.set_secret(value)


def list_aliases(home):
    scope = _scope(home)
    names = set()
    with _collection() as collection:
        for item in collection.search_items(scope):
            attributes = _attributes(item)
            alias = validate_alias(attributes.get("alias"))
            if attributes != {**scope, "alias": alias} or alias in names:
                raise HomeError("conflicting credential records in the default keyring")
            names.add(alias)
    return sorted(names)


def delete_value(home, alias):
    alias = validate_alias(alias)
    with _collection() as collection:
        item = _item(collection, _scope(home), alias)
        if item is None:
            raise HomeError(f"credential alias not found: {alias}")
        item.delete()


def parse_bindings(options, inherited):
    if len(options) > 16:
        raise HomeError("at most 16 credential mappings are allowed per launch")
    bindings = {}
    for option in options:
        name, separator, alias = option.partition("=")
        if not separator or not _ENV_NAME.fullmatch(name):
            raise HomeError("credential mapping must have the form ENV=alias")
        validate_alias(alias)
        if name in bindings:
            raise HomeError(f"duplicate credential environment variable: {name}")
        if name in inherited or name in _CONTROL_ENV or name.startswith(_CONTROL_PREFIXES):
            raise HomeError(f"credential mapping cannot replace a reserved or existing environment variable: {name}")
        bindings[name] = alias
    return bindings


def resolve_environment(home, bindings):
    scope = _scope(home)
    values = {}
    with _collection() as collection:
        for alias in dict.fromkeys(bindings.values()):
            item = _item(collection, scope, alias)
            if item is None:
                raise HomeError(f"credential alias not found: {alias}")
            values[alias] = _decode_value(item.get_secret())
    return {name: values[alias] for name, alias in bindings.items()}

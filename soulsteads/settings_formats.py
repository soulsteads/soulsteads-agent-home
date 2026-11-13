"""Strict parsers and comment-preserving editors for native settings files."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from .core import HomeError


def _jsonc_clean(text: str, *, trailing=True) -> str:
    """Remove JSONC comments and trailing commas without touching string data."""
    out = list(text)
    i = 0
    quote = False
    escape = False
    while i < len(text):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                quote = False
            i += 1
            continue
        if ch == '"':
            quote = True
            i += 1
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            j = text.find("\n", i)
            j = len(text) if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j < 0:
                raise HomeError("unterminated JSONC comment")
            for k in range(i, j + 2):
                if out[k] not in "\r\n":
                    out[k] = " "
            i = j + 2
        else:
            i += 1
    if quote:
        raise HomeError("unterminated JSON string")
    clean = "".join(out)
    if not trailing:
        return clean
    # Remove commas before closing brackets outside strings (comments are spaces).
    chars = list(clean)
    quote = escape = False
    for i, ch in enumerate(clean):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                quote = False
        elif ch == '"':
            quote = True
        elif ch == ",":
            j = i + 1
            while j < len(clean) and clean[j].isspace():
                j += 1
            if j < len(clean) and clean[j] in "]}":
                chars[i] = " "
    return "".join(chars)


def parse_jsonc(text: str) -> Any:
    try:

        def reject_constant(value):
            raise ValueError(f"invalid JSON constant {value}")

        def reject_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON object key")
                result[key] = value
            return result

        def finite_float(value):
            parsed = float(value)
            if not math.isfinite(parsed):
                raise ValueError("non-finite JSON number")
            return parsed

        return json.loads(
            _jsonc_clean(text),
            parse_constant=reject_constant,
            parse_float=finite_float,
            object_pairs_hook=reject_duplicates,
        )
    except HomeError:
        raise
    except (ValueError, TypeError, RecursionError) as exc:
        raise HomeError("invalid JSON/JSONC settings") from exc


def parse_toml(text: str) -> dict[str, Any]:
    try:
        import tomlkit
    except ImportError as exc:
        raise HomeError(
            "TOML settings editing requires the optional 'settings' extra"
        ) from exc
    try:
        return tomlkit.parse(text)
    except Exception as exc:
        raise HomeError("invalid TOML settings") from exc


def _tokens(text: str) -> list[tuple[str, int, int]]:
    """JSONC lexical tokens with source spans."""
    clean = _jsonc_clean(text)
    token_re = re.compile(
        r'\s+|"(?:\\.|[^"\\])*"|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]'
    )
    result = []
    pos = 0
    while pos < len(clean):
        m = token_re.match(clean, pos)
        if not m:
            raise HomeError("invalid JSON/JSONC settings")
        if not m.group().isspace():
            result.append((m.group(), m.start(), m.end()))
        pos = m.end()
    return result


def _spans(text: str) -> tuple[Any, dict[str, Any] | None]:
    parse_jsonc(text)
    tokens = _tokens(text)
    idx = 0

    def parse_value():
        nonlocal idx
        if idx >= len(tokens):
            raise HomeError("invalid JSON/JSONC settings")
        tok, start, end = tokens[idx]
        if tok == "{":
            idx += 1
            value = {}
            members = {}
            if idx < len(tokens) and tokens[idx][0] == "}":
                idx += 1
                return value, (start, tokens[idx - 1][2]), members
            while True:
                if idx >= len(tokens) or not tokens[idx][0].startswith('"'):
                    raise HomeError("invalid JSON/JSONC object key")
                kt, ks, _ke = tokens[idx]
                key = json.loads(kt)
                idx += 1
                if idx >= len(tokens) or tokens[idx][0] != ":":
                    raise HomeError("invalid JSON/JSONC object")
                idx += 1
                child, span, childmembers = parse_value()
                value[key] = child
                members[key] = (ks, span[1], span, childmembers)
                if idx >= len(tokens):
                    raise HomeError("invalid JSON/JSONC object")
                sep = tokens[idx][0]
                idx += 1
                if sep == "}":
                    break
                if sep != ",":
                    raise HomeError("invalid JSON/JSONC object")
            return value, (start, tokens[idx - 1][2]), members
        if tok == "[":
            idx += 1
            arr = []
            if idx < len(tokens) and tokens[idx][0] == "]":
                idx += 1
                return arr, (start, tokens[idx - 1][2]), None
            while True:
                child, _, _ = parse_value()
                arr.append(child)
                if idx >= len(tokens):
                    raise HomeError("invalid JSON/JSONC array")
                sep = tokens[idx][0]
                idx += 1
                if sep == "]":
                    break
                if sep != ",":
                    raise HomeError("invalid JSON/JSONC array")
            return arr, (start, tokens[idx - 1][2]), None
        idx += 1
        try:
            val = json.loads(tok)
        except ValueError as exc:
            raise HomeError("invalid JSON/JSONC value") from exc
        return val, (start, end), None

    value, _span, members = parse_value()
    if idx != len(tokens):
        raise HomeError("invalid JSON/JSONC trailing data")
    return value, members


def update_jsonc(text: str, edits: list[tuple[tuple[str, ...], Any]]) -> str:
    """Set JSONC values while retaining comments and unrelated formatting."""
    result = text
    for path, value in edits:
        if not path or not isinstance(path, (tuple, list)):
            raise HomeError("settings path must be a non-empty pointer")
        parsed, members = _spans(result)
        node = parsed
        table = members
        meta = None
        for path_index, key in enumerate(path):
            if not isinstance(node, dict) or table is None:
                raise HomeError("JSONC pointer parent is not an object")
            if key not in node:
                if key != path[-1]:
                    raise HomeError("JSONC set requires existing parent objects")
                # Insert immediately before this object's closing brace.
                tokens = _tokens(result)
                depth = 0
                # Match the object represented by this member table from the
                # opening brace to its closing brace, respecting nested objects.
                if table is members:
                    begin = next(i for i, t in enumerate(tokens) if t[0] == "{")
                else:
                    begin = None
                    # Locate the parent's object by the span of the preceding path.
                    prefix = path[:path_index]
                    parent = parsed
                    parentmeta = None
                    parent_members = members
                    for p in prefix:
                        if parent_members is None:
                            raise HomeError("JSONC pointer parent is not an object")
                        parentmeta = parent_members[p]
                        parent_members = parentmeta[3]
                        parent = parent[p]
                    begin = next(
                        i
                        for i, t in enumerate(tokens)
                        if t[1] == (parentmeta[2][0] if parentmeta else 0)
                    )
                depth = 0
                close = None
                for i in range(begin, len(tokens)):
                    if tokens[i][0] == "{":
                        depth += 1
                    elif tokens[i][0] == "}":
                        depth -= 1
                        if depth == 0:
                            close = tokens[i][1]
                            break
                if close is None:
                    raise HomeError("invalid JSONC object")
                line_start = result.rfind("\n", 0, close) + 1
                base_indent = re.match(r"[ \\t]*", result[line_start:close]).group(0)
                child_indent = base_indent + "  "
                has_items = bool(table)
                if has_items:
                    last_end = max(meta[2][1] for meta in table.values())
                    between = _jsonc_clean(result)[last_end:close]
                    raw_between = result[last_end:close]
                    raw_lead = raw_between.lstrip()
                    had_trailing = (
                        raw_lead.startswith(",")
                        and not _jsonc_clean(raw_lead[1:]).strip()
                    )
                    if not had_trailing and not re.match(r"\s*,\s*$", between):
                        result = result[:last_end] + "," + result[last_end:]
                        close += 1
                insertion = (
                    "\n"
                    + child_indent
                    + json.dumps(key)
                    + ": "
                    + json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                    + base_indent
                )
                result = result[:close] + insertion + result[close:]
                break
            meta = table[key]
            node = node[key]
            table = meta[3]
        else:
            start, end = meta[2]
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            result = result[:start] + encoded + result[end:]
        parse_jsonc(result)
    return result


def delete_jsonc(text: str, path: tuple[str, ...]) -> str:
    """Remove a JSONC member while preserving all non-member text."""
    parsed, members = _spans(text)
    node = parsed
    table = members
    for key in path[:-1]:
        if not isinstance(node, dict) or key not in node or table is None:
            return text
        meta = table[key]
        node = node[key]
        table = meta[3]
    if not isinstance(node, dict) or path[-1] not in node or table is None:
        return text
    key_start, _member_end, value_span, _ = table[path[-1]]
    tokens = _tokens(text)
    after = next((t for t in tokens if t[1] >= value_span[1]), None)
    between_end = after[1] if after else len(text)
    visible = _jsonc_clean(text, trailing=False)
    following_comma = visible.find(",", value_span[1], between_end)
    if after and after[0] == ",":
        start, end = key_start, after[2]
    elif following_comma >= 0:
        start, end = key_start, following_comma + 1
    else:
        siblings = sorted(table.values(), key=lambda member: member[0])
        previous = [member for member in siblings if member[0] < key_start]
        if previous:
            comma = visible.find(",", previous[-1][2][1], key_start)
            if comma < 0:
                raise HomeError("invalid JSONC sibling separator")
            start, end = comma, value_span[1]
        else:
            start, end = key_start, value_span[1]
    result = text[:start] + text[end:]
    parse_jsonc(result)
    return result


def delete_toml(text: str, paths: list[tuple[str, ...]]) -> str:
    doc = parse_toml(text)
    for path in paths:
        if not path:
            raise HomeError("settings path must be a non-empty pointer")
        node = doc
        for key in path[:-1]:
            if key not in node or not hasattr(node[key], "pop"):
                node = None
                break
            node = node[key]
        if node is not None:
            node.pop(path[-1], None)
    import tomlkit

    return tomlkit.dumps(doc)


def update_toml(text: str, edits: list[tuple[tuple[str, ...], Any]]) -> str:
    doc = parse_toml(text)
    for path, value in edits:
        if not path:
            raise HomeError("settings path must be a non-empty pointer")
        node = doc
        for key in path[:-1]:
            if key not in node or not hasattr(node[key], "__setitem__"):
                raise HomeError("TOML set requires existing parent tables")
            node = node[key]
        node[path[-1]] = value
    import tomlkit

    return tomlkit.dumps(doc)

"""A small, forgiving parser for Godot's text resource formats.

Covers ``.tscn``, ``.tres`` and ``project.godot`` at the *section* level:
``[header key=value ...]`` lines followed by ``key = value`` properties.
Values are kept as raw strings except for the few shapes the map needs
(quoted strings, ``ExtResource("id")`` / ``SubResource("id")`` references,
string arrays). It never rejects a file it does not fully understand — a
property it cannot read is kept verbatim, which is why it copes with
``bus/1/name = &"Music"`` and typed arrays that trip stricter parsers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADER = re.compile(r"^\[(\w+)(.*)\]\s*$")
# key=value pairs inside a header. Values: "quoted", [array], or a bare
# token optionally followed by a call like ExtResource("1_abc").
_ATTR = re.compile(
    r'(\w+)=("(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^\s\]"(]+(?:\([^)]*\))?)'
)
_PROP = re.compile(r"^([\w/.:@]+)\s*=\s*(.*)$")
_REF = re.compile(r'^(Ext|Sub)Resource\(\s*&?"?([^")\s]+)"?\s*\)$')
_STR = re.compile(r'^&?"((?:[^"\\]|\\.)*)"$')
_STR_ITEM = re.compile(r'&?"((?:[^"\\]|\\.)*)"')
_STR_ARRAY = re.compile(r"^(?:PackedStringArray|Array(?:\[[\w.]+\])?)\((.*)\)$", re.S)


@dataclass
class Ref:
    """An ExtResource/SubResource reference by id."""

    kind: str  # "Ext" or "Sub"
    id: str


@dataclass
class Section:
    name: str
    attrs: dict[str, object] = field(default_factory=dict)
    props: dict[str, str] = field(default_factory=dict)

    def attr_str(self, key: str, default: str | None = None) -> str | None:
        v = self.attrs.get(key, default)
        return v if isinstance(v, str) or v is None else str(v)

    def attr_ref(self, key: str) -> Ref | None:
        v = self.attrs.get(key)
        return v if isinstance(v, Ref) else None

    def prop_ref(self, key: str) -> Ref | None:
        raw = self.props.get(key)
        return parse_value(raw) if raw is not None else None  # type: ignore[return-value]

    def prop_str(self, key: str) -> str | None:
        raw = self.props.get(key)
        if raw is None:
            return None
        v = parse_value(raw)
        return v if isinstance(v, str) else None


def parse_value(raw: str) -> object:
    """Decode the value shapes the map cares about; anything else is returned raw."""
    raw = raw.strip()
    m = _REF.match(raw)
    if m:
        return Ref(m.group(1), m.group(2))
    m = _STR.match(raw)
    if m:
        return m.group(1).replace('\\"', '"')
    if raw.startswith("[") and raw.endswith("]"):
        return _STR_ITEM.findall(raw)
    m = _STR_ARRAY.match(raw)
    if m:
        return _STR_ITEM.findall(m.group(1))
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_attrs(text: str) -> dict[str, object]:
    return {k: parse_value(v) for k, v in _ATTR.findall(text)}


def parse(text: str) -> list[Section]:
    """Split a text resource into sections. Property values are raw strings;
    a value continued over several lines (arrays, dictionaries) is joined."""
    sections: list[Section] = []
    current: Section | None = None
    last_key: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        h = _HEADER.match(stripped)
        if h and not stripped.startswith("[\"") and _looks_like_header(stripped):
            current = Section(h.group(1), _parse_attrs(h.group(2)))
            sections.append(current)
            last_key = None
            continue
        if current is None:
            continue
        p = _PROP.match(line)
        if p:
            last_key = p.group(1)
            current.props[last_key] = p.group(2).strip()
        elif last_key is not None:
            current.props[last_key] += " " + stripped
    return sections


def _looks_like_header(line: str) -> bool:
    # A property whose value is an array can start with "[" only when it is
    # a continuation line; a real header begins with "[word".
    return bool(re.match(r"^\[\w+(\s|\])", line))


def parse_file(path: str) -> list[Section]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse(fh.read())

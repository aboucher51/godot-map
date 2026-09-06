"""Regex-level facts about a GDScript file.

Not a parser: it reads the handful of declarations that describe how a
script relates to the rest of the project — what it extends, what it is
called, which resources it loads, which signals it declares, emits and
connects to. Anything inside a string literal or comment can fool it; the
map is for orientation, not for proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CLASS_NAME = re.compile(r"^class_name\s+([A-Za-z_]\w*)", re.M)
_EXTENDS = re.compile(r'^extends\s+(?:"([^"]+)"|([A-Za-z_][\w.]*))', re.M)
_TOOL = re.compile(r"^@tool\b", re.M)
_LOAD = re.compile(r'\b(?:preload|load)\(\s*"(res://[^"]+)"\s*\)')
_RES_REF = re.compile(r'"(res://[^"\s]+)"')
_SIGNAL = re.compile(r"^signal\s+([A-Za-z_]\w*)", re.M)
_FUNC = re.compile(r"^(?:static\s+)?func\s+([A-Za-z_]\w*)", re.M)
_EMIT = re.compile(r"\b([A-Za-z_][\w.]*)\.emit\(")
_EMIT_SIGNAL = re.compile(r'\bemit_signal\(\s*"([A-Za-z_]\w*)"')
_CONNECT = re.compile(r"\b([A-Za-z_][\w.]*)\.connect\(")
_GET_NODE = re.compile(r'(?:\$|get_node\(\s*")([\w/%]+)')
_COMMENT = re.compile(r"#.*$", re.M)


@dataclass
class ScriptInfo:
    path: str  # res:// path
    class_name: str | None = None
    extends: str | None = None
    is_tool: bool = False
    loads: list[str] = field(default_factory=list)  # preload/load res:// paths
    refs: list[str] = field(default_factory=list)  # every other res:// literal
    signals: list[str] = field(default_factory=list)
    funcs: list[str] = field(default_factory=list)
    emits: list[str] = field(default_factory=list)  # "EventBus.saved" or "saved"
    connects: list[str] = field(default_factory=list)  # "EventBus.saved" or "button.pressed"
    node_paths: list[str] = field(default_factory=list)  # $Foo/Bar and get_node("..")
    lines: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "class_name": self.class_name,
            "extends": self.extends,
            "tool": self.is_tool,
            "loads": self.loads,
            "refs": self.refs,
            "signals": self.signals,
            "funcs": self.funcs,
            "emits": self.emits,
            "connects": self.connects,
            "node_paths": self.node_paths,
            "lines": self.lines,
        }


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def scan_source(res_path: str, source: str) -> ScriptInfo:
    info = ScriptInfo(path=res_path, lines=source.count("\n") + 1)
    code = _COMMENT.sub("", source)
    m = _CLASS_NAME.search(code)
    info.class_name = m.group(1) if m else None
    m = _EXTENDS.search(code)
    info.extends = (m.group(1) or m.group(2)) if m else None
    info.is_tool = bool(_TOOL.search(code))
    info.loads = _uniq(_LOAD.findall(code))
    info.refs = _uniq(p for p in _RES_REF.findall(code) if p not in info.loads)
    info.signals = _uniq(_SIGNAL.findall(code))
    info.funcs = _uniq(_FUNC.findall(code))
    info.emits = _uniq(_EMIT.findall(code) + _EMIT_SIGNAL.findall(code))
    info.connects = _uniq(_CONNECT.findall(code))
    info.node_paths = _uniq(_GET_NODE.findall(code))
    return info


def scan_file(res_path: str, fs_path: str) -> ScriptInfo:
    with open(fs_path, encoding="utf-8", errors="replace") as fh:
        return scan_source(res_path, fh.read())

"""Regex-level facts about a C# script, in the same shape as ``gdscript``.

Reads what the map needs to place a ``.cs`` file in the project: the
class and its base, ``[GlobalClass]`` (visible to GDScript and the editor
by name), ``[Tool]``, ``[Signal]`` delegates, ``GD.Load``/
``ResourceLoader.Load`` paths, ``EmitSignal``, ``+=`` and ``Connect``
listeners, and ``GetNode("…")`` paths. A regex, not Roslyn.
"""

from __future__ import annotations

import re

from .gdscript import ScriptInfo, _uniq

_STRING = re.compile(r'@"(?:[^"]|"")*"|\$?"(?:[^"\\]|\\.)*"')
_COMMENT_OR_STRING = re.compile(f"({_STRING.pattern})|//[^\\n]*|/\\*.*?\\*/", re.S)
_NAMED = re.compile(r'\.Name\s*=\s*"([^"/]+)"')
_GROUP_JOIN = re.compile(r'\bAddToGroup\(\s*"([^"]+)"')
_GROUP_QUERY = re.compile(r'\b(?:GetNodesInGroup|CallGroup|CallGroupFlags|IsInGroup|GetFirstNodeInGroup|HasGroup)\(\s*(?:\d+\s*,\s*)?"([^"]+)"')
_CLASS = re.compile(r"\b(?:partial\s+)?class\s+([A-Za-z_]\w*)\s*(?::\s*([\w.]+))?")
_GLOBAL = re.compile(r"\[\s*GlobalClass\s*\]")
_TOOL = re.compile(r"\[\s*Tool\s*\]")
_LOAD = re.compile(r'\bLoad(?:<[^>]*>)?\(\s*"(res://[^"]+)"')
_RES_REF = re.compile(r'"(res://[^"\s]+)"')
_SIGNAL = re.compile(r"\[\s*Signal\s*\][^;]*?\bdelegate\s+\w+\s+([A-Za-z_]\w*?)(?:EventHandler)?\s*\(", re.S)
_FUNC = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|override|virtual|async|sealed|new|partial|unsafe|extern)\s+)+"
    r"[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\(",
    re.M,
)
_EMIT = re.compile(r'(?:\b([A-Za-z_]\w*)\.)?\bEmitSignal\(\s*(?:SignalName\.(\w+)|"(\w+)")')
_CONNECT_CALL = re.compile(r'(?:\b([A-Za-z_]\w*)\.)?\bConnect\(\s*(?:SignalName\.(\w+)|"(\w+)")')
# Foo.Bar += handler, Bar += handler: a PascalCase last segment, and a
# handler (not a number) on the right, so `count += 1` stays out.
_CONNECT_ADD = re.compile(r"(?:([\)\]])\.)?\b((?:[A-Za-z_]\w*\.)*[A-Z]\w*)\s*\+=\s*[A-Za-z_(]")
# GetNode on this node only; `other.GetNode("X")` is relative to `other`.
_NODE_PATH = re.compile(r'(?:(?<![.\w])|\bthis\.)GetNode(?:<[^>]*>)?\(\s*"([^"]+)"')
_IDENT = re.compile(r"\b[A-Za-z_]\w*\b")


def scan_source(res_path: str, source: str) -> ScriptInfo:
    info = ScriptInfo(path=res_path, lang="csharp", lines=source.count("\n") + 1)
    code = _COMMENT_OR_STRING.sub(lambda m: m.group(1) or "", source)
    m = _CLASS.search(code)
    if m:
        info.class_name = m.group(1)
        info.extends = m.group(2)
    info.is_global = bool(_GLOBAL.search(code))
    info.is_tool = bool(_TOOL.search(code))
    info.loads = _uniq(_LOAD.findall(code))
    info.refs = _uniq(p for p in _RES_REF.findall(code) if p not in info.loads)
    info.signals = _uniq(_SIGNAL.findall(code))
    info.funcs = _uniq(_FUNC.findall(code))
    info.emits = _uniq(_qualified(m) for m in _EMIT.findall(code))
    info.connects = _uniq(
        [_qualified(m) for m in _CONNECT_CALL.findall(code)]
        + [f"?.{name}" if closer else name for closer, name in _CONNECT_ADD.findall(code)]
    )
    info.node_paths = _uniq(_NODE_PATH.findall(code))
    info.groups_joined = _uniq(_GROUP_JOIN.findall(code))
    info.groups_queried = _uniq(_GROUP_QUERY.findall(code))
    info.idents = set(_IDENT.findall(_STRING.sub('""', code)))
    info.named_nodes = set(_NAMED.findall(code))
    return info


def _qualified(m: tuple[str, str, str]) -> str:
    obj, a, b = m
    name = a or b
    return f"{obj}.{name}" if obj else name


def scan_file(res_path: str, fs_path: str) -> ScriptInfo:
    with open(fs_path, encoding="utf-8", errors="replace") as fh:
        return scan_source(res_path, fh.read())

"""Walk a Godot project and build the map model."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import csharp, gdscript, tscn

SKIP_DIRS = {
    ".godot", ".git", ".import", "addons", "node_modules", ".venv", "builds", "shots",
    "bin", "obj", ".mono",
}
DATA_EXTS = (".json", ".csv", ".gdshader")
_NODEPATH_PROP = re.compile(r'^NodePath\("([^"]*)"\)$')
_TEMPLATE = re.compile(r"%[sd]|\{[^}]*\}")


@dataclass
class NodeInfo:
    path: str  # scene-relative path, "." for the root
    name: str
    type: str | None  # None when the node comes from an instanced scene
    script: str | None = None  # res:// path
    instance: str | None = None  # res:// path of the instanced scene
    groups: list[str] = field(default_factory=list)
    unique: bool = False  # unique_name_in_owner, reachable as %Name
    node_paths: list[str] = field(default_factory=list)  # NodePath("…") property values set in the scene

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "type": self.type,
            "script": self.script,
            "instance": self.instance,
            "groups": self.groups,
            "unique": self.unique,
            "node_paths": self.node_paths,
        }


@dataclass
class Connection:
    signal: str
    from_node: str
    to_node: str
    method: str

    def to_dict(self) -> dict:
        return {"signal": self.signal, "from": self.from_node, "to": self.to_node, "method": self.method}


@dataclass
class SceneInfo:
    path: str
    uid: str | None = None
    root: NodeInfo | None = None
    nodes: list[NodeInfo] = field(default_factory=list)
    ext_resources: list[dict] = field(default_factory=list)  # {id,type,path}
    connections: list[Connection] = field(default_factory=list)
    inherits: str | None = None  # base scene path when the root is `instance=`

    @property
    def scripts(self) -> list[str]:
        return _uniq([n.script for n in self.nodes if n.script])

    @property
    def instances(self) -> list[str]:
        return _uniq([n.instance for n in self.nodes if n.instance])

    @property
    def resources(self) -> list[str]:
        """Non-script, non-scene external resources (textures, fonts, .tres)."""
        return _uniq(
            [r["path"] for r in self.ext_resources if r["type"] not in ("Script", "PackedScene")]
        )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "uid": self.uid,
            "root": self.root.to_dict() if self.root else None,
            "inherits": self.inherits,
            "nodes": [n.to_dict() for n in self.nodes],
            "scripts": self.scripts,
            "instances": self.instances,
            "resources": self.resources,
            "connections": [c.to_dict() for c in self.connections],
        }


@dataclass
class ResourceInfo:
    path: str
    type: str | None
    script: str | None = None
    resources: list[str] = field(default_factory=list)  # other external resources it names

    def to_dict(self) -> dict:
        return {"path": self.path, "type": self.type, "script": self.script, "resources": self.resources}


@dataclass
class Project:
    root: str  # filesystem root
    name: str | None = None
    main_scene: str | None = None
    features: list[str] = field(default_factory=list)
    autoloads: dict[str, str] = field(default_factory=dict)  # Name -> res:// path
    scenes: dict[str, SceneInfo] = field(default_factory=dict)
    scripts: dict[str, gdscript.ScriptInfo] = field(default_factory=dict)
    resources: dict[str, ResourceInfo] = field(default_factory=dict)
    data: list[str] = field(default_factory=list)  # res:// paths of .json/.csv/.gdshader files
    uids: dict[str, str] = field(default_factory=dict)  # uid:// -> res://

    # derived
    used_by: dict[str, list[str]] = field(default_factory=dict)  # res:// -> [res:// or "autoload:Name"]
    classes: dict[str, str] = field(default_factory=dict)  # class_name -> res://
    groups: dict[str, dict] = field(default_factory=dict)  # group -> {scenes: {scene: [nodes]}, joined_in, queried_in}

    def chain(self, path: str | None) -> list:
        """A script and its ancestors, as far as the project's own scripts reach."""
        out: list = []
        seen: set[str] = set()
        while path and path in self.scripts and path not in seen:
            seen.add(path)
            script = self.scripts[path]
            out.append(script)
            ext = script.extends
            path = ext if ext and ext.startswith("res://") else self.classes.get(ext or "")
        return out

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "main_scene": self.main_scene,
            "features": self.features,
            "autoloads": self.autoloads,
            "scenes": {k: v.to_dict() for k, v in sorted(self.scenes.items())},
            "scripts": {k: v.to_dict() for k, v in sorted(self.scripts.items())},
            "resources": {k: v.to_dict() for k, v in sorted(self.resources.items())},
            "data": {k: {"used_by": sorted(self.used_by.get(k, []))} for k in sorted(self.data)},
            "classes": dict(sorted(self.classes.items())),
            "groups": {k: v for k, v in sorted(self.groups.items())},
            "used_by": {k: sorted(v) for k, v in sorted(self.used_by.items())},
        }


def _uniq(items):
    seen = set()
    out = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _walk(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            yield os.path.join(dirpath, fn)


def _res(root: str, fs_path: str) -> str:
    return "res://" + os.path.relpath(fs_path, root).replace(os.sep, "/")


def _read_project_godot(project: Project) -> None:
    path = os.path.join(project.root, "project.godot")
    if not os.path.exists(path):
        return
    for sec in tscn.parse_file(path):
        if sec.name == "application":
            project.name = sec.prop_str("config/name")
            project.main_scene = sec.prop_str("run/main_scene")
            feats = sec.props.get("config/features")
            if feats:
                v = tscn.parse_value(feats)
                project.features = v if isinstance(v, list) else []
        elif sec.name == "autoload":
            for name, raw in sec.props.items():
                v = tscn.parse_value(raw)
                if isinstance(v, str):
                    project.autoloads[name] = v.lstrip("*")


def _read_scene(project: Project, res_path: str, fs_path: str) -> SceneInfo:
    scene = SceneInfo(path=res_path)
    ext: dict[str, dict] = {}
    for sec in tscn.parse_file(fs_path):
        if sec.name in ("gd_scene", "gd_resource"):
            scene.uid = sec.attr_str("uid")
        elif sec.name == "ext_resource":
            entry = {"id": sec.attr_str("id"), "type": sec.attr_str("type"), "path": sec.attr_str("path")}
            uid = sec.attr_str("uid")
            if uid and entry["path"]:
                project.uids.setdefault(uid, entry["path"])
            ext[str(entry["id"])] = entry
            scene.ext_resources.append(entry)
        elif sec.name == "node":
            name = sec.attr_str("name") or "?"
            parent = sec.attr_str("parent")
            if parent is None:
                npath = "."
            elif parent == ".":
                npath = name
            else:
                npath = f"{parent}/{name}"
            node = NodeInfo(path=npath, name=name, type=sec.attr_str("type"))
            inst = sec.attr_ref("instance")
            if inst and inst.id in ext:
                node.instance = ext[inst.id]["path"]
            script = sec.prop_ref("script")
            if isinstance(script, tscn.Ref) and script.id in ext:
                node.script = ext[script.id]["path"]
            groups = sec.attrs.get("groups")
            if isinstance(groups, list):
                node.groups = groups
            node.unique = sec.props.get("unique_name_in_owner", "").strip() == "true"
            for raw in sec.props.values():
                m = _NODEPATH_PROP.match(raw.strip())
                if m and m.group(1):
                    node.node_paths.append(m.group(1))
            scene.nodes.append(node)
            if parent is None:
                scene.root = node
                if node.instance:
                    scene.inherits = node.instance
        elif sec.name == "connection":
            scene.connections.append(
                Connection(
                    signal=sec.attr_str("signal") or "?",
                    from_node=sec.attr_str("from") or "?",
                    to_node=sec.attr_str("to") or "?",
                    method=sec.attr_str("method") or "?",
                )
            )
    return scene


def _read_resource(project: Project, res_path: str, fs_path: str) -> ResourceInfo:
    info = ResourceInfo(path=res_path, type=None)
    ext: dict[str, dict] = {}
    for sec in tscn.parse_file(fs_path):
        if sec.name == "gd_resource":
            info.type = sec.attr_str("type")
            uid = sec.attr_str("uid")
            if uid:
                project.uids[uid] = res_path
        elif sec.name == "ext_resource":
            entry = {"type": sec.attr_str("type"), "path": sec.attr_str("path")}
            ext[str(sec.attr_str("id"))] = entry
            uid = sec.attr_str("uid")
            if uid and entry["path"]:
                project.uids.setdefault(uid, entry["path"])
            if entry["path"] and entry["type"] != "Script":
                info.resources.append(entry["path"])
        elif sec.name == "resource":
            ref = sec.prop_ref("script")
            if isinstance(ref, tscn.Ref) and ref.id in ext:
                info.script = ext[ref.id]["path"]
    return info


def _resolve_uid(project: Project, value: str | None) -> str | None:
    if value and value.startswith("uid://"):
        return project.uids.get(value, value)
    return value


def _derive(project: Project) -> None:
    def use(target: str | None, by: str) -> None:
        if target:
            project.used_by.setdefault(target, [])
            if by not in project.used_by[target]:
                project.used_by[target].append(by)

    for name, path in project.autoloads.items():
        use(path, f"autoload:{name}")
    for scene in project.scenes.values():
        scene.uid and project.uids.setdefault(scene.uid, scene.path)
    project.main_scene = _resolve_uid(project, project.main_scene)
    for scene in project.scenes.values():
        for s in scene.scripts:
            use(s, scene.path)
        for i in scene.instances:
            use(i, scene.path)
        for r in scene.resources:
            use(r, scene.path)
    all_paths = sorted(set(project.scenes) | set(project.scripts) | set(project.resources) | set(project.data))
    for script in project.scripts.values():
        if script.class_name:
            project.classes[script.class_name] = script.path
        for target in script.loads + script.refs:
            if target != script.path:
                use(target, script.path)
            # "res://data/" + id + ".json" and "res://data/%s.json": the
            # literal names a directory, so every file under it is a use.
            prefix, suffix = _built_path(target)
            if prefix is not None:
                for path in all_paths:
                    if path != script.path and path.startswith(prefix) and path.endswith(suffix):
                        use(path, script.path)
        if script.extends and script.extends.startswith("res://"):
            use(script.extends, script.path)
    for res in project.resources.values():
        use(res.script, res.path)
        for r in _uniq(res.resources):
            use(r, res.path)
    # A class_name or autoload named anywhere in a script (X.new(), a static
    # call, a type hint, `is X`, `extends X`) is a use of its script. This is
    # where most uses live in a project that builds its UI in code.
    by_name = dict(project.classes)
    by_name.update(project.autoloads)
    for script in project.scripts.values():
        for name, target in by_name.items():
            if target != script.path and name in script.idents:
                use(target, script.path)
    for users in project.used_by.values():
        users.sort()
    # Groups: membership from scenes, add_to_group and queries from code.
    def group(name: str) -> dict:
        return project.groups.setdefault(name, {"scenes": {}, "joined_in": [], "queried_in": []})

    for spath, scene in sorted(project.scenes.items()):
        for node in scene.nodes:
            for g in node.groups:
                group(g)["scenes"].setdefault(spath, []).append(node.path)
    for spath, script in sorted(project.scripts.items()):
        for g in script.groups_joined:
            group(g)["joined_in"].append(spath)
        for g in script.groups_queried:
            group(g)["queried_in"].append(spath)


def _built_path(literal: str) -> tuple[str | None, str]:
    """('res://data/', '.json') for a literal that names a directory or a
    template; (None, '') for a plain file path."""
    if literal.endswith("/"):
        return (literal, "") if len(literal) > len("res://") else (None, "")
    parts = _TEMPLATE.split(literal)
    if len(parts) > 1 and "/" in parts[0]:
        return parts[0][: parts[0].rfind("/") + 1], parts[-1]
    # "res://data/battle": no extension on the last segment, so a directory
    # joined at runtime (path_join, + "/" + name).
    last = literal.rsplit("/", 1)[-1]
    if len(parts) == 1 and last and "." not in last:
        return literal + "/", ""
    return None, ""


def scan(root: str) -> Project:
    root = os.path.abspath(root)
    project = Project(root=root)
    _read_project_godot(project)
    for fs_path in _walk(root):
        res_path = _res(root, fs_path)
        if fs_path.endswith(".tscn"):
            project.scenes[res_path] = _read_scene(project, res_path, fs_path)
        elif fs_path.endswith(".gd"):
            project.scripts[res_path] = gdscript.scan_file(res_path, fs_path)
        elif fs_path.endswith(".cs"):
            project.scripts[res_path] = csharp.scan_file(res_path, fs_path)
        elif fs_path.endswith(DATA_EXTS):
            project.data.append(res_path)
        elif fs_path.endswith(".tres"):
            project.resources[res_path] = _read_resource(project, res_path, fs_path)
        elif fs_path.endswith(".uid"):
            try:
                with open(fs_path, encoding="utf-8") as fh:
                    uid = fh.read().strip()
                if uid.startswith("uid://"):
                    project.uids[uid] = res_path[: -len(".uid")]
            except OSError:
                pass
    _derive(project)
    return project

"""Walk a Godot project and build the map model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import gdscript, tscn

SKIP_DIRS = {".godot", ".git", ".import", "addons", "node_modules", ".venv", "builds", "shots"}


@dataclass
class NodeInfo:
    path: str  # scene-relative path, "." for the root
    name: str
    type: str | None  # None when the node comes from an instanced scene
    script: str | None = None  # res:// path
    instance: str | None = None  # res:// path of the instanced scene
    groups: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "type": self.type,
            "script": self.script,
            "instance": self.instance,
            "groups": self.groups,
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

    def to_dict(self) -> dict:
        return {"path": self.path, "type": self.type, "script": self.script}


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
    uids: dict[str, str] = field(default_factory=dict)  # uid:// -> res://

    # derived
    used_by: dict[str, list[str]] = field(default_factory=dict)  # res:// -> [res:// or "autoload:Name"]
    classes: dict[str, str] = field(default_factory=dict)  # class_name -> res://

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "main_scene": self.main_scene,
            "features": self.features,
            "autoloads": self.autoloads,
            "scenes": {k: v.to_dict() for k, v in sorted(self.scenes.items())},
            "scripts": {k: v.to_dict() for k, v in sorted(self.scripts.items())},
            "resources": {k: v.to_dict() for k, v in sorted(self.resources.items())},
            "classes": dict(sorted(self.classes.items())),
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
            ext[str(sec.attr_str("id"))] = {"type": sec.attr_str("type"), "path": sec.attr_str("path")}
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
    for script in project.scripts.values():
        if script.class_name:
            project.classes[script.class_name] = script.path
        for target in script.loads + script.refs:
            if target != script.path:
                use(target, script.path)
        if script.extends and script.extends.startswith("res://"):
            use(script.extends, script.path)
    for res in project.resources.values():
        use(res.script, res.path)
    # extends by class_name is a use too
    for script in project.scripts.values():
        if script.extends and script.extends in project.classes:
            use(project.classes[script.extends], script.path)


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

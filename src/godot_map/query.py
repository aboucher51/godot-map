"""Questions asked of a scanned project: who uses this, and does this node
path exist. Pure functions over the model; the CLI prints them."""

from __future__ import annotations

from dataclasses import dataclass

from .scan import Project, SceneInfo


def resolve_target(project: Project, name: str) -> str:
    """A res:// path, a project-relative path, a class_name or an autoload name -> res:// path."""
    if name in project.classes:
        return project.classes[name]
    if name in project.autoloads:
        return project.autoloads[name]
    if name.startswith("res://"):
        return name
    return "res://" + name.lstrip("./")


def users_tree(project: Project, target: str, depth: int = 1, cap: int = 200) -> list[str]:
    """Transitive users of ``target`` as indented lines, depth-first, each
    path expanded once (a repeat is marked, not expanded again). Stops at
    ``cap`` lines with a final "... N more" line."""
    lines: list[str] = []
    expanded: set[str] = set()
    overflow = 0

    def walk(path: str, level: int) -> None:
        nonlocal overflow
        for user in project.used_by.get(path, []):
            if len(lines) >= cap:
                overflow += 1
                continue
            indent = "  " * level
            if user.startswith("autoload:") or level + 1 >= depth:
                lines.append(indent + user)
                continue
            if user in expanded:
                lines.append(f"{indent}{user} (see above)")
                continue
            expanded.add(user)
            lines.append(indent + user)
            walk(user, level + 1)

    expanded.add(target)
    walk(target, 0)
    if overflow:
        lines.append(f"... {overflow} more (cap {cap})")
    return lines


@dataclass
class MissingPath:
    script: str
    node_path: str
    scene: str
    attached_at: str

    def __str__(self) -> str:
        return f"{self.script}: {self.node_path} not in {self.scene} (attached at {self.attached_at})"


def _node_index(project: Project, scene: SceneInfo, seen: set[str] | None = None) -> dict[str, object]:
    """Scene-relative path -> NodeInfo, including nodes inherited from a base scene."""
    seen = seen or set()
    index: dict[str, object] = {}
    if scene.inherits and scene.inherits in project.scenes and scene.inherits not in seen:
        seen.add(scene.path)
        index.update(_node_index(project, project.scenes[scene.inherits], seen))
    for n in scene.nodes:
        index[n.path] = n
    return index


def _exists(project: Project, scene: SceneInfo, base: str, rel: str, hops: int = 0) -> bool | None:
    """True/False when the answer is known; None when the path leaves what
    the map can see (an instanced scene outside the project, `..` above
    the root, a node added at runtime)."""
    if hops > 20:
        return None
    index = _node_index(project, scene)
    segments = [s for s in rel.split("/") if s]
    cur = base
    if rel.startswith("%"):
        name = segments[0][1:]
        hits = [n for n in scene.nodes if n.unique and n.name == name]
        if not hits:
            return False
        cur = hits[0].path  # type: ignore[union-attr]
        segments = segments[1:]
    for i, seg in enumerate(segments):
        if seg == ".":
            continue
        if seg == "..":
            if cur == ".":
                return None
            cur = cur.rsplit("/", 1)[0] if "/" in cur else "."
            continue
        nxt = seg if cur == "." else f"{cur}/{seg}"
        if nxt in index:
            cur = nxt
            continue
        # Into an instanced scene?
        node = index.get(cur)
        inst = getattr(node, "instance", None)
        if inst and inst in project.scenes:
            return _exists(project, project.scenes[inst], ".", "/".join(segments[i:]), hops + 1)
        if inst:
            return None
        return False
    return True


def check_node_paths(project: Project, scripts: list[str] | None = None) -> tuple[int, list[MissingPath], int]:
    """For every script attached in a scene, confirm each node path it uses
    exists under the node it is attached to. A path through a node the
    script itself names (`box.name = "Menu"`) is built at runtime and is
    skipped. Returns (checked, missing, skipped)."""
    wanted = set(scripts) if scripts else None
    checked = 0
    skipped = 0
    missing: list[MissingPath] = []
    for spath, scene in sorted(project.scenes.items()):
        for node in scene.nodes:
            if not node.script or node.script not in project.scripts:
                continue
            if wanted is not None and node.script not in wanted:
                continue
            script = project.scripts[node.script]
            for rel in script.node_paths:
                if any(seg.lstrip("%") in script.named_nodes for seg in rel.split("/")):
                    skipped += 1
                    continue
                checked += 1
                if _exists(project, scene, node.path, rel) is False:
                    missing.append(MissingPath(node.script, rel, spath, node.path))
    return checked, missing, skipped

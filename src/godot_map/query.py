"""Questions asked of a scanned project: who uses this, and does this node
path exist. Pure functions over the model; the CLI prints them."""

from __future__ import annotations

import os
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
            if wanted is None:
                for rel in node.node_paths:  # exported NodePath set in the scene
                    checked += 1
                    if _exists(project, scene, node.path, rel) is False:
                        missing.append(MissingPath(spath, f'NodePath("{rel}")', spath, node.path))
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


# Signals the engine declares on the node types a project script usually
# extends. A signal on this list is never reported as undeclared. It is not
# complete: an engine signal it lacks is reported as a false positive, and
# the fix is to add it here.
ENGINE_SIGNALS = frozenset("""
ready tree_entered tree_exiting tree_exited child_entered_tree child_exiting_tree
child_order_changed renamed replacing_by editor_description_changed
property_list_changed script_changed
draw hidden item_rect_changed visibility_changed
resized gui_input mouse_entered mouse_exited focus_entered focus_exited
size_flags_changed minimum_size_changed theme_changed
pressed toggled button_down button_up
text_changed text_submitted text_change_rejected value_changed changed
item_selected item_activated item_clicked item_focused multi_selected empty_clicked
tab_changed tab_selected tab_clicked tab_hovered tab_close_pressed pre_popup_pressed
body_entered body_exited body_shape_entered body_shape_exited
area_entered area_exited area_shape_entered area_shape_exited
input_event sleeping_state_changed
timeout finished loop_finished step_finished
animation_finished animation_started animation_changed animation_looped
current_animation_changed caches_cleared animation_libraries_updated animation_list_changed
frame_changed sprite_frames_changed texture_changed
request_completed
about_to_popup popup_hide close_requested go_back_requested window_input
files_dropped titlebar_changed focus_entered dpi_changed theme_changed
node_added node_removed node_renamed node_configuration_warning_changed
tree_changed tree_process_mode_changed process_frame physics_frame
peer_connected peer_disconnected connected_to_server connection_failed server_disconnected
peer_authenticating peer_authentication_failed
screen_entered screen_exited
drag_started drag_ended scroll_started scroll_ended
confirmed canceled custom_action
color_changed preset_added preset_removed
meta_clicked meta_hover_started meta_hover_ended
navigation_finished path_changed target_reached velocity_computed waypoint_reached link_reached
lines_edited_from caret_changed gutter_clicked
cell_selected item_edited item_collapsed nothing_selected button_clicked
mouse_shape_entered mouse_shape_exited
camera_entered camera_exited
wall_min_slide_angle_changed
""".split())


@dataclass
class Problem:
    source: str  # res:// path of the file the problem is in
    kind: str  # "missing", "signal", "method"
    detail: str

    def __str__(self) -> str:
        return f"{self.source}: {self.detail}"


def _on_disk(project: Project, res_path: str) -> bool:
    return os.path.exists(os.path.join(project.root, res_path[len("res://"):]))


def _checkable_literal(path: str) -> bool:
    """A concrete file path: no template, no directory, has an extension."""
    if any(c in path for c in "%{*"):
        return False
    last = path.rstrip("/").rsplit("/", 1)[-1]
    return not path.endswith("/") and "." in last


def broken_refs(project: Project) -> list[Problem]:
    """Every res:// reference the map holds that names nothing on disk."""
    out: list[Problem] = []

    def check(source: str, target: str | None, what: str) -> None:
        # addons/ is outside the map (never scanned); a script loading an
        # optional addon guards it with ResourceLoader.exists, so it is not judged here.
        if what in ("load", "literal") and target and target.startswith("res://addons/"):
            return
        if target and target.startswith("res://") and not _on_disk(project, target):
            out.append(Problem(source, "missing", f"{what} {target} is not on disk"))

    check("res://project.godot", project.main_scene, "main scene")
    for name, path in project.autoloads.items():
        check("res://project.godot", path, f"autoload {name}")
    for spath, scene in sorted(project.scenes.items()):
        for r in scene.ext_resources:
            check(spath, r["path"], f"ext_resource {r['type']}")
    for rpath, res in sorted(project.resources.items()):
        check(rpath, res.script, "script")
        for r in res.resources:
            check(rpath, r, "ext_resource")
    for spath, script in sorted(project.scripts.items()):
        if script.extends and script.extends.startswith("res://"):
            check(spath, script.extends, "extends")
        for target in script.loads:
            check(spath, target, "load")
        # A test script's literals are often deliberately absent files.
        if spath.startswith("res://tests/") or spath.startswith("res://test/"):
            continue
        for target in script.refs:
            if _checkable_literal(target):
                check(spath, target, "literal")
    return out


def _snake(name: str) -> str:
    """BodyEntered -> body_entered, so a C# engine signal matches the list."""
    import re

    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _declared_signals(project: Project, path: str | None) -> set[str] | None:
    """Signals a script or its project ancestors declare; None when the script is unknown."""
    if not path or path not in project.scripts:
        return None
    return {sig for s in project.chain(path) for sig in s.signals}


def _declared_funcs(project: Project, path: str | None) -> set[str] | None:
    if not path or path not in project.scripts:
        return None
    return {f for s in project.chain(path) for f in s.funcs}


def signal_problems(project: Project) -> list[Problem]:
    """Emits and connects on a signal the target does not declare, and scene
    connections to a method the target script does not define.

    Only targets the map can see are checked: an autoload or class_name
    (``EventBus.saved.connect``), a script's own signals (``saved.emit()``,
    ``emit_signal("saved")``), and connection targets that carry a project
    script. A signal on ``ENGINE_SIGNALS`` is never reported."""
    out: list[Problem] = []
    by_name = dict(project.classes)
    by_name.update(project.autoloads)
    for spath, script in sorted(project.scripts.items()):
        own = _declared_signals(project, spath) or set()
        for verb, targets in (("emits", script.emits), ("connects to", script.connects)):
            for target in targets:
                if "." in target:
                    obj, sig = target.rsplit(".", 1)
                    if obj not in by_name:
                        continue  # a variable: its type is unknown here
                    declared = _declared_signals(project, by_name[obj])
                else:
                    obj, sig, declared = None, target, own
                    if sig in script.vars or sig in by_name:
                        continue  # a Signal held in a variable, or Object.connect(name, callable) on an autoload
                if declared is None or sig in declared or sig in ENGINE_SIGNALS or _snake(sig) in ENGINE_SIGNALS:
                    continue
                where = f"{obj} ({_short(by_name[obj])})" if obj else "this script"
                out.append(Problem(spath, "signal", f"{verb} {sig}, which {where} does not declare"))
    for spath, scene in sorted(project.scenes.items()):
        index = _node_index(project, scene)
        for c in scene.connections:
            to = c.to_node
            node = index.get(to)
            if node is None:
                out.append(Problem(spath, "method", f"[connection] to {to}: no such node"))
                continue
            script = node.script  # type: ignore[union-attr]
            if not script and getattr(node, "instance", None) in project.scenes:
                root = project.scenes[node.instance].root  # type: ignore[union-attr]
                script = root.script if root else None
            funcs = _declared_funcs(project, script)
            if funcs is None:
                continue  # no project script on the target: cannot tell
            if c.method not in funcs:
                out.append(Problem(spath, "method", f"[connection] {c.signal} → {to}.{c.method}(): {_short(script)} has no such func"))
    return out


def problems(project: Project) -> list[Problem]:
    return broken_refs(project) + signal_problems(project)


def signal_users(project: Project, target: str) -> list[str] | None:
    """For ``EventBus.saved`` or ``Actor.died``: who emits, who connects, which scenes wire it."""
    from .render import signal_wiring

    if "." not in target:
        return None
    obj, sig = target.rsplit(".", 1)
    if obj in project.autoloads:
        key = target
    elif obj in project.classes:
        key = sig
    else:
        return None
    for row in signal_wiring(project, all_rows=True):
        if row["signal"] == key:
            return (
                [f"emit: {p}" for p in row["emitted_in"]]
                + [f"connect: {p}" for p in row["connected_in_code"]]
                + [f"scene: {s}" for s in row["connected_in_scenes"]]
            )
    return []


def changed_files(project: Project) -> list[str]:
    """res:// paths of files modified or untracked in the working tree, via git."""
    import subprocess

    try:
        tracked = subprocess.run(
            ["git", "-C", project.root, "diff", "--name-only", "--relative", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout
        untracked = subprocess.run(
            ["git", "-C", project.root, "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted({"res://" + ln.strip() for ln in (tracked + untracked).splitlines() if ln.strip()})


def _short(path: str | None) -> str:
    return path[len("res://"):] if path and path.startswith("res://") else str(path)

"""godot-map command line.

    godot-map [ROOT]                write PROJECT_MAP.md and .godot-map/graph.json
    godot-map ROOT --check          exit 1 if the committed map is stale
    godot-map ROOT --stdout         print the Markdown instead of writing
    godot-map ROOT --who scenes/hud.tscn
    godot-map ROOT --who Enemy --depth 3
                                    everything that references a path, class or autoload
    godot-map ROOT --who EventBus.saved
                                    who emits, connects to and wires a signal
    godot-map ROOT --who --changed  users of every file modified or untracked in git
    godot-map ROOT --paths [scripts/hud.gd ...]
                                    every $Node path in a script, checked against the
                                    scenes the script is attached to; exit 1 if one is missing
    godot-map ROOT --problems       broken res:// references, undeclared signals,
                                    connections to missing methods; exit 1 if any
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .query import changed_files, check_node_paths, problems, resolve_target, signal_users, users_tree
from .render import render_json, render_markdown
from .scan import scan


def _write_if_changed(path: str, content: str) -> bool:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.read() == content:
                return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="godot-map", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="project directory (holds project.godot)")
    ap.add_argument("--out", default="PROJECT_MAP.md", help="Markdown path, relative to ROOT")
    ap.add_argument("--json", default=".godot-map/graph.json", help="JSON path, relative to ROOT ('' to skip)")
    ap.add_argument("--check", action="store_true", help="exit 1 if the written map differs from a fresh one")
    ap.add_argument("--stdout", action="store_true", help="print the Markdown, write nothing")
    ap.add_argument("--no-trees", action="store_true", help="omit per-scene node trees from the Markdown")
    ap.add_argument("--mermaid", action="store_true", help="append a Mermaid scene-instance graph to the Markdown")
    ap.add_argument("--who", metavar="TARGET", nargs="?", const="", help="list what references a res:// path, class_name, autoload or Autoload.signal, and exit")
    ap.add_argument("--changed", action="store_true", help="with --who: every file git sees as modified or untracked")
    ap.add_argument("--problems", action="store_true", help="report broken references and signal/method mismatches; exit 1 if any")
    ap.add_argument("--depth", type=int, default=1, metavar="N", help="with --who: follow users N levels as an indented tree")
    ap.add_argument("--paths", nargs="*", metavar="SCRIPT", help="check node paths in these scripts (all attached scripts if none) and exit")
    ap.add_argument("--version", action="version", version=f"godot-map {__version__}")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.exists(os.path.join(root, "project.godot")):
        print(f"godot-map: no project.godot in {root}", file=sys.stderr)
        return 2
    project = scan(root)

    if args.who is not None:
        if args.changed:
            changed = [p for p in changed_files(project) if p in project.used_by]
            for path in changed:
                print(path)
                for ln in users_tree(project, path, depth=max(1, args.depth)):
                    print("  " + ln)
            if not changed:
                print("godot-map: nothing changed that anything references")
            return 0
        if not args.who:
            ap.error("--who needs a target (or --changed)")
        sig = signal_users(project, args.who)
        if sig is not None:
            for ln in sig:
                print(ln)
            return 0 if sig else 1
        target = resolve_target(project, args.who)
        lines = users_tree(project, target, depth=max(1, args.depth))
        if args.depth > 1 and lines:
            print(target)
            lines = ["  " + ln for ln in lines]
        for ln in lines:
            print(ln)
        return 0 if lines else 1

    if args.problems:
        found = problems(project)
        for pr in found:
            print(pr)
        print(f"godot-map: {len(found)} problem{'s' if len(found) != 1 else ''}")
        return 1 if found else 0

    if args.paths is not None:
        scripts = [resolve_target(project, s) for s in args.paths] or None
        unknown = [s for s in scripts or [] if s not in project.scripts]
        for s in unknown:
            print(f"godot-map: no such script {s}", file=sys.stderr)
        checked, missing, skipped = check_node_paths(project, scripts)
        for m in missing:
            print(m)
        note = f", {skipped} built at runtime (skipped)" if skipped else ""
        print(f"godot-map: {checked} node paths checked, {len(missing)} missing{note}")
        return 1 if missing or unknown else 0

    md = render_markdown(project, trees=not args.no_trees, mermaid=args.mermaid)
    js = render_json(project) if args.json else None

    if args.stdout:
        sys.stdout.write(md)
        return 0

    md_path = os.path.join(root, args.out)
    json_path = os.path.join(root, args.json) if args.json else None

    if args.check:
        stale = []
        try:
            with open(md_path, encoding="utf-8") as fh:
                if fh.read() != md:
                    stale.append(args.out)
        except OSError:
            stale.append(args.out)
        if json_path and js is not None:
            try:
                with open(json_path, encoding="utf-8") as fh:
                    if fh.read() != js:
                        stale.append(args.json)
            except OSError:
                stale.append(args.json)
        if stale:
            print("godot-map: stale: " + ", ".join(stale) + " (run `godot-map .`)")
            return 1
        print("godot-map: up to date")
        return 0

    changed = _write_if_changed(md_path, md)
    if json_path and js is not None:
        changed = _write_if_changed(json_path, js) or changed
    print(
        f"godot-map: {len(project.scenes)} scenes, {len(project.scripts)} scripts -> "
        f"{args.out}" + (f", {args.json}" if json_path else "") + ("" if changed else " (unchanged)")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

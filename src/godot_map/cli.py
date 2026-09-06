"""godot-map command line.

    godot-map [ROOT]                write PROJECT_MAP.md and .godot-map/graph.json
    godot-map ROOT --check          exit 1 if the committed map is stale
    godot-map ROOT --stdout         print the Markdown instead of writing
    godot-map ROOT --who res://scenes/hud.tscn
                                    everything that references a path
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
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
    ap.add_argument("--who", metavar="RES_PATH", help="list what references a res:// path and exit")
    ap.add_argument("--version", action="version", version=f"godot-map {__version__}")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.exists(os.path.join(root, "project.godot")):
        print(f"godot-map: no project.godot in {root}", file=sys.stderr)
        return 2
    project = scan(root)

    if args.who:
        target = args.who if args.who.startswith("res://") else "res://" + args.who.lstrip("./")
        users = project.used_by.get(target, [])
        for u in users:
            print(u)
        return 0 if users else 1

    md = render_markdown(project, trees=not args.no_trees)
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

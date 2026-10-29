# CLAUDE.md

## What this repo is

`godot-map` is a Python tool that uses only the standard library. It
maps a Godot 4 project into two files. Agents read `PROJECT_MAP.md` at the
start of a task. They query `.godot-map/graph.json` during the task. With
these files, Claude can answer "who uses this scene / script / signal" and
"does this node path exist" without reading every `.tscn`. Every project
under `~/godot-projects/` uses this tool. Kombucha's `docs/godot-tooling.md`
holds the rule that tells agents to read the map. Kombucha's
`tools/check.sh` runs the CI `--check`. Neither lives in this repo.

## Rules

- Do not add dependencies. `uv tool install` on a fresh machine must need
  nothing but Python 3.10+.
- Keep the parsers in `tscn.py` and `gdscript.py` forgiving on purpose.
  We tried `godot_parser` from PyPI. It rejects every
  `default_bus_layout.tres` (`bus/1/name = &"Music"`).
- Never reject a file. When a reader meets a shape it does not know, it
  keeps the text raw and ignores it.
- Treat a crash on one file as a bug. Add the file's shape to
  `tests/fixtures/mini/` and fix the reader.
- Keep the output deterministic. The same project must give the same
  bytes. Sort keys and paths, and write no timestamps. Or `--check` (the
  mode that fails when the committed map is stale) breaks.
- Keep the Markdown short. An agent reads it whole at the start of a task.
  Add a section only if it saves agents from grepping. Put detail in the
  JSON instead.
- `render.py` leaves out a scene's node tree when the scene has more than
  `max_tree_nodes` nodes (40 by default).
- Test against real projects. `tests/test_real_projects.py` runs the
  scanner over every sibling under `~/godot-projects/` when present. It
  checks that the scanner does not raise.
- Run `uv run pytest` before every commit.

## Layout

```
src/godot_map/
  tscn.py       section-level reader for .tscn / .tres / project.godot
  gdscript.py   regex facts about a .gd
  csharp.py     the same facts about a .cs
  scan.py       walk the project, build the model, derive used_by/classes
  query.py      --who trees and the --paths node-path check
  render.py     Markdown + JSON
  cli.py        argparse entry point
tests/fixtures/mini/   a tiny Godot project covering every shape read
docs/plan.md           what is next
```

## Commands

```bash
uv run pytest                          # tests
uv run godot-map ~/godot-projects/Kombucha --stdout | head -60
uv tool install --editable . --reinstall   # refresh the installed command
```

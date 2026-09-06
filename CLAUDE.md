# CLAUDE.md

## What this repo is

`godot-map` is a stdlib-only Python tool that maps a Godot 4 project into
`PROJECT_MAP.md` (read by agents at the start of a task) and
`.godot-map/graph.json` (queried during it). It exists so Claude can answer
"who uses this scene / script / signal" and "does this node path exist"
without reading every `.tscn`. It is consumed by every project under
`~/godot-projects/`; the rule to read it and the CI `--check` live in
Kombucha's `docs/godot-tooling.md` and `tools/check.sh`, not here.

## Rules

- **No dependencies.** `uv tool install` on a fresh machine must need
  nothing but Python 3.10+. The parsers in `tscn.py` and `gdscript.py` are
  deliberately forgiving; `godot_parser` from PyPI was tried and rejects
  every `default_bus_layout.tres` (`bus/1/name = &"Music"`).
- **Never reject a file.** A shape the reader does not know is kept raw
  and ignored. A crash on one file is a bug; add the file's shape to
  `tests/fixtures/mini/` and fix the reader.
- **Output is deterministic.** Same project, same bytes: sorted keys,
  sorted paths, no timestamps. `--check` depends on it.
- **The Markdown is a budget.** It is read whole, at the start of a task.
  Add a section only if it removes greps; move detail to the JSON. Node
  trees are omitted above `max_tree_nodes`.
- **Test against real projects.** `tests/test_real_projects.py` runs the
  scanner over every sibling under `~/godot-projects/` when present and
  asserts it does not raise. Run `uv run pytest` before every commit.

## Layout

```
src/godot_map/
  tscn.py       section-level reader for .tscn / .tres / project.godot
  gdscript.py   regex facts about a .gd
  scan.py       walk the project, build the model, derive used_by/classes
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

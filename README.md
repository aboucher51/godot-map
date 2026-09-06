# godot-map

A structural map of a Godot 4 project, for coding agents and for you.

Godot keeps a project's shape in files no code-graph tool reads: `.tscn`
scenes carry the node trees, script attachments, instanced scenes and
signal connections; `project.godot` carries the autoloads. `godot-map`
reads those plus the declarations in every `.gd` and writes two things:

- **`PROJECT_MAP.md`** — the always-read tier. Autoloads and their
  signals, who emits and who listens on each autoload signal, every scene
  with its scripts, instances, connections and (for small scenes) its node
  tree, the `class_name` index, and the scripts nothing references. Short
  enough to read at the start of a task.
- **`.godot-map/graph.json`** — the query tier. Every node, script, resource
  and edge, plus a reverse index (`used_by`) from any `res://` path to
  everything that references it.

No engine, no LSP, no dependencies: it is a few hundred lines of Python
over the text formats, and it never rejects a file it does not fully
understand.

## Install

```bash
uv tool install --editable ~/godot-projects/godot-map   # from this checkout
# or, once published: uv tool install godot-map
```

## Use

```bash
godot-map .                        # write PROJECT_MAP.md and .godot-map/graph.json
godot-map . --check                # exit 1 if the committed map is stale (CI)
godot-map . --stdout               # print the Markdown
godot-map . --who scenes/hud.tscn  # everything that references a path
godot-map . --no-trees             # smaller Markdown, no per-scene node trees
```

Commit both outputs. A checkout then reads without the tool installed, and
`--check` in CI catches a map that fell behind the scenes.

## What it reads

| Source | Facts |
|---|---|
| `project.godot` | name, main scene (uid resolved), features, autoloads in order |
| `*.tscn` | uid, root, every node (name, type, parent path, groups), `script =` attachments, `instance=` scenes, `[connection]` blocks, external resources |
| `*.tres` | type, uid, attached script |
| `*.gd` | `class_name`, `extends`, `@tool`, `preload`/`load` paths, other `res://` literals, `signal` declarations, `func` names, `X.sig.emit(`, `X.sig.connect(`, `$Node` paths |
| `*.uid` | uid → path, so `uid://` references resolve |

Skipped: `.godot/`, `addons/`, `builds/`, `shots/`, dot-directories.

## In an agent's instructions

One line does most of the work:

> Read `PROJECT_MAP.md` before grepping for which scene uses a script, who
> connects to a signal, or whether a node path exists. Run `godot-map .`
> after adding or moving scenes or scripts.

## Limits

The GDScript pass is regex, not a parser: a string literal that looks like
a declaration, or a `preload` built from a variable, will be missed or
misread. Scenes are read at the section level, so a property value in a
shape the reader does not know is kept verbatim and ignored. The map is for
orientation; the engine, the LSP and the tests are for proof.

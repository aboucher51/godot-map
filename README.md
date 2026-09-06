# godot-map

A structural map of a Godot 4 project, for coding agents and for you.

Godot keeps a project's shape in files no code-graph tool reads: `.tscn`
scenes carry the node trees, script attachments, instanced scenes and
signal connections; `project.godot` carries the autoloads. `godot-map`
reads those plus the declarations in every `.gd` and `.cs` and writes two
things:

- **`PROJECT_MAP.md`** — the always-read tier. Autoloads and their
  signals, every declared signal with who emits it and who listens (in
  code and in scenes), every scene with its scripts, instances,
  connections and (for small scenes) its node tree, the `class_name`
  index, the scripts nothing references, and where the data files live.
  Short enough to read at the start of a task.
- **`.godot-map/graph.json`** — the query tier. Every node, script, resource
  and data file, plus a reverse index (`used_by`) from any `res://` path to
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
godot-map . --who Enemy --depth 3  # ...or a class_name / autoload, transitively, as a tree
godot-map . --paths                # every $Node / %Unique path in every attached script,
                                   # checked against the scenes; exit 1 if one is missing
godot-map . --paths scripts/hud.gd # the same for one script
godot-map . --no-trees             # smaller Markdown, no per-scene node trees
godot-map . --mermaid              # append a Mermaid scene-instance graph (off by default)
```

Commit both outputs. A checkout then reads without the tool installed, and
`--check` in CI catches a map that fell behind the scenes. `--check`
compares against the same flags you pass it, so a project that commits
with `--mermaid` checks with `--mermaid`.

## What it reads

| Source | Facts |
|---|---|
| `project.godot` | name, main scene (uid resolved), features, autoloads in order |
| `*.tscn` | uid, root, every node (name, type, parent path, groups, `unique_name_in_owner`), `script =` attachments, `instance=` scenes, `[connection]` blocks, external resources |
| `*.tres` | type, uid, attached script, external resources it names (a shader, a texture) |
| `*.gd` | `class_name`, `extends`, `@tool`, `preload`/`load` paths, other `res://` literals, `signal` declarations, `func` names, `X.sig.emit(`, `X.sig.connect(`, `$Node`, `%Unique` and `get_node("…")` paths, `x.name = "…"` |
| `*.cs` | class and base, `[GlobalClass]`, `[Tool]`, `[Signal]` delegates, `GD.Load`/`ResourceLoader.Load` paths, `EmitSignal`, `+=` and `Connect(` listeners, `GetNode("…")` paths |
| `*.json`, `*.csv`, `*.gdshader` | listed, with who names them |
| `*.uid` | uid → path, so `uid://` references resolve |

A script is *used by* whatever attaches, autoloads, loads or extends it,
and by every script that names its `class_name` or autoload name in code
(`Enemy.new()`, a static call, a type hint). That last rule is where most
uses live in a project that builds its UI in code.

Skipped: `.godot/`, `addons/`, `builds/`, `shots/`, `bin/`, `obj/`, dot-directories.

## In an agent's instructions

One line does most of the work:

> Read `PROJECT_MAP.md` before grepping for which scene uses a script, who
> connects to a signal, or whether a node path exists. Run `godot-map .`
> after adding or moving scenes or scripts.

A PostToolUse hook on `.gd`/`.tscn` edits can run `godot-map .` so the map
never goes stale mid-task; Kombucha ships one as `tools/seeds/claude-hooks.json`.

## Limits

The GDScript and C# passes are regex, not parsers: a string literal that
looks like a declaration, or a `preload` built from a variable, will be
missed or misread. Scenes are read at the section level, so a property
value in a shape the reader does not know is kept verbatim and ignored.
`--paths` checks only paths relative to the script's own node
(`other.get_node("X")` is skipped) and skips paths through a node the
script names itself; a node added at runtime some other way is reported as
missing. The map is for orientation; the engine, the LSP and the tests are
for proof.

# godot-map

A structural map of a Godot 4 project, for coding agents and for you.

Godot keeps a project's shape in files that no code-graph tool reads.
`.tscn` scenes hold the node trees, script attachments, instanced scenes
and signal connections. `project.godot` holds the autoloads. `godot-map`
reads those files and the declarations in every `.gd` and `.cs`. Then it
writes two files:

- **`PROJECT_MAP.md`** — the always-read tier. Autoloads and their
  signals, every declared signal with who emits it and who listens (in
  code and in scenes), every scene with its scripts, instances,
  connections and (for small scenes) its node tree, the `class_name`
  index, the scripts nothing references, the groups, where the data files
  live, and the problems the engine would report on load (broken `res://`
  references, undeclared signals, connections to missing methods). Short
  enough to read at the start of a task.
- **`.godot-map/graph.json`** — the query tier. Every node, script, resource
  and data file, plus a reverse index (`used_by`) from any `res://` path to
  everything that references it.

The tool needs no engine, no LSP and no dependencies. It is a few hundred
lines of Python that read the text formats. It never rejects a file, even
one it does not fully understand.

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
godot-map . --who EventBus.saved   # who emits, connects to and wires a signal
godot-map . --who --changed        # users of every file git sees as modified or untracked
godot-map . --paths                # every $Node / %Unique path in every attached script and
                                   # every NodePath("…") set in a scene, checked; exit 1 on a miss
godot-map . --paths scripts/hud.gd # the same for one script
godot-map . --problems             # broken res:// references, signals the target does not
                                   # declare, connections to missing methods; exit 1 if any
godot-map . --no-trees             # smaller Markdown, no per-scene node trees
godot-map . --mermaid              # append a Mermaid scene-instance graph (off by default)
```

Commit both outputs. Then anyone can read the map in a checkout without the tool
installed. `--check` in CI catches a map that fell behind the scenes.
`--check` compares against the same flags you pass it. So a project that
commits with `--mermaid` must check with `--mermaid`.

## What it reads

| Source | Facts |
|---|---|
| `project.godot` | name, main scene (uid resolved), features, autoloads in order |
| `*.tscn` | uid, root, every node (name, type, parent path, groups, `unique_name_in_owner`, `NodePath("…")` properties), `script =` attachments, `instance=` scenes, `[connection]` blocks, external resources |
| `*.tres` | type, uid, attached script, external resources it names (a shader, a texture) |
| `*.gd` | `class_name`, `extends`, `@tool`, `preload`/`load` paths, other `res://` literals, `signal` declarations, `func` names, `X.sig.emit(`, `X.sig.connect(`, `$Node`, `%Unique` and `get_node("…")` paths, `x.name = "…"`, `add_to_group`, `get_nodes_in_group`/`call_group`/`is_in_group` |
| `*.cs` | class and base, `[GlobalClass]`, `[Tool]`, `[Signal]` delegates, `GD.Load`/`ResourceLoader.Load` paths, `EmitSignal`, `+=` and `Connect(` listeners, `GetNode("…")` paths, `AddToGroup`, `GetNodesInGroup` |
| `*.json`, `*.csv`, `*.gdshader` | listed, with who names them |
| `*.uid` | uid → path, so `uid://` references resolve |

A script is *used by* whatever attaches, autoloads, loads or extends it,
and by every script that names its `class_name` or autoload name in code
(`Enemy.new()`, a static call, a type hint). That last rule is where most
uses live in a project that builds its UI in code. A literal can name a
directory or a template (`"res://data/"`, `"res://data/%s.json"`). The
tool counts it as a use of every matching file under it. So "used by"
still shows data that a script loads from a built path. "Used by" counts
test scripts but does not list them.

Skipped: `.godot/`, `addons/`, `builds/`, `shots/`, `bin/`, `obj/`, dot-directories.

## In an agent's instructions

One line does most of the work:

> Read `PROJECT_MAP.md` before grepping for which scene uses a script, who
> connects to a signal, or whether a node path exists. Run `godot-map .`
> after adding or moving scenes or scripts.

A PostToolUse hook on `.gd`/`.tscn` edits can run `godot-map .` so the map
never goes stale mid-task; Kombucha ships one as `tools/seeds/claude-hooks.json`.

## Limits

The GDScript and C# passes use regex, not parsers. They miss or misread
a string literal that looks like a declaration. They also miss or misread
a `preload` built from a variable. The scene reader works at the section
level. When it meets a property value in a shape it does not know, it
keeps the text as it is and ignores it.

`--paths` checks only paths relative to the script's own node. It skips
`other.get_node("X")`. It also skips paths through a node the script
names itself. It reports a node that the game adds at runtime some other
way as missing.

`--problems` learns the engine's signals from a list in `query.py`, not
from the engine. It reports an engine signal that the list lacks as
undeclared. To fix that, add one line to the list. The tool does not
check that literals in test scripts and under `addons/` exist.

Use the map to find your way around. Use the engine, the LSP and the
tests for proof.

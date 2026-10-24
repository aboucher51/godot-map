# godot-map: plan

Status: scaffolded 2026-09-05. Consumed by Kombucha per
`Kombucha/docs/plans/2026-09-05-fast-feedback.md` item 5.

## Why a separate tool

Kombucha owns the files a Godot project carries as a copy (runner, harness,
console). The map is a Python program every project *runs*, not a file it
carries; it has its own tests, its own release cadence, and nothing in it
is project-specific. Kombucha keeps the rule that says to read the map and
the check that keeps it fresh.

The prior art (2026-09-05): graphify builds code graphs from tree-sitter
grammars and has no GDScript grammar, so `.gd` falls to an LLM pass and
`.tscn` is never read. Scene Dependency Viewer and SignalVisualizer show the
same facts inside the editor with no text output. `godot_parser` (PyPI)
parses scenes but rejects real files from every project here.

## Landed 2026-09-05

- Section reader for `.tscn`/`.tres`/`project.godot`; regex reader for
  `.gd`; uid resolution from headers and `.uid` sidecars.
- Model with `used_by` reverse index and `class_name` index.
- Markdown: autoloads, autoload signal wiring (emit/connect by script),
  scenes with connections and small trees, class index, unreferenced
  scripts, compact script table. JSON: everything.
- CLI: write, `--check`, `--stdout`, `--who`, `--no-trees`.
- Tests on a fixture project and a does-not-raise pass over the siblings.

## Assessed 2026-09-05

Run over all twelve siblings: no crash, 100–310 Markdown lines each. Two
things blocked usefulness, found by comparing the map to a grep:
`class_name` references were invisible (the "used by" column was empty for
17/18 class scripts in Kombucha, 91/102 in Monmon, 72/75 in NavalWar, and
`--who` on them exited 1), and nothing consumed the map. Both landed the
same day; the list below is what came of it.

## Landed 2026-09-05, second pass

- **`class_name` and autoload uses.** Every identifier a script names
  outside strings and comments is matched against the class and autoload
  index; a hit is a `used_by` edge. `--who` takes a class or autoload
  name. The "used by" cell caps at six entries.
- **`%UniqueName` paths**, `$"quoted paths"`, `self.get_node`; and
  `other.get_node("X")` is no longer read as a path of this script.
  `unique_name_in_owner` is kept per node.
- **Signal wiring** replaces the autoload-only table: every declared
  signal that something listens to or another script emits, with code
  listeners and scene `[connection]` listeners side by side.
- **`--who --depth N`**: transitive users as an indented tree, each path
  expanded once, capped at 200 lines.
- **`--paths [SCRIPT…]`**: every node path in every attached script
  checked against the scenes it is attached to, through instanced and
  inherited scenes; a path through a node the script names itself
  (`box.name = "Menu"`) is skipped as built at runtime. Exit 1 on a
  missing path. On the siblings: 0 missing, 7 skipped, after those two
  rules removed every false positive.
- **Data files**: `.json`/`.csv`/`.gdshader` listed in the JSON with their
  users; one Markdown line with the count and the directories nothing
  names. `.tres` external resources (a shader, a texture) count as uses.
- **`--mermaid`**: an optional scene-instance graph, off by default.
- **C#**: `csharp.py` reads `.cs` into the same `ScriptInfo`
  (`[GlobalClass]`, base class, `[Signal]`, `GD.Load`, `EmitSignal`,
  `+=`/`Connect`, `GetNode`). No sibling has a `.cs` file; the fixture
  has one.
- **Hook seed** in Kombucha (`tools/seeds/claude-hooks.json`); the
  read-the-map rule in `docs/godot-tooling.md`; `check.sh` fails on a
  stale map when the tool is installed. Maps committed in Kombucha and
  Template.
- **Publish prerequisites**: `uv.lock` tracked, `[project.urls]` and
  classifiers, version 0.2.0, `uv build` clean.

## Landed 2026-09-05, third pass (0.3.0)

- **Problems**: `--problems` and a Markdown section. Every `res://`
  reference the map holds checked against disk (ext_resources, loads,
  literals, autoloads, main scene, `extends "res://…"`); emits and connects
  on a signal the target does not declare (autoloads and classes by
  name, own signals, with an engine-signal list in `query.py`); scene
  `[connection]`s to a method the target script lacks. Zero false
  positives on the twelve siblings after four rules: `obj().sig.connect`
  is an unknown object, a `var` holding a Signal is not an own signal,
  `Autoload.connect(name, callable)` is the Object API, and literals in
  tests or under `addons/` are not judged.
- **Built data paths**: a literal naming a directory (`"res://data/"`,
  or `"res://data/battle"` with no extension, joined at runtime) or a
  template (`"res://data/%s.json"`) is a use of every matching file.
  Monmon's "named by nothing" data files fell from 306 of 313 to 7.
- **Groups**: scene membership, `add_to_group`, and the group queries in
  one table; `groups` in the JSON.
- **`--who --changed`**: users of every file git sees as modified or
  untracked. **`--who Autoload.signal`** and `Class.signal`: emitters,
  code listeners, scene wiring.
- **Tests counted, not listed** in "used by"; a script only tests
  reference is listed as such under "Scripts nothing references".
- **Exported NodePaths** set in scenes join the `--paths` check.

## Next

1. **Maps in the game projects.** Kombucha and Template carry one; each
   game adopts it by running `godot-map .` once and committing both
   files, after which `check.sh` keeps it fresh.
2. **`--problems` in `check.sh`**: a gate beside the map gate, once a few
   projects have run it and the engine-signal list has settled.
3. **`sync-tooling.sh --check`** noting when a project's
   `.claude/settings.json` lacks the hook from `claude-hooks.json`.
4. **Engine class list** for `extends`: today `extends Foo` where `Foo`
   is neither a class_name nor an engine class is not reported, because
   the map has no engine class list. A generated list per Godot minor
   would close it, at the cost of tracking versions.

## Not planned

- Anything that needs the engine or the editor running. The LSP and the
  harness cover that side.
- A full GDScript parser. The facts the map needs are declarations at the
  start of a line; the cost of correctness beyond that is a grammar.

## Landed 2026-10-24 (0.3.1)

- **Git-ignored files are not mapped.** The walk asks
  `git ls-files --others --ignored --exclude-standard --directory` once and
  skips what it lists; outside a repo nothing is skipped. IceEngine's art
  packs (`assets/quaternius/`, git-ignored, imported on one machine) added
  seven data files to the map there, so `--check` read stale in that
  checkout and fresh everywhere else.

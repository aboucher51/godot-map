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

## Next

1. **`--who` with depth**: transitive users ("what breaks if I rename
   this") as an indented tree, capped.
2. **Node-path check**: `godot-map . --paths scripts/hud.gd` — for every
   `$Foo/Bar` in a script, confirm the path exists in every scene the
   script is attached to. Turns the most common Godot runtime error into a
   static one.
3. **Signals in scenes vs code**: `[connection]` blocks and
   `.connect(` calls in one table per signal, so a listener added in code
   and one added in the editor are both visible.
4. **Mermaid**: an optional `--mermaid` scene-instance graph for the
   Markdown, off by default (tokens).
5. **Hook seed**: a PostToolUse snippet (`.gd`/`.tscn` edits →
   `godot-map .`) for Kombucha's `tools/seeds/claude-hooks.json`.
6. **C# projects**: `.cs` with `[GlobalClass]`, `partial class X : Node`,
   `GD.Load<>("res://…")`, `[Signal]` delegates. None of the siblings use
   C# today; low priority.
7. **Publish** to PyPI once two or three projects have committed maps.

## Not planned

- Anything that needs the engine or the editor running. The LSP and the
  harness cover that side.
- A full GDScript parser. The facts the map needs are declarations at the
  start of a line; the cost of correctness beyond that is a grammar.

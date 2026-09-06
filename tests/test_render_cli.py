import os
import shutil

from godot_map.cli import main
from godot_map.render import render_json, render_markdown
from godot_map.scan import scan

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mini")


def test_markdown_sections():
    md = render_markdown(scan(FIXTURE))
    assert md.startswith("# Project map: Mini\n")
    for heading in ("## Autoloads", "## Autoload signal wiring", "## Scenes", "## class_name index",
                    "## Scripts nothing references", "## Scripts"):
        assert heading in md, heading
    assert "| EventBus.score_changed | `scripts/main.gd` | `scripts/main.gd` |" in md
    assert "| EventBus.settings_changed | `scripts/autoloads/game_manager.gd` | — |" in md
    assert "- `Hud/StartButton` pressed → `.`._on_start_pressed()" in md
    assert "  Hud  ← scenes/hud.tscn" in md
    assert "- `scripts/orphan.gd`" in md
    assert "`scripts/enemy.gd`" in md


def test_deterministic():
    a = scan(FIXTURE)
    b = scan(FIXTURE)
    assert render_markdown(a) == render_markdown(b)
    assert render_json(a) == render_json(b)


def test_cli_write_check_and_who(tmp_path, capsys):
    root = tmp_path / "proj"
    shutil.copytree(FIXTURE, root)
    assert main([str(root)]) == 0
    assert (root / "PROJECT_MAP.md").exists()
    assert (root / ".godot-map" / "graph.json").exists()
    assert main([str(root), "--check"]) == 0
    (root / "scenes" / "extra.tscn").write_text('[gd_scene format=3]\n\n[node name="Extra" type="Node"]\n')
    assert main([str(root), "--check"]) == 1
    assert "stale" in capsys.readouterr().out
    assert main([str(root), "--who", "scenes/hud.tscn"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["res://scenes/main.tscn", "res://scripts/main.gd"]
    assert main([str(root), "--who", "res://nothing.gd"]) == 1


def test_cli_no_project(tmp_path):
    assert main([str(tmp_path)]) == 2

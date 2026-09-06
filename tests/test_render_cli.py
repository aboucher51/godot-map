import os
import shutil

from godot_map.cli import main
from godot_map.render import render_json, render_markdown
from godot_map.scan import scan

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mini")


def test_markdown_sections():
    md = render_markdown(scan(FIXTURE))
    assert md.startswith("# Project map: Mini\n")
    for heading in ("## Autoloads", "## Signal wiring", "## Scenes", "## class_name index",
                    "## Scripts nothing references", "## Scripts", "## Data files"):
        assert heading in md, heading
    assert "## Scene graph" not in md
    assert "| EventBus.score_changed | `scripts/autoloads/event_bus.gd` | `scripts/main.gd` | `scripts/main.gd` | — |" in md
    assert "| EventBus.settings_changed | `scripts/autoloads/event_bus.gd` | `scripts/autoloads/game_manager.gd` | — | — |" in md
    assert "| died | `scripts/actor.gd` | `scripts/enemy.gd` | — | `scenes/main.tscn`: Hud → Hud._on_died |" in md
    assert "| round_started |" not in md  # emitted only by its declarer, no listener
    assert "| `scripts/actor.gd` | CharacterBody2D | Actor | resources/stats.tres, scripts/csharp/Bullet.cs, scripts/enemy.gd, scripts/hud.gd |" in md
    assert "3 `.json`/`.csv`/`.gdshader` files" in md and "`data/` (1)" in md
    assert "- `Hud/StartButton` pressed → `.`._on_start_pressed()" in md
    assert "  Hud  ← scenes/hud.tscn" in md
    assert "- `scripts/orphan.gd`" in md
    assert "`scripts/enemy.gd`" in md


def test_mermaid():
    md = render_markdown(scan(FIXTURE), mermaid=True)
    graph = md[md.index("## Scene graph"):]
    assert "```mermaid\ngraph LR" in graph
    assert 'sscenes_main_tscn["scenes/main.tscn"]:::main' in graph
    assert "sscenes_main_tscn --> sscenes_hud_tscn" in graph


def test_users_cell_caps_long_lists():
    from godot_map.render import _users_cell
    assert _users_cell(["autoload:EventBus", "res://a.gd"]) == "EventBus, a.gd"
    cell = _users_cell([f"res://s{i}.gd" for i in range(10)])
    assert cell == "s0.gd, s1.gd, s2.gd, s3.gd, +6 more"


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
    assert out == ["res://scenes/main.tscn", "res://scripts/csharp/Bullet.cs", "res://scripts/main.gd"]
    assert main([str(root), "--who", "res://nothing.gd"]) == 1


def test_cli_who_by_name_and_depth(capsys):
    assert main([FIXTURE, "--who", "GameManager"]) == 0
    assert capsys.readouterr().out.splitlines() == ["autoload:GameManager", "res://scripts/main.gd"]
    assert main([FIXTURE, "--who", "Actor", "--depth", "3"]) == 0
    assert capsys.readouterr().out == """\
res://scripts/actor.gd
  res://resources/stats.tres
  res://scripts/csharp/Bullet.cs
  res://scripts/enemy.gd
    res://scripts/main.gd
      res://scenes/main.tscn
  res://scripts/hud.gd
    res://scenes/hud.tscn
      res://scenes/main.tscn
      res://scripts/csharp/Bullet.cs
      res://scripts/main.gd
    res://scripts/main.gd (see above)
"""


def test_users_tree_cap():
    from godot_map.query import users_tree
    lines = users_tree(scan(FIXTURE), "res://scripts/actor.gd", depth=3, cap=2)
    assert len(lines) == 3 and lines[-1].startswith("... ") and "more" in lines[-1]


def test_cli_paths(capsys):
    # The fixture carries two deliberately wrong paths so the check is seen to fail.
    assert main([FIXTURE, "--paths"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "res://scripts/hud.gd: Missing not in res://scenes/hud.tscn (attached at .)",
        "res://scripts/main.gd: Hud/Nope not in res://scenes/main.tscn (attached at .)",
        "godot-map: 7 node paths checked, 2 missing, 1 built at runtime (skipped)",
    ]
    assert main([FIXTURE, "--paths", "scripts/hud.gd"]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "godot-map: 3 node paths checked, 1 missing"
    assert main([FIXTURE, "--paths", "scripts/orphan.gd"]) == 0  # attached nowhere: nothing to check
    assert main([FIXTURE, "--paths", "scripts/nope.gd"]) == 1


def test_cli_no_project(tmp_path):
    assert main([str(tmp_path)]) == 2

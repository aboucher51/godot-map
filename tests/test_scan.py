import os

import pytest

from godot_map.scan import scan

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mini")


@pytest.fixture(scope="module")
def project():
    return scan(FIXTURE)


def test_project_godot(project):
    assert project.name == "Mini"
    assert project.features == ["4.7", "GL Compatibility"]
    assert list(project.autoloads) == ["EventBus", "GameManager"]
    assert project.autoloads["EventBus"] == "res://scripts/autoloads/event_bus.gd"


def test_main_scene_uid_resolves(project):
    assert project.main_scene == "res://scenes/main.tscn"


def test_skips_addons_and_dot_dirs(project):
    assert not any("addons/" in p or "/.godot/" in p for p in project.scripts)


def test_scene_nodes(project):
    scene = project.scenes["res://scenes/main.tscn"]
    assert scene.root.name == "Main" and scene.root.type == "Node2D"
    assert scene.root.groups == ["state", "settle"]
    assert scene.root.script == "res://scripts/main.gd"
    by_path = {n.path: n for n in scene.nodes}
    assert by_path["Hud"].instance == "res://scenes/hud.tscn"
    assert by_path["Hud"].type is None
    assert by_path["Camera/Deep"].type == "Node"
    assert scene.instances == ["res://scenes/hud.tscn"]
    assert scene.resources == ["res://icon.svg"]


def test_scene_connections(project):
    scene = project.scenes["res://scenes/main.tscn"]
    assert [(c.signal, c.from_node, c.to_node, c.method) for c in scene.connections] == [
        ("pressed", "Hud/StartButton", ".", "_on_start_pressed"),
        ("score_changed", ".", "Hud", "_on_score_changed"),
        ("died", "Hud", "Hud", "_on_died"),
    ]


def test_script_facts(project):
    main = project.scripts["res://scripts/main.gd"]
    assert main.extends == "Node2D"
    assert main.class_name is None  # the one in a comment must not count
    assert main.loads == ["res://scenes/hud.tscn", "res://scripts/enemy.gd"]
    assert main.refs == ["res://data/levels.json"]
    assert main.signals == ["round_started"]
    assert "helper" in main.funcs and "_ready" in main.funcs
    assert "EventBus.score_changed" in main.emits and "round_started" in main.emits
    assert "EventBus.score_changed" in main.connects
    assert main.node_paths == ["Hud/StartButton", "Camera/Deep", "Hud/ScoreLabel", "Hud/Nope", "MenuBox"]
    assert main.named_nodes == {"MenuBox"}

    enemy = project.scripts["res://scripts/enemy.gd"]
    assert enemy.is_tool and enemy.extends == "res://scripts/actor.gd"
    assert enemy.emits == ["died"]


def test_classes_and_used_by(project):
    assert project.classes == {
        "Actor": "res://scripts/actor.gd",
        "Enemy": "res://scripts/enemy.gd",
        "Hud": "res://scripts/hud.gd",
        "Bullet": "res://scripts/csharp/Bullet.cs",
    }
    ub = project.used_by
    assert ub["res://scripts/main.gd"] == ["res://scenes/main.tscn"]
    assert ub["res://scenes/hud.tscn"] == ["res://scenes/main.tscn", "res://scripts/csharp/Bullet.cs", "res://scripts/main.gd"]
    # naming an autoload or a class_name in code is a use of its script
    assert ub["res://scripts/autoloads/event_bus.gd"] == [
        "autoload:EventBus", "res://scripts/autoloads/game_manager.gd", "res://scripts/main.gd", "res://scripts/orphan.gd"]
    assert ub["res://scripts/actor.gd"] == [
        "res://resources/stats.tres", "res://scripts/csharp/Bullet.cs", "res://scripts/enemy.gd", "res://scripts/hud.gd"]
    assert ub["res://scripts/orphan.gd"] == ["res://tests/test_enemy.gd"]  # a test-only reference


def test_unique_names_and_node_paths(project):
    hud = project.scenes["res://scenes/hud.tscn"]
    assert [n.name for n in hud.nodes if n.unique] == ["ScoreLabel"]
    # %Unique counts, "%s" in a format string and a path in a string do not
    assert project.scripts["res://scripts/hud.gd"].node_paths == ["ScoreLabel", "%ScoreLabel", "Missing"]


def test_data_files(project):
    assert project.data == ["res://data/levels.json", "res://data/unused.csv", "res://shaders/glow.gdshader"]
    ub = project.used_by
    # game_manager.gd names "res://data/%s.json": a built path, so every data/*.json is a use
    assert ub["res://data/levels.json"] == [
        "res://scripts/autoloads/game_manager.gd", "res://scripts/csharp/Bullet.cs", "res://scripts/main.gd"]
    assert ub["res://shaders/glow.gdshader"] == ["res://resources/glow_material.tres"]
    assert "res://data/unused.csv" not in ub


def test_csharp_script(project):
    b = project.scripts["res://scripts/csharp/Bullet.cs"]
    assert b.lang == "csharp" and b.class_name == "Bullet" and b.is_global and b.is_tool
    assert b.extends == "Area2D"
    assert b.signals == ["Hit"] and b.emits == ["Hit"] and b.connects == ["BodyEntered", "Hit"]
    assert b.loads == ["res://scenes/hud.tscn"] and b.refs == ["res://data/levels.json"]
    assert b.funcs == ["_Ready", "OnBodyEntered", "OnHit"]
    assert b.node_paths == ["%ScoreLabel"]
    assert project.classes["Bullet"] == "res://scripts/csharp/Bullet.cs"


def test_resource(project):
    res = project.resources["res://resources/stats.tres"]
    assert res.type == "Resource" and res.script == "res://scripts/actor.gd"
    assert project.resources["res://default_bus_layout.tres"].type == "AudioBusLayout"


def test_built_paths():
    from godot_map.scan import _built_path
    assert _built_path("res://data/") == ("res://data/", "")
    assert _built_path("res://data/%s.json") == ("res://data/", ".json")
    assert _built_path("res://data/{id}/stats.tres") == ("res://data/", "/stats.tres")
    assert _built_path("res://data/battle") == ("res://data/battle/", "")  # joined at runtime
    assert _built_path("res://") == (None, "")  # the whole project is not a use
    assert _built_path("res://data/levels.json") == (None, "")


def test_groups(project):
    assert project.groups["state"] == {
        "scenes": {"res://scenes/main.tscn": ["."]},
        "joined_in": [],
        "queried_in": ["res://scripts/hud.gd", "res://scripts/main.gd"],
    }
    assert project.groups["runtime"]["joined_in"] == ["res://scripts/main.gd"]


def test_nodepath_properties(project):
    by_path = {n.path: n for n in project.scenes["res://scenes/main.tscn"].nodes}
    assert by_path["Camera"].node_paths == ["../Sprite"]
    assert by_path["Camera/Deep"].node_paths == ["Nowhere"]


def test_chain(project):
    assert [s.path for s in project.chain("res://scripts/enemy.gd")] == [
        "res://scripts/enemy.gd", "res://scripts/actor.gd"]


def test_signal_problems_edge_cases(tmp_path):
    import shutil
    from godot_map.query import problems
    root = tmp_path / "proj"
    shutil.copytree(FIXTURE, root)
    (root / "scripts" / "edge.gd").write_text("""extends Node
var _sig: Signal
func _ready():
	EventBus.connect("score_changed", _go)  # Object.connect on an autoload: not a signal named EventBus
	_sig.emit()  # a Signal variable
	get_viewport().size_changed.connect(_go)  # unknown object
	var s = load("res://addons/optional/thing.gd")  # optional addon: not judged
func _go(): pass
""")
    found = [str(pr) for pr in problems(scan(str(root))) if "edge.gd" in str(pr)]
    assert found == []


def test_skips_git_ignored_files(tmp_path):
    """A git-ignored file is one checkout's (imported art packs), so the
    committed map must not change when it is there."""
    import shutil
    import subprocess
    root = tmp_path / "proj"
    shutil.copytree(FIXTURE, root)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("assets/packs/*\n!assets/packs/README.md\nlocal.json\n")
    packs = root / "assets" / "packs"
    packs.mkdir(parents=True)
    (packs / "manifest.json").write_text("{}")
    (packs / "README.md").write_text("kept")
    (root / "local.json").write_text("{}")
    (root / "kept.json").write_text("{}")
    data = scan(str(root)).data
    assert "res://assets/packs/manifest.json" not in data
    assert "res://local.json" not in data
    assert "res://kept.json" in data


def test_without_git_nothing_is_ignored(tmp_path):
    import shutil
    root = tmp_path / "proj"
    shutil.copytree(FIXTURE, root)
    (root / ".gitignore").write_text("extra.json\n")
    (root / "extra.json").write_text("{}")
    env_root = str(root)
    # tmp_path is outside any repo, so .gitignore has no say.
    assert "res://extra.json" in scan(env_root).data

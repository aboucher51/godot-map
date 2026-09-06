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
    assert main.node_paths == ["Hud/StartButton", "Camera/Deep"]

    enemy = project.scripts["res://scripts/enemy.gd"]
    assert enemy.is_tool and enemy.extends == "res://scripts/actor.gd"
    assert enemy.emits == ["died"]


def test_classes_and_used_by(project):
    assert project.classes == {
        "Actor": "res://scripts/actor.gd",
        "Enemy": "res://scripts/enemy.gd",
        "Hud": "res://scripts/hud.gd",
    }
    ub = project.used_by
    assert ub["res://scripts/main.gd"] == ["res://scenes/main.tscn"]
    assert ub["res://scenes/hud.tscn"] == ["res://scenes/main.tscn", "res://scripts/main.gd"]
    assert "autoload:EventBus" in ub["res://scripts/autoloads/event_bus.gd"]
    assert ub["res://scripts/actor.gd"] == ["res://scripts/enemy.gd", "res://resources/stats.tres"]
    assert "res://scripts/orphan.gd" not in ub


def test_resource(project):
    res = project.resources["res://resources/stats.tres"]
    assert res.type == "Resource" and res.script == "res://scripts/actor.gd"
    assert project.resources["res://default_bus_layout.tres"].type == "AudioBusLayout"

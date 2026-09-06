extends Node2D
## The main scene. Comments mention class_name Fake and preload("res://nope.gd").

const HudScene := preload("res://scenes/hud.tscn")
var Enemy = load("res://scripts/enemy.gd")

signal round_started(n: int)

func _ready() -> void:
	EventBus.score_changed.connect(_on_score_changed)
	$Hud/StartButton.pressed.connect(_on_start_pressed)
	get_node("Camera/Deep").visible = true
	$Hud/ScoreLabel.text = "0"  # resolves through the instanced scene
	$Hud/Nope.text = "0"  # does not
	var box := VBoxContainer.new()
	box.name = "MenuBox"  # so $MenuBox is built at runtime, not a missing path
	add_child(box)
	$MenuBox.visible = true
	print("#not a comment", "res://data/levels.json")
	GameManager.start()

func _on_start_pressed() -> void:
	round_started.emit(1)
	EventBus.score_changed.emit(10)

func _on_score_changed(_score: int) -> void:
	pass

static func helper() -> String:
	return "res://data/levels.json"

@tool
class_name Enemy
extends "res://scripts/actor.gd"

func _ready() -> void:
	emit_signal("died")

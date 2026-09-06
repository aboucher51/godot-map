extends Node

# Every problem the map reports, in one script: --problems must name all three.
const Gone = preload("res://scripts/gone.gd")

func nothing() -> void:
	EventBus.nope.connect(nothing)
	emit_signal("undeclared")
	EventBus.ready.connect(nothing)  # an engine signal: not a problem

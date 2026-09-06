extends Node

func start() -> void:
	EventBus.settings_changed.emit()

func level_path(name: String) -> String:
	return "res://data/%s.json" % name  # a built path: every data/*.json is a use

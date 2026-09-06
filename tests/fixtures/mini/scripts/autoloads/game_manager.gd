extends Node

func start() -> void:
	EventBus.settings_changed.emit()

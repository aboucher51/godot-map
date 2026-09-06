class_name Hud
extends CanvasLayer

var actor: Actor  # a class_name reference is a use of actor.gd

func _on_score_changed(score: int) -> void:
	$ScoreLabel.text = str(score)
	%ScoreLabel.visible = true
	$Missing.hide()  # deliberately absent from hud.tscn: --paths must report it
	print("%s scored %d" % [name, score])
	get_tree().call_group("state", "reset")

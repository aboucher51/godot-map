class_name Hud
extends CanvasLayer

func _on_score_changed(score: int) -> void:
	$ScoreLabel.text = str(score)

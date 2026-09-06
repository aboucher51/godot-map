using Godot;

// A C# script in the shapes the reader knows. Not attached to a scene.
[GlobalClass]
[Tool]
public partial class Bullet : Area2D
{
    [Signal]
    public delegate void HitEventHandler(Node body);

    private static readonly PackedScene HudScene = GD.Load<PackedScene>("res://scenes/hud.tscn");
    private const string DataPath = "res://data/levels.json";

    public override void _Ready()
    {
        BodyEntered += OnBodyEntered;   /* engine signal */
        Hit += OnHit;
        GetNode<Label>("%ScoreLabel").Text = "0";
        var actor = new Actor(); // a class_name reference
    }

    private void OnBodyEntered(Node body) => EmitSignal(SignalName.Hit, body);

    private void OnHit(Node body) { }
}

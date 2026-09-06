from godot_map import csharp, gdscript


def test_node_paths_forms():
    code = '''
@onready var a = $Foo/Bar
@onready var b = $"Spaced Name/Child"
@onready var c = %Unique
var d = %Unique/Deep
var e = get_node("Camera/Deep")
var f = self.get_node("%Panel")
var g = other.get_node("NotMine")
var h = "%s scored %d" % [name, 3]
var i = x % Y
var j = "$delete"
'''
    assert gdscript.node_paths(code) == [
        "Foo/Bar", "Spaced Name/Child", "%Unique", "%Unique/Deep", "Camera/Deep", "%Panel"]


def test_idents_skip_strings_and_comments():
    info = gdscript.scan_source("res://x.gd", 'var a: Actor = null  # Enemy\nvar s = "Hud"\n')
    assert "Actor" in info.idents and "Enemy" not in info.idents and "Hud" not in info.idents


def test_hash_inside_string_is_not_a_comment():
    info = gdscript.scan_source("res://x.gd", 'var c = Color("#ff0000")\nvar p = preload("res://a.gd")  # x\n')
    assert info.loads == ["res://a.gd"]


def test_csharp_shapes():
    src = '''
using Godot;
/* block
   comment mentioning Nope */
public partial class Foo : Node2D // trailing
{
    [Signal] public delegate void ScoredEventHandler(int n);
    public override void _Ready()
    {
        var s = ResourceLoader.Load<PackedScene>("res://a.tscn");
        Bus.Scored += OnScored;
        count += 1;
        Connect(SignalName.Scored, Callable.From(OnScored));
        hud.EmitSignal("Refresh");
        other.GetNode("X");
        this.GetNode<Node>("Y/Z");
    }
    private void OnScored(int n) { }
}
'''
    i = csharp.scan_source("res://Foo.cs", src)
    assert i.class_name == "Foo" and i.extends == "Node2D" and not i.is_global
    assert i.signals == ["Scored"] and i.loads == ["res://a.tscn"]
    assert i.connects == ["Scored", "Bus.Scored"] and i.emits == ["hud.Refresh"]
    assert i.node_paths == ["Y/Z"] and i.funcs == ["_Ready", "OnScored"]
    assert "Nope" not in i.idents and "PackedScene" in i.idents


def test_connect_on_a_call_result_is_not_an_own_signal():
    info = gdscript.scan_source("res://x.gd", """
signal died
var _resolver: Signal
func _ready():
	get_viewport().size_changed.connect(_on_resize)
	$Button.pressed.connect(_go)
	EventBus.saved.connect(_go)
	died.emit()
	_resolver.emit(1)
	items[0].changed.connect(_go)
""")
    assert info.connects == ["?.size_changed", "Button.pressed", "EventBus.saved", "?.changed"]
    assert info.emits == ["died", "_resolver"]
    assert info.vars == {"_resolver"}

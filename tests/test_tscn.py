from godot_map import tscn

SCENE = '''[gd_scene load_steps=2 format=3 uid="uid://abc"]

[ext_resource type="Script" path="res://scripts/a.gd" id="1_a"]

[node name="Root" type="Node2D" groups=["state", "settle"]]
script = ExtResource("1_a")
list = Array[int]([1,
2])

[node name="Child" parent="." instance=ExtResource("1_a")]
text = "with = sign and [brackets]"

[connection signal="pressed" from="Child" to="." method="_on_pressed"]
'''


def test_headers_and_attrs():
    secs = tscn.parse(SCENE)
    assert [s.name for s in secs] == ["gd_scene", "ext_resource", "node", "node", "connection"]
    assert secs[0].attrs["uid"] == "uid://abc"
    assert secs[0].attrs["format"] == 3
    assert secs[2].attrs["groups"] == ["state", "settle"]
    inst = secs[3].attr_ref("instance")
    assert inst is not None and inst.kind == "Ext" and inst.id == "1_a"


def test_props_and_continuations():
    secs = tscn.parse(SCENE)
    root = secs[2]
    ref = root.prop_ref("script")
    assert isinstance(ref, tscn.Ref) and ref.id == "1_a"
    assert root.props["list"] == "Array[int]([1, 2])"
    assert secs[3].prop_str("text") == "with = sign and [brackets]"


def test_connection_attrs():
    c = tscn.parse(SCENE)[4]
    assert (c.attrs["signal"], c.attrs["from"], c.attrs["to"], c.attrs["method"]) == (
        "pressed", "Child", ".", "_on_pressed")


def test_bus_layout_does_not_raise():
    secs = tscn.parse('[gd_resource type="AudioBusLayout" format=3]\n\n[resource]\nbus/1/name = &"Music"\nbus/1/solo = false\n')
    assert secs[1].prop_str("bus/1/name") == "Music"
    assert tscn.parse_value(secs[1].props["bus/1/solo"]) is False


def test_legacy_numeric_ext_resource():
    secs = tscn.parse('[ext_resource path="res://x.gd" type="Script" id=1]\n[node name="N" type="Node"]\nscript = ExtResource( 1 )\n')
    assert secs[0].attrs["id"] == 1
    ref = secs[1].prop_ref("script")
    assert isinstance(ref, tscn.Ref) and ref.id == "1"

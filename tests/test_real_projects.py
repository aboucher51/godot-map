"""Does-not-raise pass over every sibling Godot project on this machine.

Skipped where ~/godot-projects is absent (CI, another machine).
"""

import glob
import os

import pytest

from godot_map.render import render_json, render_markdown
from godot_map.scan import scan

SIBLINGS = sorted(
    d for d in glob.glob(os.path.expanduser("~/godot-projects/*/"))
    if os.path.exists(os.path.join(d, "project.godot"))
)


@pytest.mark.skipif(not SIBLINGS, reason="no sibling projects here")
@pytest.mark.parametrize("root", SIBLINGS, ids=[os.path.basename(d.rstrip("/")) for d in SIBLINGS])
def test_sibling_scans(root):
    project = scan(root)
    assert project.scripts, root
    md = render_markdown(project)
    js = render_json(project)
    assert md.startswith("# Project map: ")
    assert js.startswith("{")

"""Runs the editor's real highlight functions under node."""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

SOURCE = (pathlib.Path(__file__).parents[1] / "editor" / "index.html").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def _function(name):
    start = SOURCE.index("function %s(" % name)
    depth, i = 0, SOURCE.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(SOURCE[i], 0)
        i += 1
        if depth == 0:
            return SOURCE[start:i]


def _highlight(glossary, text):
    script = "const state={};%s\nbuildGlossIndex(%s);console.log(highlightGloss(%s));" % (
        "\n".join(_function(n) for n in ("esc", "highlightGloss", "buildGlossIndex")),
        json.dumps(glossary), json.dumps(text))
    return subprocess.run(["node", "-e", script], capture_output=True, text=True,
                          check=True).stdout.strip()


def test_a_hostile_glossary_cannot_leave_the_title_attribute():
    html = _highlight({"terms": {"x": {"translit": "sabr",
                                       "english": 'patience" onmouseover="alert(1)'}}},
                      "on patience and sabr")
    assert "&quot; onmouseover=&quot;" in html
    assert re.search(r'<mark title="[^"]*"\s+on', html) is None


def test_a_term_inside_an_earlier_tip_does_not_corrupt_the_markup():
    html = _highlight({"terms": {"a": {"translit": "tawhid", "english": "the Oneness of Allah"},
                                 "b": {"translit": "ilah", "english": "Allah"}}},
                      "the Oneness of Allah and Allah")
    assert html == ('<mark title="a — tawhid">the Oneness of Allah</mark> and '
                    '<mark title="b — ilah">Allah</mark>')


def test_cue_text_stays_escaped():
    html = _highlight({"terms": {"a": {"translit": "sabr", "english": "patience"}}},
                      "<img src=x> & patience")
    assert html.startswith("&lt;img src=x&gt; &amp; <mark")


def test_no_term_is_dropped_however_large_the_glossary():
    terms = {"k%d" % i: {"translit": "term%dx" % i, "english": "longer rendering %d" % i}
             for i in range(1200)}
    terms["short"] = {"translit": "sabr", "english": "patience"}
    assert _highlight({"terms": terms}, "patience").count("<mark") == 1

"""`${S}` reads S into a new string, and the string goes wherever the template goes.

A template literal is string concatenation with different punctuation: `` `${a}-${b}` `` is
`a + "-" + b`, and the reader already lets a value flow on through arithmetic. It had no
row for the template, so a state interpolated anywhere went silent, eleven sites on an Astro
site audited on 2026-11-12. The substitution and the template string are both declared
pass-through: the derived value flows on, and whatever then receives it decides the reading.

That is a reading, not a clearance. Returned, the string is output. Compared, it is a split.
Handed to a function nobody modeled, it is that callee's silence, which is the honest place
for it to stop: a string derived from the state can still decide something in there.
"""

from __future__ import annotations

import subprocess

import pytest


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _finding(tmp_path, name: str, source: str, lang: str) -> dict:
    from l1_analyzer import state_bounds

    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    [finding] = [f for f in state_bounds.classify(tmp_path, lang)["findings"] if f["state"] == "S"]
    return finding


_LANGS = [("typescript", "m.ts"), ("javascript", "m.js")]


@pytest.mark.parametrize("lang,name", _LANGS)
def test_an_interpolated_value_that_is_returned_is_output(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export let S = 'a';\nexport function f() { return `hello ${S}`; }\n", lang)
    assert (found["verdict"], found["silence"], found["drives_decision"]) == ("neutral", "", False)


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_member_read_into_a_template_flows_the_same_way(tmp_path, lang, name):
    found = _finding(tmp_path, name, (
        "export let S = { path: '/' };\n"
        "export function f() { return `${S.path}?x=1`; }\n"), lang)
    assert (found["verdict"], found["silence"]) == ("neutral", "")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_template_compared_is_a_split(tmp_path, lang, name):
    found = _finding(tmp_path, name, (
        "export let S = 'a';\n"
        "export function f() { if (`${S}-x` === 'b-x') { return 1; } return 0; }\n"), lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_template_handed_to_an_unknown_callee_stops_there(tmp_path, lang, name):
    """Not cleared: the callee can decide on the string. The silence moves from a construct
    nobody taught the reader to the callee nobody modeled."""
    found = _finding(tmp_path, name,
                     "export let S = 'a';\nexport function f() { send(`${S}`); }\n", lang)
    assert (found["verdict"], found["silence"]) == ("unresolved", "unmodeled_callee")

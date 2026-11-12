"""`c ? S : T` evaluates to S itself, so S flows on as the ternary's value.

The reader had a row for a ternary's CONDITION, the two-class split every truth test makes,
and none for the two values it chooses between. A state in either arm stopped the reading
there: eight sites on an Astro site audited on 2026-11-12, counting the ones held up behind
a template literal until the template was read.

The arm is the same object, not a copy, so it flows on exactly as a parenthesis does, and
whatever receives the ternary's value decides the reading. The condition keeps its own row:
a state there decides which arm runs, and that is a split, never a pass-through.
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
def test_a_chosen_value_that_is_returned_is_output(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export let S = 'a';\nexport function f(c) { return c ? S : 'b'; }\n", lang)
    assert (found["verdict"], found["silence"], found["drives_decision"]) == ("neutral", "", False)


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_chosen_value_keeps_its_reading_downstream(tmp_path, lang, name):
    """Through the arm and on to a keyed read with an open key: unbounded, as it would be
    without the ternary in the way."""
    found = _finding(tmp_path, name, (
        "export const S = {};\n"
        "export function put(k) { S[k] = 1; }\n"
        "export function get(c, k) { if ((c ? S : {})[k]) { return 1; } return 0; }\n"), lang)
    assert found["verdict"] == "promiscuous"


@pytest.mark.parametrize("lang,name", _LANGS)
def test_the_condition_is_still_a_split(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export let S = false;\nexport function f() { return S ? 1 : 0; }\n", lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)

"""`for (const x of S)` walks every cell of S, and the reader had no row for it.

Go's `range` and Rust's `for` have read this way since the loop row was written: walking a
collection reads every cell it holds, so the reach is the cell set and nothing wider. Finite
when the state's writes bound its cells, unbounded when nothing does. JavaScript and
TypeScript spell both loops as one node, `for_in_statement`, with the walked value in its
`right` field whether the operator is `of` (values) or `in` (keys); a key walk reads the key
set, which is the same cell set. The reader declared no row, so the plainest loop the
language has came back as a construct nobody had taught it: four states on an Astro site
audited on 2026-11-12.

Read from the `right` field and never from the node type alone, so a state named in the
loop's BODY is not taken for the collection being walked.
"""

from __future__ import annotations

import subprocess

import pytest


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _findings(tmp_path, name: str, source: str, lang: str) -> dict[str, dict]:
    from l1_analyzer import state_bounds

    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return {f["state"]: f for f in state_bounds.classify(tmp_path, lang)["findings"]}


_LANGS = [("typescript", "m.ts"), ("javascript", "m.js")]


@pytest.mark.parametrize("lang,name", _LANGS)
def test_walking_a_collection_nothing_bounds_is_unbounded(tmp_path, lang, name):
    """Read correctly, this is a finding: a list anyone may push to, walked, and tested.
    The state also sits in a condition, so the carried-value rule, which clears a state
    that appears in no test expression, does not apply."""
    found = _findings(tmp_path, name, (
        "export const SLOTS = [];\n"
        "export function add(s) { SLOTS.push(s); }\n"
        "export function full() { if (SLOTS.length > 9) { return 1; } return 0; }\n"
        "export function any() { for (const s of SLOTS) { if (s) { return 1; } } return 0; }\n"), lang)
    assert (found["SLOTS"]["verdict"], found["SLOTS"]["silence"]) == ("promiscuous", "")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_walking_keys_whose_writes_are_bounded_is_finite(tmp_path, lang, name):
    """Two literal-keyed stores bound the cells at two, so walking the keys reads three
    classes: each key, and none."""
    found = _findings(tmp_path, name, (
        "export const FLAGS = {};\n"
        "export function on() { FLAGS['a'] = 1; FLAGS['b'] = 1; }\n"
        "export function keys() { const out = []; for (const k in FLAGS) { out.push(k); } return out; }\n"), lang)
    assert (found["FLAGS"]["verdict"], found["FLAGS"]["silence"]) == ("neutral", "")
    assert found["FLAGS"]["partition"]["classes"] == 3


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_state_in_the_loop_body_is_not_the_collection_walked(tmp_path, lang, name):
    found = _findings(tmp_path, name, (
        "export let LAST = null;\n"
        "export function scan(items) { for (const x of items) { LAST = x; } return LAST; }\n"), lang)
    assert found["LAST"]["silence"] != "unmodeled_construct"

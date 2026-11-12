"""`() => S.length + 1` returns `S.length + 1`, and the reader had no row for that.

An arrow function whose body is an expression returns it: `x => x * 2` and
`x => { return x * 2; }` are the same program. The second reads as output, the verdict a
`return` gets: the value is handed to the caller and reaches no decision here. The first had
no row, so a state read in a concise arrow went silent. Five states on an Astro site audited
on 2026-11-12, `() => controller.abort()` and `() => ({ ok, ms: Date.now() - t0 })`
among them.

It is the row C# has had for an expression-bodied member since its spelling was found to read
differently from the `return` it means. Not a new clearing: the two spellings now agree. Only
the `body` field: a single-parameter arrow hangs its parameter off the same node, and that is
a binding, not a returned value.
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

    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    [finding] = [f for f in state_bounds.classify(tmp_path, lang)["findings"] if f["state"] == "S"]
    return finding


_LANGS = [("typescript", "m.ts"), ("javascript", "m.js")]


@pytest.mark.parametrize("lang,name", _LANGS)
@pytest.mark.parametrize("arrow", [
    "export const f = () => S.length + 1;",
    "export const f = () => ({ size: S.length });",
])
def test_the_two_spellings_of_a_return_read_the_same(tmp_path, lang, name, arrow):
    concise = _finding(tmp_path / "concise", name, "export let S = [1];\n" + arrow + "\n", lang)
    braced_source = arrow.replace("=> ", "=> { return ").rstrip(";") + "; };"
    braced = _finding(tmp_path / "braced", name, "export let S = [1];\n" + braced_source + "\n", lang)
    assert (concise["verdict"], concise["silence"]) == (braced["verdict"], braced["silence"]) == ("neutral", "")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_returned_value_that_decides_downstream_still_decides(tmp_path, lang, name):
    """Through the arrow's return and nothing else: a split inside the body is still read."""
    found = _finding(tmp_path, name,
                     "export let S = 0;\nexport const f = () => (S > 3 ? 'many' : 'few');\n", lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)

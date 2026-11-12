"""`S.attr = v` writes into S, and the reader read it as a construct it had no rule for.

`S[k] = v` has always been a write. `S.attr = v` is the same operation with a fixed key, and
in JavaScript it is literally `S["attr"] = v`. The member-access row followed `S.attr` on as a
value and the assignment it was the target of had no row for its left side, so the state
went silent: `anim.onfinish = () => ...`, `pending.length = 0`, `options.proxy =
{...}`, six sites on an Astro site audited on 2026-11-12. Python's `S.attr = v` read the same
way.

A write is not a decision, so on its own it costs no test. A conditional store
`S.attr ??= v` also reads whether the property is there, which is the presence split the
same row already gives `S[k] ??= v`.
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


@pytest.mark.parametrize("lang,name,source", [
    ("typescript", "m.ts", "export const S: any = {};\nexport function f(v) { S.attr = v; }\n"),
    ("javascript", "m.js", "export const S = {};\nexport function f(v) { S.attr = v; }\n"),
    ("javascript", "m.js", "export const S = [];\nexport function reset() { S.length = 0; }\n"),
    ("python", "m.py", "S = {}\n\ndef f(v):\n    S.attr = v\n"),
])
def test_a_stored_property_is_a_write(tmp_path, lang, name, source):
    found = _finding(tmp_path, name, source, lang)
    assert (found["verdict"], found["silence"], found["drives_decision"]) == ("neutral", "", False)


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_a_conditional_store_reads_presence_first(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export const S = {};\nexport function f() { S.ready ??= true; }\n", lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)

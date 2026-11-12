"""`{ S }` is `{ S: S }`, and the reader saw the second and not the first.

A shorthand property names a variable and reads it, exactly as the long form does, but the
grammar spells it as a `shorthand_property_identifier` rather than an `identifier`. The
reference collector matched identifiers only, so a shorthand reference was never collected at
all. The state then looked as if it had fewer uses than it does: written somewhere, read
nowhere, and the write-only rule cleared it to neutral. The same program written the long way
reads as a mutable alias. Spelling it shorter bought a cleaner result, which is the one thing
this measure must never sell.

Found on 2026-11-12 while teaching the reader object literals. The destructuring form,
`const { S } = o`, is a different node, `shorthand_property_identifier_pattern`: it binds a
new name and is not a reference to the state, and it stays out.
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
_PROGRAM = ("export const S = {{}};\n"
            "export function put(k) {{ S[k] = 1; }}\n"
            "export function f(k) {{ const o = {literal}; if (o.S[k]) {{ return 1; }} return 0; }}\n")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_the_short_and_long_spellings_read_the_same(tmp_path, lang, name):
    short = _finding(tmp_path / "short", name, _PROGRAM.format(literal="{ S }"), lang)
    long = _finding(tmp_path / "long", name, _PROGRAM.format(literal="{ S: S }"), lang)
    assert (short["verdict"], short["silence"]) == (long["verdict"], long["silence"])
    assert short["verdict"] != "neutral"


@pytest.mark.parametrize("lang,name", _LANGS)
def test_destructuring_binds_a_new_name_and_is_not_a_reference(tmp_path, lang, name):
    found = _finding(tmp_path, name, (
        "export let S = 1;\n"
        "export function f(o) { const { S } = o; return S; }\n"), lang)
    assert (found["verdict"], found["silence"]) == ("neutral", "")

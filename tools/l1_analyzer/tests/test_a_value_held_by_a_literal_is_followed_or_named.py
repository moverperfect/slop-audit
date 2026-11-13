"""A value put into an object or array literal is held by it, and the literal is followed.

`{ ms: Date.now() - t0 }`, `[startTime, endTime]`, `{ ...DEFAULTS }`: the commonest
place a JavaScript value goes after a variable is a literal, and the reader had no row for
any of them. They were 40 of the 54 constructs left on an Astro site audited on 2026-11-12.

A literal does not copy a value. `{ a: S }` holds a REFERENCE to S, so whatever reaches the
literal can reach S, and a write through `o.a` writes S. A spread is a shallow copy, and its
elements are the same objects. So the reading continues from the literal, and where the
literal then goes decides it, by the same rows the value itself would meet there:

    returned, discarded or stored          output, as `return S` is
    handed to a function                   that call's reading, as `f(S)` is
    a method taken off it                  the chain rule: `[x, y].some(isNaN)` in a condition
    indexed                                the element chosen flows on; the index decides
                                           which cell of the LITERAL, not of the state
    bound to a name inside a function      silent, as a mutable alias: the state is now
    or walked by a loop                    `local.a` or the loop variable, which this walk
                                           does not follow, and a write through it would
                                           reach the state unseen

The last row is the one that keeps this honest. Following the local would charge the state
with every decision taken on the container's other fields, and an open-key read of the
container would be read as one of the state: an accusation it did not earn.
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
_HEAD = "export let S = [1];\n"


@pytest.mark.parametrize("lang,name", _LANGS)
@pytest.mark.parametrize("body", [
    "export function f() { return { a: S }; }",
    "export function f() { return { total: S.length + 1 }; }",
    "export function f() { return [0, S]; }",
    "export function f() { return [...S, 2]; }",
    "export function f() { return { ...S }; }",
    "export function f(k) { return ({ a: S, b: [] })[k]; }",
])
def test_a_literal_that_is_returned_is_output(tmp_path, lang, name, body):
    found = _finding(tmp_path, name, _HEAD + body + "\n", lang)
    assert (found["verdict"], found["silence"], found["drives_decision"]) == ("neutral", "", False)


@pytest.mark.parametrize("lang,name", _LANGS)
@pytest.mark.parametrize("body", [
    "export function f() { send({ a: S }); }",
    "export function f() { send([S]); }",
    "export function f() { send(...S); }",
])
def test_a_literal_handed_to_an_unknown_callee_stops_there(tmp_path, lang, name, body):
    # `send` is the project's own, imported from a file this reader cannot open. Left
    # undeclared, an ES module could only be calling a platform global, the adopter's boundary.
    found = _finding(tmp_path, name, "import { send } from './transport';\n" + _HEAD + body + "\n", lang)
    assert (found["verdict"], found["silence"]) == ("unresolved", "unmodeled_callee")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_method_on_the_literal_in_a_condition_is_a_split(tmp_path, lang, name):
    found = _finding(tmp_path, name, _HEAD + (
        "export function f(t) { if ([S, t].some(Boolean)) { return 1; } return 0; }\n"), lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)


@pytest.mark.parametrize("lang,name", _LANGS)
@pytest.mark.parametrize("body", [
    "export function f() { const o = { a: S }; o.a.push(2); return 1; }",
    "export function f() { const o = [S]; return o; }",
    "export function f() { for (const x of [S, []]) { x.push(1); } }",
])
def test_a_literal_under_another_name_is_a_mutable_alias(tmp_path, lang, name, body):
    found = _finding(tmp_path, name, _HEAD + body + "\n", lang)
    assert (found["verdict"], found["silence"]) == ("unresolved", "mutable_alias")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_an_open_key_on_the_literal_is_not_an_open_key_on_the_state(tmp_path, lang, name):
    """The open key picks a cell of the literal. S is one candidate, and it flows on into
    the comparison like any chosen value: a split, not an unbounded read of S."""
    found = _finding(tmp_path, name, _HEAD + (
        "export function f(k) { if (({ a: S, b: 0 })[k] === 0) { return 1; } return 0; }\n"), lang)
    assert found["verdict"] == "neutral"

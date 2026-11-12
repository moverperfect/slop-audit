"""`await x` and `x satisfies T` hand x on, and the reader stopped at both.

`await` resolves a promise to the value it holds and is a pass-through in Python's and Rust's
rows already; JavaScript's had none, so `await env.KV.put(k, v)` as a statement came back as
a construct nobody had taught the reader. `satisfies` checks a value against a type and
leaves it exactly as it was, which is why the state enumerator already looks through it;
the flow walker did not, so `{ exclude: patterns } satisfies Config` stopped there. One site
each on an Astro site audited on 2026-11-12.

Both are pass-through and identity-preserving, so `satisfies` joins TypeScript's
value-wrapper row as well: a literal under it is still that literal.
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


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_an_awaited_value_flows_on(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export let S = Promise.resolve(1);\nexport async function f() { return await S; }\n", lang)
    assert (found["verdict"], found["silence"]) == ("neutral", "")


def test_a_value_checked_with_satisfies_flows_on(tmp_path):
    found = _finding(tmp_path, "m.ts", (
        "export let S = ['a'];\n"
        "export function f() { return { exclude: S } satisfies { exclude: string[] }; }\n"), "typescript")
    assert (found["verdict"], found["silence"]) == ("neutral", "")

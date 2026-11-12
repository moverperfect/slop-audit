"""`String(x)`, `encodeURI(x)` and `clearTimeout(t)` are the language's own functions, and
the reader treated each as a callee nobody had modeled.

Python's row names the builtins whose result flows on, `len`, `bool`, `abs` and the rest, and
JavaScript declared none, so every conversion was silence charged to us. A conversion reads
its argument and returns a new value; it writes nothing, so the value flows on through the
call and whatever receives it decides. Strictly: Python files `str` as an effect and stops
there, and following the result instead can only find more decisions, never fewer.

`clearTimeout(t)` and `clearInterval(t)` cancel the timer a handle names and return nothing,
which is what the writing-builtins row already says of Go's `delete(m, k)`: a write, and no
decision. Six sites on an Astro site audited on 2026-11-12.
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
@pytest.mark.parametrize("call", ["String(S)", "Number(S)", "encodeURI(S)", "parseInt(S, 10)"])
def test_a_conversion_hands_its_result_on(tmp_path, lang, name, call):
    found = _finding(tmp_path, name, f"export let S = '1';\nexport function f() {{ return {call}; }}\n", lang)
    assert (found["verdict"], found["silence"]) == ("neutral", "")


@pytest.mark.parametrize("lang,name", _LANGS)
def test_a_converted_value_that_decides_still_decides(tmp_path, lang, name):
    found = _finding(tmp_path, name,
                     "export let S = 1;\nexport function f() { if (String(S) === '1') { return 1; } return 0; }\n", lang)
    assert (found["verdict"], found["drives_decision"]) == ("neutral", True)


@pytest.mark.parametrize("lang,name", _LANGS)
def test_cancelling_a_timer_is_a_write(tmp_path, lang, name):
    found = _finding(tmp_path, name, (
        "export let S = undefined;\n"
        "export function start(f) { S = setTimeout(f, 10); }\n"
        "export function stop() { clearTimeout(S); }\n"), lang)
    assert found["silence"] != "unmodeled_callee"

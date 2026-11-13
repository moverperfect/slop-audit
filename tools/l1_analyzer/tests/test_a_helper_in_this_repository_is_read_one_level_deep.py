"""A state handed to one of this repository's own functions is read inside that function.

`daysBetween(start)`, `renderList(entries)`, `buildBreadcrumbs(ROOT, ...)`:
the commonest thing a value does in a TypeScript codebase is go into a helper written in the
same codebase, and every one of those was `unmodeled_callee`, a name the reader could have
read and had not. 38 of the 58 callee silences on an Astro site audited on 2026-11-12.

The helper is read ONE LEVEL deep. A plain-name callee declared in the same file, or imported
by a path or a `tsconfig` alias that resolves to a file in this repository, is opened, the
parameter the state was passed as is found, and that parameter's references are read with the
same rows the state's own references get. What the body does with it is what the call does
with the state: a write is a write, an open-key lookup is unbounded, and a value the helper
hands back flows on from the call, as it does through a bounded builtin.

Everything that would need a second hop or a guess stays silent, as it was: a call inside the
helper to another plain name, an import that resolves to nothing, a re-export, a parameter
taken apart by destructuring or gathered by a rest, and a literal or a spread passed as the
argument, which the helper would hold under a name of its own.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _finding(root: Path, files: dict[str, str]) -> dict:
    from l1_analyzer import state_bounds

    files = {"package.json": json.dumps({"name": "site"}), **files}
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    [finding] = [f for f in state_bounds.classify(root, "typescript")["findings"] if f["state"] == "S"]
    return finding


_STATE = "export let S = 1;\nexport function set(v) { S = v; }\n"


def test_a_same_file_helper_s_returned_value_flows_on_into_the_caller_s_split(tmp_path):
    found = _finding(tmp_path, {"src/m.ts": _STATE + (
        "function inc(x) { return x + 1; }\n"
        "export function f() { if (inc(S) > 3) { return 1; } return 0; }\n")})
    assert (found["verdict"], found["silence"], found["drives_decision"]) == ("neutral", "", True)


def test_an_imported_helper_that_looks_up_an_open_key_makes_the_state_unbounded(tmp_path):
    """Read correctly through the helper, this is a finding."""
    found = _finding(tmp_path, {
        "src/pick.ts": "export function pick(table, key) { if (table[key]) { return 1; } return 0; }\n",
        "src/m.ts": ("import { pick } from './pick';\n"
                     "export const S = {};\nexport function put(k) { S[k] = 1; }\n"
                     "export function f(k) { return pick(S, k); }\n")})
    assert found["verdict"] == "promiscuous"


def test_a_helper_reached_through_a_tsconfig_alias_is_read(tmp_path):
    found = _finding(tmp_path, {
        "tsconfig.json": json.dumps({"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}),
        "src/lib/text.ts": "export const shout = (s: string) => s.toUpperCase();\n",
        "src/m.ts": "import { shout } from '@/lib/text';\n" + _STATE + (
            "export function f() { return shout(S); }\n")})
    assert (found["verdict"], found["silence"]) == ("neutral", "")


def test_a_helper_that_writes_the_parameter_writes_the_state(tmp_path):
    found = _finding(tmp_path, {"src/m.ts": (
        "export const S = new Set();\n"
        "function remember(seen, v) { seen.add(v); }\n"
        "export function f(v) { remember(S, v); }\n")})
    assert (found["verdict"], found["silence"]) == ("neutral", "")


@pytest.mark.parametrize("files", [
    # A second hop: the helper hands the parameter to another plain name.
    {"src/m.ts": _STATE + "function a(x) { return b(x); }\nfunction b(y) { return y; }\n"
                          "export function f() { return a(S); }\n"},
    # A re-export the reader does not follow.
    {"src/h.ts": "export function h(x) { return x; }\n",
     "src/index.ts": "export { h } from './h';\n",
     "src/m.ts": "import { h } from './index';\n" + _STATE + "export function f() { return h(S); }\n"},
    # A destructured parameter, and a rest parameter.
    {"src/m.ts": _STATE + "function d({ a }) { return a; }\nexport function f() { return d(S); }\n"},
    {"src/m.ts": _STATE + "function r(...xs) { return xs; }\nexport function f() { return r(S); }\n"},
    # A literal passed as the argument: the helper would hold it under its own name.
    {"src/m.ts": _STATE + "function w(o) { return o; }\nexport function f() { return w({ s: S }); }\n"},
])
def test_what_would_need_a_second_hop_or_a_guess_stays_silent(tmp_path, files):
    found = _finding(tmp_path, files)
    assert (found["verdict"], found["silence"]) == ("unresolved", "unmodeled_callee")

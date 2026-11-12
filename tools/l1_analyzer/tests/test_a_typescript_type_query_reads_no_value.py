"""`typeof X` in a type position is the compiler asking for X's type, and the program never
runs it.

TypeScript writes a type derived from a constant as `(typeof SIZES)[number]`. That
`typeof` is a type query: it is erased before the program exists, so it cannot read the
value, write it, or decide anything at run time. The reader had no row for it, and one
reference with no row makes the whole state unresolved, so a constant table that a type is
derived from went silent however it was used. Five states on an Astro site audited on
2026-11-12 were silent for this alone.

It is the row C# and C already have for `sizeof` and `typeof`: the operand is not read.
The runtime `typeof x === "string"` is a different node, a unary operator over a value, and
keeps the reading it always had.
"""

from __future__ import annotations

import subprocess


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _finding(tmp_path, source: str) -> dict:
    from l1_analyzer import state_bounds

    (tmp_path / "m.ts").write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    [finding] = state_bounds.classify(tmp_path, "typescript")["findings"]
    return finding


def test_a_type_derived_from_a_constant_does_not_silence_it(tmp_path):
    finding = _finding(tmp_path, (
        "export const SIZES = ['sm', 'md'];\n"
        "export type Size = (typeof SIZES)[number];\n"
        "export function all() { return SIZES; }\n"))
    assert (finding["verdict"], finding["silence"]) == ("neutral", "")


def test_the_type_query_hides_nothing_the_value_does(tmp_path):
    """The other direction. Read correctly, the type query is not a decision, so whatever
    the value's own references decide is what the state is: here an open key, which is
    unbounded. It used to be unresolved, because the silent reference came first."""
    finding = _finding(tmp_path, (
        "export const TABLE: Record<string, number> = {};\n"
        "export type Key = keyof typeof TABLE;\n"
        "export function put(k: string) { TABLE[k] = 1; }\n"
        "export function has(k: string) { if (TABLE[k]) { return 1; } return 0; }\n"))
    assert finding["verdict"] == "promiscuous"


def test_a_runtime_typeof_is_still_a_read(tmp_path):
    """`typeof S === "string"` compares the value's runtime type: a two-class split."""
    finding = _finding(tmp_path, (
        "export let S: unknown = 1;\n"
        "export function f() { if (typeof S === 'string') { return 1; } return 0; }\n"))
    assert finding["verdict"] == "neutral" and finding["drives_decision"]

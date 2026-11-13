"""A state is a declared constant only when ITS OWN declaration says so.

The rule that settles `private static final int X = 11` at one value climbed four ancestors
from EVERY reference to the state and asked two questions of whatever it reached: does any
child, or any child's child, carry the language's constant modifier, and is every declaration
underneath a literal. A reference sitting in a block that also held an unrelated
`final int n = 1` reached that block, found the neighbour's `final`, found only literal
declarations, and settled the state as a constant: neutral, one class, and no reference of it
ever read. Mutable state, read as a constant because of a different variable on the line above.

Found on 2026-11-12 in TypeScript, `for (const k in FLAGS)` beside `let n = 0`, and it
reproduces in every family the rule serves: Java's `final`, C#'s `const`, C's `const`,
Rust's `const` and TypeScript's. Go's constants are not binding sites the rule reaches, so Go
was never settled by it and is not touched.

Now the rule starts at the state's binding site and judges only the declaration that binds it,
by the per-language `declaration_types` row. True constants in the three languages that have
always been settled stay settled.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds

# A mutable state, compared against an unrelated literal constant declared beside the
# comparison. Read correctly it drives a decision; settled as a constant it drives nothing.
_NEIGHBOURED = {
    "typescript": ("m.ts", "C", (
        "export const C = { ready: false };\n"
        "export function arm() { C.ready = true; }\n"
        "export function f() { if (C.ready) { return 1; } return 0; }\n"
        "export function g() { const n = 0; return C; }\n")),
    "java": ("A.java", "count", (
        "class A {\n  private static int count = 0;\n"
        "  int f() { final int n = 1; if (count > n) { return 1; } count = count + 1; return 0; }\n}\n")),
    "csharp": ("a.cs", "count", (
        "class A {\n  private static int count = 0;\n"
        "  int F() { const int n = 1; if (count > n) { return 1; } count = count + 1; return 0; }\n}\n")),
    "c": ("m.c", "count", (
        "static int count = 0;\n"
        "int f(void) { const int n = 1; if (count > n) { return 1; } count = count + 1; return 0; }\n")),
    "rust": ("m.rs", "COUNT", (
        "static mut COUNT: i32 = 0;\n"
        "fn f() -> i32 { const N: i32 = 1; let x = 2;"
        " unsafe { if COUNT > N + x { return 1; } COUNT += 1; } 0 }\n")),
}

_TRUE_CONSTANTS = {
    "java": ("A.java", "PEEKED", (
        "class A {\n  private static final int PEEKED = 11;\n"
        "  int q(int p) { switch (p) { case PEEKED: return 1; default: return 0; } }\n}\n")),
    "csharp": ("a.cs", "Peeked", (
        "class A {\n  private const int Peeked = 11;\n"
        "  int Q(int p) { switch (p) { case Peeked: return 1; default: return 0; } }\n}\n")),
    "c": ("m.c", "LIMIT", "static const int LIMIT = 3;\nint f(int p) { if (p > LIMIT) { return 1; } return 0; }\n"),
}


def _finding(lang: str, filename: str, state: str, source: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        found = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"].endswith(state)]
        assert found, f"{state} should be enumerated as state"
        return found[0]


@pytest.mark.parametrize("lang", sorted(_NEIGHBOURED))
def test_a_neighbour_s_constant_does_not_settle_the_state(lang):
    filename, state, source = _NEIGHBOURED[lang]
    found = _finding(lang, filename, state, source)
    assert found["drives_decision"], f"{lang}: {state} was settled as a constant by a neighbour"


@pytest.mark.parametrize("lang", sorted(_TRUE_CONSTANTS))
def test_a_true_constant_is_still_settled(lang):
    filename, state, source = _TRUE_CONSTANTS[lang]
    found = _finding(lang, filename, state, source)
    assert (found["verdict"], found["partition"]["classes"], found["drives_decision"]) == ("neutral", 1, False)

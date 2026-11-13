"""A collection walked by a loop whose body branches on each element drives a decision.

The carried-value rule clears a state none of whose references sits in a test expression:
unbounded data that never reaches a branch does not bound testability. A loop over the state
puts no reference to it in a test. The loop's body does, through the element:

    for (const { pattern, label } of PATTERNS) {
      if (pattern.test(path)) return label;
    }

Every element is tested, and which section comes back depends on what the table holds. The rule
read the state's own references, found none in a test, and cleared it. On an Astro site audited
on 2026-11-12, three such tables were read as unbounded and then cleared to neutral.

Now a state walked by a loop, directly or through a method chain on it (`self.items.iter()`),
whose bound element appears in a test expression in the loop's body counts as driving a
decision. It applies in every language with a loop row (Go's `range`, Rust's `for`, and
JavaScript's `for...of` and `for...in`), and a body that tests nothing still clears.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds

_TESTED = {
    "typescript": ("m.ts", "S", (
        "export const S = [];\n"
        "export function add(x) { S.push(x); }\n"
        "export function f() { for (const { a } of S) { if (a.ok) { return 1; } } return 0; }\n")),
    "javascript": ("m.js", "S", (
        "export const S = [];\n"
        "export function add(x) { S.push(x); }\n"
        "export function f() { for (const x of S) { if (x) { return 1; } } return 0; }\n")),
    "go": ("m.go", "items", (
        "package m\n\ntype P struct { items []int }\n\n"
        "func (p *P) Add(x int) { p.items = append(p.items, x) }\n\n"
        "func (p *P) Any() int {\n\tfor _, v := range p.items {\n\t\tif v > 1 {\n\t\t\treturn 1\n\t\t}\n\t}\n\treturn 0\n}\n")),
    "rust": ("m.rs", "items", (
        "struct P { items: Vec<i32> }\n"
        "impl P {\n"
        "    fn add(&mut self, x: i32) { self.items.push(x); }\n"
        "    fn any(&self) -> i32 { for x in self.items.iter() { if *x > 1 { return 1; } } 0 }\n"
        "}\n")),
}

_UNTESTED = {
    "typescript": ("m.ts", "S", (
        "export const S = [];\n"
        "export function add(x) { S.push(x); }\n"
        "export function f() { let n = 0; for (const x of S) { n += x; } return n; }\n")),
    "go": ("m.go", "items", (
        "package m\n\ntype P struct { items []int }\n\n"
        "func (p *P) Add(x int) { p.items = append(p.items, x) }\n\n"
        "func (p *P) Sum() int {\n\tn := 0\n\tfor _, v := range p.items {\n\t\tn += v\n\t}\n\treturn n\n}\n")),
}


def _finding(lang: str, filename: str, state: str, source: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        found = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"].endswith(state)]
        assert found, f"{state} should be enumerated as state"
        return found[0]


@pytest.mark.parametrize("lang", sorted(_TESTED))
def test_a_tested_element_keeps_the_collection_s_finding(lang):
    filename, state, source = _TESTED[lang]
    assert _finding(lang, filename, state, source)["verdict"] == "promiscuous"


@pytest.mark.parametrize("lang", sorted(_UNTESTED))
def test_a_loop_that_tests_nothing_still_clears(lang):
    filename, state, source = _UNTESTED[lang]
    assert _finding(lang, filename, state, source)["verdict"] == "neutral"

"""A local bound from a read of the state, then tested, is the state driving a decision.

The carried-value rule clears a state none of whose references sits in a test expression:
unbounded data that never reaches a branch does not bound testability. Reading a value out of
the state into a local first puts no reference to the state in a test either:

    let value = await env.CACHE.get(key);
    if (!value) { ... }

The test is on `value`, and what `value` holds is what the state holds at that key, so which
branch runs depends on the state. The rule read the state's own references, found none in a test
and cleared it. On an Astro site audited on 2026-11-12 that is how a Worker's `env` came out
neutral after the classifier had read it as unbounded.

Now a reference that is READ, through member access, a method call taken off it, a subscript,
an `await` or a transparent wrapper, and whose read is bound to a local, counts as driving a
decision when that local appears in a test expression in the same function. Only a read counts:
the state handed to a call as an argument is the helper rule's question, not this one. A local
that is bound and never tested still clears.

The end-to-end cases are the six languages in which the classifier reads this shape as unbounded
before the filter runs. Python, Ruby and Java read the shapes tried here as neutral, or as
promiscuous behind the open-key guard, so the rule never reaches them end to end. The rule
itself is checked in all nine.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds, state_bounds_filters
from l1_analyzer.indicators import _get_parser
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.ts_nodes import refs as refs_under
from l1_analyzer.ts_nodes import text

# {lang: (file, state, the state and its writer, read into a local and tested, read into a
# local and handed back)}
_END_TO_END = {
    "typescript": ("m.ts", "S",
        ("export const S = { kv: new Map<string, string>() };\n"
         "export function put(k: string, v: string) { S.kv.set(k, v); }\n"),
        "export async function f(k: string) { let v = await S.kv.get(k); if (!v) { return 1; } return 0; }\n",
        "export function f(k: string) { const v = S.kv.get(k); return v; }\n"),
    "javascript": ("m.js", "S",
        "export const S = { kv: new Map() };\nexport function put(k, v) { S.kv.set(k, v); }\n",
        "export function f(k) { const v = S.kv.get(k); if (v) { return 1; } return 0; }\n",
        "export function f(k) { const v = S.kv.get(k); return v; }\n"),
    "csharp": ("P.cs", "cache",
        ("using System.Collections.Generic;\n"
         "class Store { public Dictionary<string, string> Kv = new Dictionary<string, string>(); }\n"
         "class P {\n  private Store cache = new Store();\n  void Put(string k, string v) { cache.Kv[k] = v; }\n"),
        "  int F(string k) { var v = cache.Kv.GetValueOrDefault(k); if (v != null) { return 1; } return 0; }\n}\n",
        "  string F(string k) { var v = cache.Kv.GetValueOrDefault(k); return v; }\n}\n"),
    "rust": ("m.rs", "cache",
        ("use std::collections::HashMap;\nstruct Store { kv: HashMap<String, String> }\nstruct P { cache: Store }\n"
         "impl P {\n    fn put(&mut self, k: String, v: String) { self.cache.kv.insert(k, v); }\n"),
        "    fn f(&self, k: &str) -> i32 { let v = self.cache.kv.get(k); if v.is_some() { return 1; } 0 }\n}\n",
        "    fn f(&self, k: &str) -> Option<&String> { let v = self.cache.kv.get(k); v }\n}\n"),
    "go": ("m.go", "cache",
        ("package m\n\ntype Store struct { kv map[string]string }\n\ntype P struct { cache Store }\n\n"
         "func (p *P) Put(k, v string) { p.cache.kv[k] = v }\n\n"),
        "func (p *P) F(k string) int {\n\tv := p.cache.kv[k]\n\tif v != \"\" {\n\t\treturn 1\n\t}\n\treturn 0\n}\n",
        "func (p *P) F(k string) string {\n\tv := p.cache.kv[k]\n\treturn v\n}\n"),
    "c": ("m.c", "counts",
        "static struct { int kv[64]; } counts;\nvoid put(int k, int v) { counts.kv[k] = v; }\n",
        "int f(int k) { int v = counts.kv[k]; if (v) { return 1; } return 0; }\n",
        "int f(int k) { int v = counts.kv[k]; return v; }\n"),
}


def _finding(lang: str, filename: str, state: str, source: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        found = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"].endswith(state)]
        assert found, f"{state} should be enumerated as state"
        return found[0]


@pytest.mark.parametrize("lang", sorted(_END_TO_END))
def test_a_tested_local_keeps_the_state_s_finding(lang):
    filename, state, head, tested, _ = _END_TO_END[lang]
    assert _finding(lang, filename, state, head + tested)["verdict"] == "promiscuous"


@pytest.mark.parametrize("lang", sorted(_END_TO_END))
def test_a_local_that_is_never_tested_still_clears(lang):
    filename, state, head, _, untested = _END_TO_END[lang]
    assert _finding(lang, filename, state, head + untested)["verdict"] == "neutral"


# The rule itself, in all nine: {lang: (the state's reference as the reader keys it, read into a
# local and tested, read into a local and handed back)}.
_RULE = {
    "python": ("self.cache",
        "class P:\n    def f(self, k):\n        v = self.cache.get(k)\n        if v:\n            return 1\n        return 0\n",
        "class P:\n    def f(self, k):\n        v = self.cache.get(k)\n        return v\n"),
    "ruby": ("@cache",
        "class P\n  def f(k)\n    v = @cache.fetch(k, 0)\n    if v > 3\n      return 1\n    end\n    0\n  end\nend\n",
        "class P\n  def f(k)\n    v = @cache.fetch(k, 0)\n    v\n  end\nend\n"),
    "java": ("cache",
        "class P {\n  int f(String k) { String v = cache.get(k); if (v != null) { return 1; } return 0; }\n}\n",
        "class P {\n  String f(String k) { String v = cache.get(k); return v; }\n}\n"),
    "csharp": ("cache",
        "class P {\n  int F(string k) { var v = cache[k]; if (v != null) { return 1; } return 0; }\n}\n",
        "class P {\n  string F(string k) { var v = cache[k]; return v; }\n}\n"),
    "javascript": ("S",
        "function f(k) { let v; v = S.get(k); if (v) { return 1; } return 0; }\n",
        "function f(k) { let v; v = S.get(k); return v; }\n"),
    "typescript": ("S",
        "async function f(k: string) { const v = (await S.get(k))!; if (v) { return 1; } return 0; }\n",
        "async function f(k: string) { const v = (await S.get(k))!; return v; }\n"),
    "rust": ("self.cache",
        "impl P {\n    fn f(&self, k: &str) -> i32 { let v = self.cache.get(k); if v.is_some() { return 1; } 0 }\n}\n",
        "impl P {\n    fn f(&self, k: &str) -> Option<&String> { let v = self.cache.get(k); v }\n}\n"),
    "go": ("p.cache",
        "package m\n\nfunc (p *P) F(k string) int {\n\tv, ok := p.cache[k]\n\tif !ok {\n\t\treturn 1\n\t}\n\treturn len(v)\n}\n",
        "package m\n\nfunc (p *P) F(k string) string {\n\tv := p.cache[k]\n\treturn v\n}\n"),
    "c": ("counts",
        "int f(int k) { int v = counts[k]; if (v) { return 1; } return 0; }\n",
        "int f(int k) { int v = counts[k]; return v; }\n"),
}


def _drives_no_decision(lang: str, key: str, source: str) -> bool:
    sp = LANG_SPEC[lang]
    root = _get_parser(lang).parse(source.encode()).root_node
    # Every node spelling the state the way the reader keys it: a name, a member access such
    # as `self.cache`, or Ruby's instance variable. Collected here rather than through the
    # enumerator, which stops at class bodies and wants a declaration these snippets omit.
    kinds = {*sp["name_reference_types"], *sp["member_types"], "instance_variable"}
    refs = refs_under(root, lambda n: n.type in kinds and text(n) == key)
    assert refs, f"{key} should be found in the source"
    return state_bounds_filters._drives_no_decision(refs, sp)


@pytest.mark.parametrize("lang", sorted(_RULE))
def test_the_rule_reads_a_tested_local_as_a_decision(lang):
    key, tested, _ = _RULE[lang]
    assert not _drives_no_decision(lang, key, tested)


@pytest.mark.parametrize("lang", sorted(_RULE))
def test_the_rule_still_clears_a_local_nobody_tests(lang):
    key, _, untested = _RULE[lang]
    assert _drives_no_decision(lang, key, untested)


def test_a_state_handed_to_a_call_is_not_a_read_of_it():
    """`const v = pick(S); if (v)` is the helper rule's question: whether `pick` tests S is
    read inside `pick`. Counting the call's result here would make any call over the state a
    decision on it."""
    source = "function f() { const v = pick(S); if (v) { return 1; } return 0; }\n"
    assert _drives_no_decision("javascript", "S", source)

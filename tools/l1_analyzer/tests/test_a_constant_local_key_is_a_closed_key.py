"""A key held in a binding that cannot be reassigned and was initialised to a literal is that literal.

A keyed read on state is graded by its key. `S.get('status')` cuts one cell out of S's domain, a
two-class split. `S.get(k)` with `k` a parameter ranges over every key there is, so the state is
unbounded. A name used as a key was always read as the second kind, including

    const key = 'status';
    let value = await env.CACHE.get(key);

where `key` can only ever be `'status'`. That made a Worker's `env` on an Astro site
promiscuous, and spelling the literal inline made it neutral: the same program, two grades.

Now a name read as a key is resolved through the lexical scope to the binding it names. When that
binding cannot be reassigned and its initialiser is a literal, the key is that literal and shares
its cell with the literal written inline. Which bindings cannot be reassigned is a language fact:

    JavaScript, TypeScript   const
    Java                     final (a local or a field)
    C#                       const (a local or a field; readonly can still be assigned in a constructor)
    Rust                     let without mut, const, static without mut
    Go                       const
    C                        const on a plain declarator (`const char *p` is a mutable pointer)
    Python, Ruby             none: every local can be rebound, so the rule never applies

A binding that can be reassigned, a parameter or loop binding of the same name nearer the read, a
template with a substitution, or two bindings of the name in one scope, leave the key open.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds

# {lang: (file, state, the state and its writer, the reading function with KEY_DECL in it, the
# fixed declaration, the reassignable one)}
_CASES = {
    "typescript": ("m.ts", "S",
        "export const S = new Map<string, string>();\nexport function put(k: string, v: string) { S.set(k, v); }\n",
        "export function f() { KEY_DECL if (S.get(k)) { return 1; } return 0; }\n",
        "const k = 'status';", "let k = 'status';"),
    "javascript": ("m.js", "S",
        "export const S = new Map();\nexport function put(k, v) { S.set(k, v); }\n",
        "export function f() { KEY_DECL if (S.get(k)) { return 1; } return 0; }\n",
        "const k = 'status';", "var k = 'status';"),
    "java": ("P.java", "cache",
        ("import java.util.*;\nclass P {\n  private Map<String, String> cache = new HashMap<>();\n"
         "  void put(String k, String v) { cache.put(k, v); }\n"),
        "  int f() { KEY_DECL if (cache.get(k) != null) { return 1; } return 0; }\n}\n",
        "final String k = \"status\";", "String k = \"status\";"),
    "csharp": ("P.cs", "cache",
        ("using System.Collections.Generic;\nclass P {\n"
         "  private Dictionary<string, string> cache = new Dictionary<string, string>();\n"
         "  void Put(string k, string v) { cache[k] = v; }\n"),
        "  int F() { KEY_DECL if (cache.GetValueOrDefault(k) != null) { return 1; } return 0; }\n}\n",
        "const string k = \"status\";", "var k = \"status\";"),
    "rust": ("m.rs", "cache",
        ("use std::collections::HashMap;\nstruct P { cache: HashMap<String, String> }\nimpl P {\n"
         "    fn put(&mut self, k: String, v: String) { self.cache.insert(k, v); }\n"),
        "    fn f(&self) -> i32 { KEY_DECL if self.cache.get(k).is_some() { return 1; } 0 }\n}\n",
        "let k = \"status\";", "let mut k = \"status\";"),
    "go": ("m.go", "cache",
        "package m\n\ntype P struct { cache map[string]string }\n\nfunc (p *P) Put(k, v string) { p.cache[k] = v }\n\n",
        "func (p *P) F() int {\n\tKEY_DECL\n\tif p.cache[k] != \"\" {\n\t\treturn 1\n\t}\n\treturn 0\n}\n",
        "const k = \"status\"", "k := \"status\""),
    "c": ("m.c", "counts",
        "static int counts[64];\nvoid put(int k, int v) { counts[k] = v; }\n",
        "int f(void) { KEY_DECL if (counts[k]) { return 1; } return 0; }\n",
        "const int k = 3;", "int k = 3;"),
}


def _verdict(lang: str, filename: str, state: str, source: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        found = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"].endswith(state)]
        assert found, f"{state} should be enumerated as state"
        return found[0]["verdict"]


def _source(lang: str, declaration: str) -> tuple[str, str, str]:
    filename, state, head, reader, _, _ = _CASES[lang]
    return filename, state, head + reader.replace("KEY_DECL", declaration)


@pytest.mark.parametrize("lang", sorted(_CASES))
def test_a_fixed_literal_key_is_the_literal(lang):
    filename, state, source = _source(lang, _CASES[lang][4])
    assert _verdict(lang, filename, state, source) == "neutral"


@pytest.mark.parametrize("lang", sorted(_CASES))
def test_a_key_that_can_be_reassigned_stays_open(lang):
    filename, state, source = _source(lang, _CASES[lang][5])
    assert _verdict(lang, filename, state, source) == "promiscuous"


_TS_HEAD = "export const S = new Map<string, string>();\nexport function put(k: string, v: string) { S.set(k, v); }\n"


def test_a_module_level_const_is_read_from_inside_a_function():
    source = _TS_HEAD + "const KEY = 'status';\nexport function f() { if (S.get(KEY)) { return 1; } return 0; }\n"
    assert _verdict("typescript", "m.ts", "S", source) == "neutral"


def test_the_literal_and_the_name_for_it_are_one_cell():
    """`S.get('status')` and `S.get(KEY)` with KEY = 'status' ask about the same cell, so they
    cut the partition once between them, as two inline spellings of the literal do."""
    source = _TS_HEAD + ("const KEY = 'status';\n"
                         "export function f() { if (S.get(KEY)) { return 1; } if (S.get('status')) { return 2; } return 0; }\n")
    assert _verdict("typescript", "m.ts", "S", source) == "neutral"


@pytest.mark.parametrize("source", [
    # A parameter of the same name, nearer the read than the constant.
    "const k = 'status';\nexport function f(k: string) { if (S.get(k)) { return 1; } return 0; }\n",
    # A loop binding of the same name.
    "const k = 'status';\nexport function f(ks: string[]) { for (const k of ks) { if (S.get(k)) { return 1; } } return 0; }\n",
    # A template that interpolates is not one value.
    "export function f(x: string) { const k = `a-${x}`; if (S.get(k)) { return 1; } return 0; }\n",
])
def test_a_name_the_rule_cannot_settle_stays_open(source):
    assert _verdict("typescript", "m.ts", "S", _TS_HEAD + source) == "promiscuous"


def test_a_const_in_the_block_around_the_read_is_the_one_it_sees():
    """Block scope: the `else` branch's binding is not visible from the `if` branch, so the read
    sees exactly one binding of `k`, the literal beside it."""
    source = _TS_HEAD + ("export function f(x: boolean) { if (x) { const k = 'a'; if (S.get(k)) { return 1; } }"
                         " else { const k = 'b'; } return 0; }\n")
    assert _verdict("typescript", "m.ts", "S", source) == "neutral"


_RUST_HEAD = ("use std::collections::HashMap;\nstruct P { cache: HashMap<String, String> }\nimpl P {\n"
              "    fn put(&mut self, k: String, v: String) { self.cache.insert(k, v); }\n")


@pytest.mark.parametrize("body", [
    # Declared after the read: the read is the parameter's.
    "    fn f(&self, k: &str) -> i32 { if self.cache.get(k).is_some() { return 1; } let k = \"status\"; 0 }\n}\n",
    # Shadowed in the same block: two bindings of the name in one scope are not settled here.
    "    fn f(&self, x: &str) -> i32 { let k = \"status\"; let k = x; if self.cache.get(k).is_some() { return 1; } 0 }\n}\n",
])
def test_a_rust_binding_that_does_not_settle_the_read_leaves_it_open(body):
    assert _verdict("rust", "m.rs", "cache", _RUST_HEAD + body) == "promiscuous"


def test_python_has_no_binding_that_cannot_be_rebound():
    source = ("class P:\n    def __init__(self):\n        self.cache = {}\n\n"
              "    def put(self, k, v):\n        self.cache[k] = v\n\n"
              "    def f(self):\n        k = 'status'\n        if self.cache.get(k):\n            return 1\n        return 0\n")
    assert _verdict("python", "m.py", "cache", source) == "promiscuous"

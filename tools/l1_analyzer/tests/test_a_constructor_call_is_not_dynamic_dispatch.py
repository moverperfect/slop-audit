"""`new Foo(S)` names what runs, and the reader said the program chooses it at run time.

A state handed to a constructor was filed as `dynamic_dispatch`, "the call target is chosen
while the program runs". The reader finds a callee in a call's `function` field, and a
constructor call keeps it somewhere else: `constructor` in JavaScript's new_expression, `type`
in C#'s and Java's object_creation_expression. Finding no function, it concluded the target was
computed. On an Astro site audited on 2026-11-13 six states stopped at `new Response(...)` that
way, and `new URLSearchParams(...)` before them.

A per-language row now names each constructor-call node and the field that holds what is
constructed, and the constructor is read the way a callee is. A plain name, with any generic
arguments peeled off, is a name the reader could model, which is ours; a name reached through
another, `ns.Foo` or `System.Text.StringBuilder`, is the adopter's boundary; anything computed
is still dynamic dispatch. Java read its plain constructors as ours already, by way of having no
receiver field, and now reads them on purpose.

Python, Ruby, Rust, Go and C have no constructor-call node: they construct through an ordinary
call or a literal, which the reader already reads.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds

_TS = "class Foo { constructor(x) {} }\nexport let S = 1;\nexport function f() { return EXPR; }\n"
_CS = ("class Foo { public Foo(int x) {} }\n"
       "class A {\n  private static int S = 0;\n  object F() { S = S + 1; return EXPR; }\n}\n")
_JAVA = ("class Foo { Foo(int x) {} }\n"
         "class A {\n  private static int S = 0;\n  Object f() { S = S + 1; return EXPR; }\n}\n")

_CASES = [
    ("typescript", "m.ts", _TS, "new Foo(S)", "unmodeled_callee"),
    ("javascript", "m.js", _TS, "new Foo(S)", "unmodeled_callee"),
    ("typescript", "m.ts", _TS, "new ns.Foo(S)", "external_boundary"),
    ("typescript", "m.ts", _TS, "new Foo<number>(S)", "unmodeled_callee"),
    ("typescript", "m.ts", _TS, "new (pick())(S)", "dynamic_dispatch"),
    ("csharp", "a.cs", _CS, "new Foo(S)", "unmodeled_callee"),
    ("csharp", "a.cs", _CS, "new System.Text.StringBuilder(S)", "external_boundary"),
    ("csharp", "a.cs", _CS, "new List<int>(S)", "unmodeled_callee"),
    ("java", "A.java", _JAVA, "new Foo(S)", "unmodeled_callee"),
    ("java", "A.java", _JAVA, "new java.util.ArrayList<>(S)", "external_boundary"),
]


def _silence(lang: str, filename: str, source: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        [found] = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"].endswith("S")]
        return found["silence"]


@pytest.mark.parametrize("lang,filename,template,expr,reason", _CASES,
                         ids=[f"{c[0]}:{c[3]}" for c in _CASES])
def test_a_constructor_is_read_like_a_callee(lang, filename, template, expr, reason):
    assert _silence(lang, filename, template.replace("EXPR", expr)) == reason

"""`fetch(S)`, `new Response(S)`, `getComputedStyle(S)`: the platform's code, filed as ours.

A plain-name callee was `unmodeled_callee`, a name this reader could model and had not. In an
ES module a name that is neither declared in the file nor imported can only be a global the
platform provides: the browser's `getComputedStyle`, the Workers runtime's `fetch` and
`Response`, the language's `URLSearchParams`. None of that code is in the repository, so the
honest reason is the adopter's boundary, where an explicit contract would make it decidable.

WHAT AN ES MODULE IS, here. A `.mjs` or `.mts` file always is; a `.cjs` or `.cts` file never is;
a `.js` or `.ts` file is one when the nearest package.json says `"type": "module"` (see
test_a_type_module_package_makes_a_file_an_es_module.py); and any file is one when it has a
top-level `import` or `export`, which is TypeScript's own `moduleDetection: auto` rule. These
cases write a package.json with no type. A file that is none of these is a SCRIPT, and scripts
share one global scope: a name it does not declare may be declared by another script in the
project, so it stays ours, and so does every name in a CommonJS file.

"Declared in the file" is read generously: any binding of the name anywhere in the file, a
parameter of some other function or a destructured local included, keeps it ours. Erring that
way can only leave a global filed as ours, never move our own code to the adopter.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds


def _silence(filename: str, source: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "package.json").write_text('{"name": "site"}')
        (root / filename).write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        lang = "javascript" if filename.endswith(("js", "cjs", "mjs")) else "typescript"
        [found] = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"] == "S"]
        return found["silence"]


@pytest.mark.parametrize("call", ["fetch(S)", "new Response(S)", "getComputedStyle(S)",
                                  "new URLSearchParams(S)"])
def test_an_undeclared_name_in_an_es_module_is_the_platform_s(call):
    source = f"export let S = 1;\nexport function f() {{ return {call}; }}\n"
    assert _silence("m.ts", source) == "external_boundary"


def test_an_mjs_file_is_a_module_without_saying_so():
    assert _silence("m.mjs", "let S = 1;\nS = 2;\nfunction f() { return fetch(S); }\nf();\n") == "external_boundary"


@pytest.mark.parametrize("source", [
    # Declared in the file, as a class, as another function's parameter, and destructured.
    "class Response { constructor(x) {} }\nexport let S = 1;\nexport function f() { return new Response(S); }\n",
    "export function g(fetch) { return fetch; }\nexport let S = 1;\nexport function f() { return fetch(S); }\n",
    "const { fetch } = globalThis;\nexport let S = 1;\nexport function f() { return fetch(S); }\n",
])
def test_a_name_the_file_binds_anywhere_stays_ours(source):
    assert _silence("m.ts", source) == "unmodeled_callee"


@pytest.mark.parametrize("filename,source", [
    # A script: no import, no export. Another script may declare `fetch` for it.
    ("m.js", "let S = 1;\nS = 2;\nfunction f() { return fetch(S); }\nf();\n"),
    # CommonJS.
    ("m.cjs", "let S = 1;\nS = 2;\nmodule.exports = function f() { return fetch(S); };\n"),
])
def test_a_script_or_a_commonjs_file_keeps_the_silence_it_had(filename, source):
    assert _silence(filename, source) == "unmodeled_callee"

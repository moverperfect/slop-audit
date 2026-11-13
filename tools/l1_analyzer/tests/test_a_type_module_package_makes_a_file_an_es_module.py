"""`"type": "module"` in the nearest package.json makes a `.js` or `.ts` file an ES module.

That is Node's own rule: a `.js` file is an ES module when the nearest `package.json` above it
says `"type": "module"`, whether or not the file imports or exports anything. TypeScript follows
it for `.ts` under its Node module settings. The ES-module test reads it beside the top-level
`import`/`export` rule, and it decides one thing: whether a callee name the file neither declares
nor imports can only be a platform global (`external_boundary`) or may be declared by another
script sharing the global scope (`unmodeled_callee`).

The nearest `package.json` decides, looking no higher than the repository root, as Node looks no
higher than the first one it finds. `"type": "commonjs"`, or no `"type"` at all, leaves the
import/export rule as it was. A `.mjs`/`.cjs` file is settled by its suffix either way, and the
suffixes this rule does not name, `.jsx` and `.tsx`, are settled by import/export alone.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile

import pytest
from l1_analyzer import state_bounds

# No import, no export: a script unless a package.json says otherwise.
_SCRIPT = "let S = 1;\nS = 2;\nfunction f() { return fetch(S); }\nf();\n"


def _silence(files: dict[str, str]) -> str:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        source = next(n for n in files if not n.endswith(".json"))
        lang = "typescript" if source.endswith("ts") else "javascript"
        [found] = [f for f in state_bounds.classify(root, lang)["findings"] if f["state"] == "S"]
        return found["silence"]


def _package(**fields: str) -> str:
    return json.dumps({"name": "site", **fields})


@pytest.mark.parametrize("source", ["m.js", "m.ts", "src/deep/m.js"])
def test_type_module_makes_a_file_without_import_or_export_a_module(source):
    files = {"package.json": _package(type="module"), source: _SCRIPT}
    assert _silence(files) == "external_boundary"


@pytest.mark.parametrize("manifest", [_package(type="commonjs"), _package()])
def test_commonjs_or_no_type_leaves_the_import_export_rule(manifest):
    assert _silence({"package.json": manifest, "m.js": _SCRIPT}) == "unmodeled_callee"


def test_the_nearest_package_json_decides():
    """Node reads the first package.json it finds going up, and a nested one with no `"type"`
    is CommonJS however the root is set."""
    files = {"package.json": _package(type="module"), "sub/package.json": _package(), "sub/m.js": _SCRIPT}
    assert _silence(files) == "unmodeled_callee"


def test_a_cjs_file_is_commonjs_under_type_module():
    files = {"package.json": _package(type="module"),
             "m.cjs": "let S = 1;\nS = 2;\nmodule.exports = function f() { return fetch(S); };\n"}
    assert _silence(files) == "unmodeled_callee"

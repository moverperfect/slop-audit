"""A function imported from a package is code this reader cannot open, and it said "ours".

A state handed to a plain-name callee was filed as `unmodeled_callee`, "ours to fix", on the
grounds that a bare name is a builtin missing from the lists or a function in the repository.
In JavaScript a bare name is very often neither: `ok(S)` from `neverthrow`, `sequence(...)`
from Astro, `createDeliveryClient(...)` from Kontent. Those live under `node_modules`, which
this reader never opens, so the honest reason is the adopter's boundary: an explicit contract
at it would make it decidable. Seven sites on an Astro site audited on 2026-11-12 were filed
as our backlog for code nobody here can read.

A callee is a package's when the file imports it from a package the project's own
`package.json` declares, in any of its four dependency tables, or from Node's own modules
(`node:fs`, or the bare `fs`). A name imported from a path, an alias of the project's own, or
a package the manifest does not declare stays where it was.
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

    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    [finding] = [f for f in state_bounds.classify(root, "typescript")["findings"] if f["state"] == "S"]
    return finding


def _manifest(table: str, package: str) -> str:
    return json.dumps({"name": "site", table: {package: "^1.0.0"}})


@pytest.mark.parametrize("table", ["dependencies", "devDependencies", "peerDependencies",
                                   "optionalDependencies"])
def test_a_declared_package_s_function_is_an_external_boundary(tmp_path, table):
    found = _finding(tmp_path, {
        "package.json": _manifest(table, "neverthrow"),
        "src/m.ts": ("import { ok } from 'neverthrow';\n"
                     "export let S = 1;\nexport function f() { return ok(S); }\n"),
    })
    assert (found["verdict"], found["silence"]) == ("unresolved", "external_boundary")


@pytest.mark.parametrize("specifier", ["node:fs", "fs", "node:fs/promises"])
def test_a_node_built_in_is_an_external_boundary(tmp_path, specifier):
    found = _finding(tmp_path, {
        "package.json": json.dumps({"name": "site"}),
        "src/m.ts": (f"import {{ readFileSync }} from '{specifier}';\n"
                     "export let S = 'a';\nexport function f() { return readFileSync(S); }\n"),
    })
    assert found["silence"] == "external_boundary"


def test_a_scoped_package_and_an_aliased_import_are_still_the_package(tmp_path):
    found = _finding(tmp_path, {
        "package.json": _manifest("dependencies", "@kontent-ai/delivery-sdk"),
        "src/m.ts": ("import { createDeliveryClient as make } from '@kontent-ai/delivery-sdk/lib';\n"
                     "export let S = {};\nexport function f() { return make(S); }\n"),
    })
    assert found["silence"] == "external_boundary"


@pytest.mark.parametrize("specifier", ["leftpad", "@/utils/missing", "./missing"])
def test_a_name_from_anywhere_else_stays_ours(tmp_path, specifier):
    """Undeclared, or a path the project owns that resolves to nothing: still ours."""
    found = _finding(tmp_path, {
        "package.json": _manifest("dependencies", "neverthrow"),
        "src/m.ts": (f"import {{ g }} from '{specifier}';\n"
                     "export let S = 1;\nexport function f() { return g(S); }\n"),
    })
    assert found["silence"] == "unmodeled_callee"

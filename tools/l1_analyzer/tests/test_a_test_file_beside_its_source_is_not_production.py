"""A test file written beside the file it tests is a test, not production code.

The production scope dropped a test only when it sat in a directory named `test` or `tests`.
JavaScript and TypeScript projects mostly write `foo.test.ts` next to `foo.ts`, or gather them
in a `__tests__` directory, and Go writes `foo_test.go` next to `foo.go`. All three were
measured as production by every indicator that reads the production scope: dead code,
duplication, type escapes, god files, mutable state, the state classifier and the
absolute-path check. On an Astro and vitest site audited on 2026-10-29 that was 115 of the
373 files the audit called production, and the duplication, type-escape and god-file readings
were mostly readings of the test suite.

The name is not believed on its own, for the reason `_test_dir_corroborated` gives: a name is
free to forge, and renaming `billing.ts` to `billing.test.ts` would otherwise take it out of
eight indicators at the cost of nothing. A file named like a test is set aside only when its
own opening names a test framework, the same evidence a test directory has to show. A file
that fails to corroborate is measured, which is the direction that can only add code to the
audit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from l1_analyzer import dead_code, scope

_VITEST = "import { describe, expect, it } from 'vitest';\n"


def _repo(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def _production(root: Path, extensions: tuple[str, ...]) -> list[str]:
    files, _skipped, _lines = scope._read_source_bytes(root, extensions, scope.PRODUCTION)
    return sorted(f.relative_to(root).as_posix() for f, _raw in files)


def test_a_colocated_vitest_file_is_not_production(tmp_path):
    repo = _repo(tmp_path, {
        "src/price.ts": "export const price = (n: number) => n * 2;\n",
        "src/price.test.ts": _VITEST + "import { price } from './price';\n"
                             "describe('price', () => { it('doubles', () => expect(price(2)).toBe(4)); });\n",
        "src/view.spec.tsx": "import { test } from 'vitest';\ntest('renders', () => {});\n",
    })
    assert _production(repo, (".ts", ".tsx")) == ["src/price.ts"]


def test_a_tests_directory_in_the_jest_spelling_is_not_production(tmp_path):
    """`__tests__` is Jest's convention and the production scope did not know it. The
    directory is corroborated the way `tests/` is, so a helper inside it with no test name of
    its own goes with it."""
    repo = _repo(tmp_path, {
        "src/price.ts": "export const price = 1;\n",
        "src/__tests__/price.test.ts": _VITEST + "it('x', () => {});\n",
        "src/__tests__/fixtures.ts": "export const fixture = { price: 1 };\n",
    })
    assert _production(repo, (".ts",)) == ["src/price.ts"]


def test_a_go_test_file_is_not_production(tmp_path):
    """Go puts `_test.go` beside the package it tests and imports "testing" to do it. The
    comment in test_regions said the existing rule caught these; it read only directories."""
    repo = _repo(tmp_path, {
        "calc/calc.go": "package calc\n\nfunc Add(a, b int) int { return a + b }\n",
        "calc/calc_test.go": 'package calc\n\nimport "testing"\n\nfunc TestAdd(t *testing.T) {}\n',
    })
    assert _production(repo, (".go",)) == ["calc/calc.go"]


def test_a_test_name_with_no_framework_behind_it_is_still_measured(tmp_path):
    """The rename that would otherwise be free. Production code under a test file's name,
    with nothing in it that runs as a test, stays in the audit."""
    repo = _repo(tmp_path, {
        "src/billing.test.ts": "export function charge(n: number) { return n * 100; }\n",
    })
    assert _production(repo, (".ts",)) == ["src/billing.test.ts"]


def test_the_set_aside_test_files_are_disclosed_with_their_own_reason(tmp_path):
    repo = _repo(tmp_path, {
        "src/price.ts": "export const price = 1;\n",
        "src/price.test.ts": _VITEST + "it('x', () => {});\n",
    })
    disclosed = scope.bucketed_paths(repo, (".ts",), scope.PRODUCTION)
    assert disclosed["counts"] == {"test-file": 1}


def test_a_definition_only_a_colocated_test_calls_is_reported_test_only(tmp_path):
    """Dead code splits its reference sites into production and tests so that a name only the
    tests call is disclosed rather than called live or dead. It split them by the same reason
    the scope gives, so a colocated test file was a production caller."""
    repo = _repo(tmp_path, {
        "src/price.ts": "export function price(n: number) { return n * 2; }\n"
                        "export function onlyTested(n: number) { return n; }\n",
        "src/main.ts": "import { price } from './price';\nconsole.log(price(1));\n",
        "src/price.test.ts": _VITEST + "import { onlyTested } from './price';\n"
                             "it('x', () => expect(onlyTested(1)).toBe(1));\n",
    })
    row = dead_code.analyze(repo, "typescript")
    assert any("onlyTested" in str(entry) for entry in row["test_only"]), row["test_only"]

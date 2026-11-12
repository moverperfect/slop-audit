"""L1.15 for TypeScript counts what the canon names, and the canon names `any`.

spec/03-layer1-indicators.md defines the TypeScript escape as "`any` in TypeScript (excluding
declaration files)". The implementation counted `unknown` as well, and counted declaration
files, and neither is in the definition.

`unknown` is the opposite of an escape. It is TypeScript's safe top type: a value typed
`unknown` cannot be used until the code narrows it, so the checker stays in force at every
use. `any` switches the checker off for that value. Counting both charged a codebase for
writing the careful annotation, and an author watching the number learns to write `any`,
which reads the same to this counter and is worse. That is the incentive the bare-generic
fix in this package was written to remove, from the other side.

A declaration file describes code that lives somewhere else, often JavaScript with no types
at all, and its `any` says what that code accepts rather than where this codebase stopped
checking. On an Astro site audited on 2026-10-29, the generated runtime declarations held
365 of the 826 escapes counted, and every one of the other 461 was `unknown` in hand-written
code: the density was Slop, and by the canon's definition the hand-written code held none.
"""

from __future__ import annotations

from l1_analyzer import gate, indicators


def _count(tmp_path, files: dict[str, str]) -> str:
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return indicators._compute_type_escapes(tmp_path, "typescript")["details"]


def test_unknown_is_not_counted_and_any_still_is(tmp_path):
    details = _count(tmp_path, {"a.ts": "export function f(x: unknown, y: any) { return [x, y]; }\n"})
    assert details.startswith("1 escapes"), details


def test_a_caught_error_typed_unknown_is_not_an_escape(tmp_path):
    """The shape TypeScript's own `useUnknownInCatchVariables` asks for."""
    details = _count(tmp_path, {"a.ts": "try { run(); } catch (e: unknown) { report(e); }\n"})
    assert details.startswith("0 escapes"), details


def test_a_declaration_file_is_outside_the_count_and_its_lines_with_it(tmp_path):
    """Excluded from both halves. Counting its lines while ignoring its escapes would dilute
    the density with code the definition says is not being measured."""
    details = _count(tmp_path, {
        "env.d.ts": "declare const anything: any;\ndeclare function g(x: any): any;\n",
        "a.ts": "export const n: number = 1;\n",
    })
    assert details == "0 escapes in 1 production LOC", details


def test_the_ratchet_counts_what_the_indicator_counts(tmp_path):
    (tmp_path / "env.d.ts").write_text("declare const anything: any;\n")
    (tmp_path / "a.ts").write_text("export function f(x: unknown, y: any) { return [x, y]; }\n")
    assert gate._count_type_escapes(tmp_path, "typescript") == 1

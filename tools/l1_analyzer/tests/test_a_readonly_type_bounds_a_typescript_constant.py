"""A TypeScript constant's declared type says whether the value can be written, and a cast
does not hide a value that can.

The state classifier decides whether a module `const` is state by looking at the value it is
bound to: a container literal or a `new` is writable, `Object.freeze(...)` is not. It never
looked at the declared type. So the idiomatic TypeScript constant table,

    const ALLOWED: ReadonlySet<string> = new Set(['a', 'b']);

read as unbounded mutable state, though the checker refuses every `.add` on it, the same as it
refuses a write through `Object.freeze`. On an Astro site audited on 2026-10-29 most of the 25
states that set the grade to F were constant tables of this shape.

The other direction was a hole. A value wrapped in `x as T` or `x satisfies T` was not a
container literal, not a `new` and not a call, so it was declined without being looked at:

    export const CACHE = {} satisfies Record<string, number>;

is the same writable object as `{}` and read as nothing. The walk now looks through `as`,
`satisfies`, `!` and parentheses to the value inside. Two casts do change what the value is,
and stay declined: `as const`, which makes the literal readonly, and a cast to a readonly type.

`Readonly<Set<T>>` is not on the readonly side. `Readonly` marks properties readonly and a
Set's `add` is a method, so the checker lets it through; only `ReadonlySet` withholds it.
"""

from __future__ import annotations

import subprocess

import pytest

_BRANCHES_ON_IT = "\nexport function ok(k: string) { if (X.has(k)) { return 1; } return 0; }\n"
_WRITES_AND_BRANCHES = ("\nexport function put(k: string) { X[k] = 1; }\n"
                        "export function ok(k: string) { if (X[k]) { return 1; } return 0; }\n")


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _states(tmp_path, source: str) -> int:
    from l1_analyzer import state_bounds

    (tmp_path / "m.ts").write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return sum(state_bounds.classify(tmp_path, "typescript")["counts"].values())


@pytest.mark.parametrize("declaration", [
    "export const X: ReadonlySet<string> = new Set(['a', 'b']);",
    "export const X: ReadonlyMap<string, number> = new Map([['a', 1]]);",
    "export const X: readonly string[] = ['a', 'b'];",
    "export const X: ReadonlyArray<string> = ['a', 'b'];",
    "export const X: Readonly<Record<string, number>> = { a: 1 };",
    "export const X = new Set(['a', 'b']) as ReadonlySet<string>;",
    "export const X = { a: 1 } as const;",
    "export const X = ({ a: 1 } as const) satisfies Record<string, number>;",
])
def test_a_constant_the_checker_will_not_let_anyone_write_is_not_state(tmp_path, declaration):
    assert _states(tmp_path, declaration + _BRANCHES_ON_IT) == 0


@pytest.mark.parametrize("declaration", [
    "export const X = {} satisfies Record<string, number>;",
    "export const X = {} as Record<string, number>;",
    "export const X = ({});",
    "export const X = (new Map())!;",
])
def test_a_writable_value_inside_a_cast_is_still_state(tmp_path, declaration):
    assert _states(tmp_path, declaration + _WRITES_AND_BRANCHES) == 1


def test_readonly_around_a_set_still_lets_it_be_added_to(tmp_path):
    declaration = "export const X: Readonly<Set<string>> = new Set(['a']);"
    assert _states(tmp_path, declaration + _BRANCHES_ON_IT) == 1


def test_the_plain_constant_table_is_still_state(tmp_path):
    """The reading this does not change: a Set nothing typed readonly is writable."""
    assert _states(tmp_path, "export const X = new Set(['a', 'b']);" + _BRANCHES_ON_IT) == 1

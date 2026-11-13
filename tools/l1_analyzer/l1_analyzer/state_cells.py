"""How wide a keyed access is: the cell-domain rules for subscripted state.

One question, asked from several places in the classifier: given `S[k]`, how many
distinct behaviours of the program can S's value distinguish? The answer turns on the
key, on what the file declares closed, and, since 2026-08-18, on the writes.

Split out of state_bounds.py when adding the write-side bound pushed that module past
the thousand-line god-file threshold this repository publishes. Splitting by
responsibility rather than shaving lines to pass the gate is the rule the methodology
gives an adopter, and it applies here first.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer import state_partition
from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.state_partition import Reach
from l1_analyzer.ts_nodes import descendants
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import is_write_target as _is_write_target
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import sub_key as _sub_key
from l1_analyzer.ts_nodes import text as _text
from l1_analyzer.ts_nodes import unwrap_unary as _unwrap_unary


def is_unbounded_value(node: Node | None, sp: LangSpec) -> bool:
    """A value used as a lookup key / index. Literals are bounded, and so is a name that can
    only ever hold one (`literal_key`); anything else (a parameter, a variable) ranges over an
    unbounded domain."""
    return _unwrap_unary(node, sp) is not None and literal_key(node, sp) is None


def keyed_read(key_node: Node | None, sp: LangSpec, cells: int | None) -> Reach:
    """`S[k]` read. An unbounded key ranges over an unbounded domain; a literal key cuts
    one more class out of it, and whether that class has a neighbour is the whole
    ordered/unordered distinction: `S[3]` sits between `S[2]` and `S[4]`, `S["beta"]` sits
    between nothing. Distinct literals are distinct discriminators, so d of them leave
    d+1 classes."""
    if is_unbounded_value(key_node, sp):
        # An open key over a bounded cell set reaches the cells and nothing else: the ones
        # the writes can create, plus absent. Every such read splits on the SAME cell set,
        # so they share one discriminator key rather than counting once per read site.
        if cells is not None:
            return state_partition.finite(cells + 1, False, "cells")
        return state_partition.unbounded()
    # The literal itself, whether written here or bound to a fixed name, so `S['a']` and
    # `S[K]` with K fixed at 'a' cut the partition at one cell between them.
    key = literal_key(key_node, sp)
    return state_partition.finite(2, key is not None and key.type in state_partition.ORDERED_LITERALS, cell_key(key))


def literal_key(node: Node | None, sp: LangSpec) -> Node | None:
    """The literal a key stands for, or None when it stands for no single value.

    A literal stands for itself. So does a NAME bound, in the scope the read sees, by a
    declaration that can never be reassigned and was initialised to a literal:
    `const key = 'status'; S.get(key)` can only ever ask about `'status'`. Reading
    such a name as an open key graded one program two ways, by whether the author named the
    literal or wrote it inline. Which declarations are fixed is the language's
    `fixed_bindings` row; Python and Ruby declare none, so no name is ever resolved there."""
    node = _unwrap_unary(node, sp)
    if node is None:
        return None
    if node.type in sp["literal_types"]:
        return node
    if node.type in sp["name_reference_types"] and sp["fixed_bindings"]:
        return _fixed_literal(node, sp)
    return None


def _fixed_literal(name: Node, sp: LangSpec) -> Node | None:
    """The literal a name is fixed to, found by lexical scope: the nearest enclosing node
    that binds the name decides, and every doubt answers None.

    None when the nearest binding is a parameter or a loop binding, when it is reassignable,
    when its initialiser is anything but one literal (a template that interpolates is not
    one), when the scope binds the name twice (Rust's shadowing `let`), or when, inside a
    function, the binding comes after the read and so is not the one the read sees."""
    key = _text(name)
    child, scope = name, name.parent
    while scope is not None:
        if key in _bound_on_the_way(scope, child, sp):
            return None
        found = [(decl, value) for decl in _declarations_in(scope, sp)
                 for bound, value in _declared(decl, sp) if bound == key]
        if found:
            if len(found) != 1:
                return None
            decl, value = found[0]
            in_function = any(n.type in sp["func_types"] for n in _ancestors(scope))
            if in_function and decl.start_byte > name.start_byte:
                return None
            value = _unwrap_unary(value, sp)
            one_value = (value is not None and value.type in sp["literal_types"]
                         and not any(c.type == "template_substitution" for c in value.children))
            return value if one_value and _is_fixed(decl, sp) else None
        child, scope = scope, scope.parent
    return None


def _ancestors(node: Node) -> list[Node]:
    """The node and everything above it."""
    out = []
    cur: Node | None = node
    while cur is not None:
        out.append(cur)
        cur = cur.parent
    return out


def _bound_on_the_way(scope: Node, child: Node, sp: LangSpec) -> set[str]:
    """The names this scope binds other than by declaration statements: a function's or a
    catch clause's parameters, a loop's element (on the scope, or on a range clause beside the
    body as Go writes it), and a pattern a branch or arm binds. The child the read came up
    through is skipped, so a default value is not mistaken for the parameter it defaults."""
    holders = [_field(scope, f) for f in ("parameters", "parameter", "pattern")]
    if scope.type in sp["iterate_binding"]:
        holders.append(_field(scope, sp["iterate_binding"][scope.type]))
    for c in scope.children:
        if c.type in sp["iterate_binding"]:
            holders.append(_field(c, sp["iterate_binding"][c.type]))
        elif c.type not in sp["local_binding"] and c.type not in sp["fixed_bindings"]:
            holders.append(_field(c, "pattern"))
    return {_text(n) for h in holders if h is not None and not _same(h, child)
            for n in descendants(h, "named")
            if n.type in ("identifier", "shorthand_property_identifier_pattern")}


def _declarations_in(scope: Node, sp: LangSpec) -> list[Node]:
    """The declaration statements directly in this scope, an exported one included."""
    kinds = {*sp["fixed_bindings"], *sp["declaration_types"], *sp["local_binding"]}
    out = []
    for c in scope.children:
        inner = _field(c, "declaration") if c.type == "export_statement" else c
        if inner is not None and inner.type in kinds:
            out.append(inner)
    return out


def _declared(decl: Node, sp: LangSpec) -> list[tuple[str, Node | None]]:
    """(name, initialiser) for every name a declaration binds. A name bound by a pattern, or
    by a declarator that is not a plain name (C's `*p`), comes with no initialiser, so it
    binds without settling. Declarators sit at most three levels down (C# nests field,
    variable declaration, declarator), which also keeps a nested function's locals out."""
    pairs: list[tuple[str, Node | None]] = []
    level = [decl]
    for _ in range(4):
        below = []
        for node in level:
            slots = sp["local_binding"].get(node.type)
            if slots is not None:
                name_field, value_field = slots
                value = _field(node, value_field) if value_field else (
                    node.named_children[-1] if len(node.named_children) > 1 else None)
                pairs += _paired(_field(node, name_field), value, sp)
            elif _field(node, "name") is not None and _field(node, "value") is not None:
                names = node.children_by_field_name("name")
                value = _field(node, "value")
                values = value.named_children if value is not None and value.type == "expression_list" else [value]
                if len(names) == len(values):
                    pairs += [p for n, v in zip(names, values) for p in _paired(n, v, sp)]
                else:
                    pairs += [p for n in names for p in _paired(n, None, sp)]
            else:
                below += node.named_children
        level = below
    return pairs


def _paired(name: Node | None, value: Node | None, sp: LangSpec) -> list[tuple[str, Node | None]]:
    """A plain name with its initialiser; every name inside anything else with none. Go's list
    of names is paired with its list of values one to one first, when the counts agree."""
    if name is None:
        return []
    values = value.named_children if value is not None and value.type == sp["lvalue_wrapper"] else []
    names = name.named_children if sp["lvalue_wrapper"] and name.type == sp["lvalue_wrapper"] else []
    pairs = list(zip(names, values)) if names and len(names) == len(values) else [(name, value)]
    out: list[tuple[str, Node | None]] = []
    for one, its_value in pairs:
        if one.type in sp["name_reference_types"]:
            out.append((_text(one), its_value))
        else:
            out += [(_text(n), None) for n in descendants(one, "named")
                    if n.type in ("identifier", "shorthand_property_identifier_pattern")]
    return out


def _is_fixed(decl: Node, sp: LangSpec) -> bool:
    """Whether the language says this declaration's bindings can never be reassigned. The
    marker is a child or a grandchild, as `const` is the declaration's own keyword in
    JavaScript and sits in a `modifiers` node in Java."""
    row = sp["fixed_bindings"].get(decl.type)
    if row is None:
        return False
    marker, present_fixes = row
    if not marker:
        return present_fixes
    marked = any(c.type == marker or _text(c) == marker
                 or any(g.type == marker or _text(g) == marker for g in c.children)
                 for c in decl.children)
    return marked == present_fixes


def guarded_by_closed_set(key_node: Node | None, sp: LangSpec, closed_sets: dict[str, int | None]) -> int | None:
    """How many values an enclosing membership test confines this key to, or None.

    `if k in KINDS: CACHE[k] = v` writes only under a key KINDS holds, so the store can
    reach at most two cells however wide `k`'s type is. The bound is the DECLARED set's
    cardinality, which is why only a set the file declares immutable counts: a mutable
    list bounds nothing, because a later append moves the number.

    Only the consequence is read. A store on the else branch is reached by keys the test
    REJECTED, which the set does not bound, so walking up from it must find nothing."""
    if key_node is None:
        return None
    name = _text(key_node)
    node = key_node
    while node.parent is not None and node.parent.type not in sp["func_types"]:
        parent = node.parent
        if parent.type in sp["branch_types"]:
            cond = _field(parent, sp["branch_cond"])
            consequence = _field(parent, "consequence")
            mem = membership_operands(cond, sp)
            if (mem is not None and _text(mem[0]) == name and is_closed_set(mem[1], closed_sets)
                    and consequence is not None and contains(consequence, key_node)):
                size = closed_sets.get(_text(mem[1]))
                if size is not None:
                    return size
        node = parent
    return None


def contains(scope: Node, node: Node) -> bool:
    """Whether `node` sits inside `scope`, by byte span."""
    return scope.start_byte <= node.start_byte and node.end_byte <= scope.end_byte


def write_key_bound(refs: list[Node], sp: LangSpec, closed_sets: dict[str, int | None]) -> int | None:
    """How many distinct cells the subscript STORES to this state can create, or None
    when nothing bounds them.

    This is the rule the classifier had no way to express, and its absence was a false
    proof rather than a missed refinement. Every reference used to be judged alone, so a
    read with an open key reported the state provably unbounded even when every write
    into it went through a two-member frozenset. A read cannot observe a cell no write
    created, so the write side is what bounds the state and the read side never was.

    None means the rule declines, not that the state is fine: a state with no subscript
    store at all is outside its scope, and one store with an open key reopens the whole
    cell set however narrow every other store is. Both come back None and leave the
    per-reference verdict exactly as it was."""
    cells = 0
    saw_store = False
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type not in sp["subscript_types"] or not _same(_sub_collection(parent, sp), ref):
            continue
        if not _is_write_target(parent, parent.parent, sp):
            continue
        saw_store = True
        key = _sub_key(parent, sp)
        if not is_unbounded_value(key, sp):
            cells += 1
            continue
        guarded = guarded_by_closed_set(key, sp, closed_sets)
        if guarded is None:
            return None
        cells += guarded
    return cells if saw_store else None


MEMBERSHIP_TOKENS = frozenset({"in", "not in"})


def membership_operands(node: Node | None, sp: LangSpec) -> tuple[Node, Node] | None:
    """(left, right) for an `in` / `not in` membership test, else None.

    An absent node is an absent answer. This declared that it takes one and reached into it
    on the next line, so handing it the absence it advertised raised, and on the run that
    did it an adopter would get a stack trace instead of an audit."""
    if node is None:
        return None
    style = sp["membership"]
    if style == "comparison_in" and node.type == "comparison_operator":
        if not any(c.type in MEMBERSHIP_TOKENS for c in node.children):
            return None
        named = [c for c in node.children if c.is_named]
        return (named[0], named[-1]) if len(named) >= 2 else None
    if style == "binary_in" and node.type == "binary_expression" and _text(_field(node, "operator")) == "in":
        # Both halves or neither. A membership test missing one side is not a membership
        # test, and handing back a pair with a hole in it made every caller's unpacking a
        # promise this function never made.
        left, right = _field(node, "left"), _field(node, "right")
        return (left, right) if left is not None and right is not None else None
    return None


def is_closed_set(node: Node | None, closed_sets: dict[str, int | None]) -> bool:
    if node is None:
        return False
    if node.type in ("set", "tuple", "list"):
        return True
    if node.type == "call" and _text(_field(node, "function")) in ("frozenset", "set"):
        return True
    if node.type == "identifier":
        return _text(node) in closed_sets
    if node.type == "attribute":
        attr = _field(node, "attribute")
        return attr is not None and _text(attr) in closed_sets
    return False


def collect_closed_sets(root: Node) -> dict[str, int | None]:
    names: dict[str, int | None] = {}
    for n in descendants(root, "all"):
        if n.type != "assignment":
            continue
        left, rhs = _field(n, "left"), _field(n, "right")
        if left is None or not is_immutable_collection(rhs):
            continue
        if left.type == "identifier":
            names[_text(left)] = state_partition.literal_size(rhs)
        elif left.type == "attribute":
            attr = _field(left, "attribute")
            if attr is not None:
                names[_text(attr)] = state_partition.literal_size(rhs)
    return names


def is_immutable_collection(rhs: Node | None) -> bool:
    if rhs is None:
        return False
    if rhs.type == "tuple":
        return True
    if rhs.type == "call":
        return _text(_field(rhs, "function")) == "frozenset"
    return False


# name -> member count, with None for a collection that is provably fixed and not countable.


def cell_key(key_node: Node | None) -> str:
    """The discriminator identity of one cell of a keyed state.

    Both spellings of a question about a literal key share it, so `"a" in S` and `S["a"]`
    cut the partition once between them rather than twice. It exists as a function rather
    than an f-string at each site because the two sites are in different modules and drifted
    apart: one wrote holds:"a" and the other key:"a" for the same cell."""
    return f"cell:{_text(key_node)}"

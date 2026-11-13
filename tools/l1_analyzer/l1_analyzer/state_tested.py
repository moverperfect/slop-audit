"""Where a value taken from the state reaches a test that the state's own references do not show.

The carried-value rule in state_bounds_filters clears a state none of whose references sits in a
test expression: unbounded data that never reaches a branch does not bound testability. A
reference can hand its value on and have the test happen one step away, and reading only the
state's own references misses it. Two such steps are read here, each the same kind of change:

  element   a loop walks the state and its body tests the element it binds
            `for (const { pattern } of TABLE) { if (pattern.test(x)) ... }`
  local     a read of the state is bound to a local, and the local is tested
            `let v = await env.KV.get(k); if (!v) ...`

Either way which branch runs depends on what the state holds, so the state drives a decision.

A third step, the state handed to a helper in this repository which tests it there, is read by
state_reach.tested_in_a_helper, because finding the helper needs the file's call context.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer import state_ref_reads as reads
from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.ts_nodes import descendants
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import text as _text
from l1_analyzer.ts_nodes import unwrap_unary as _unwrap_unary


def element_tested(ref: Node, sp: LangSpec) -> bool:
    """Whether a loop walks this reference and its body puts the element it binds in a test
    expression. A value derived from the element counts where it is written inside the test,
    `if (pattern.test(x))`, which is how `in_test` already reads the state's own references."""
    loop = _walking_loop(ref, sp)
    if loop is None:
        return False
    node, binding_field = loop
    binding = _field(node, binding_field)
    names = {_text(n) for n in descendants(binding, "named")
             if "identifier" in n.type and not n.type.startswith("property")} if binding is not None else set()
    # Go hangs the range clause inside the for statement, which is the node with the body.
    scope = node if _field(node, "body") is not None else node.parent
    body = _field(scope, "body") if scope is not None else None
    return bool(names) and body is not None and any(
        n.type in sp["name_reference_types"] and _text(n) in names and reads.in_test(n, sp)
        for n in descendants(body, "named"))


def _walking_loop(ref: Node, sp: LangSpec) -> tuple[Node, str] | None:
    """The loop that walks this reference, with the field that binds its element: walked
    directly, through a wrapper such as `&`, or through a method chain taken off it, as
    `self.items.iter()` is. None when no loop walks it, or the loop names no binding."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        walked = sp["iterate_types"].get(parent.type)
        if walked is not None:
            holder = _field(parent, walked)
            if holder is None or not (_same(holder, cur) or _same(_unwrap_unary(holder, sp), cur)):
                return None
            binding = sp["iterate_binding"].get(parent.type)
            return (parent, binding) if binding else None
        chained = ((parent.type in sp["member_types"] and _same(_field(parent, sp["mem_object"]), cur))
                   or (not sp["flat_call"] and parent.type in sp["call_types"]
                       and _same(_field(parent, sp["call_fn"]), cur))
                   or parent.type in sp["value_wrapper_types"])
        if not chained:
            return None
        cur = parent
    return None


def derived_local_tested(ref: Node, sp: LangSpec) -> bool:
    """Whether a read of this reference is bound to a local that a test expression in the same
    function names. The read is taken off the state: a member, a method call on it, a subscript
    of it, an `await` or a transparent wrapper. The state handed to a call as an argument is
    not a read of it, and whether that callee tests it is the helper rule's question.

    A local that is rebound to something else before the test still counts. Which binding
    reaches the test is a flow question this reader does not ask, and counting it keeps a
    finding, which is the direction the carried-value rule takes when in doubt."""
    read = _read_of(ref, sp)
    binding = _bound_by(read, sp)
    if binding is None:
        return False
    names = _names_in(binding)
    # The function the local lives in, or the whole file for one bound at module level.
    scope = _enclosing_function(read, sp) or _outermost(read)
    return bool(names) and any(
        n.type in sp["name_reference_types"] and _text(n) in names and reads.in_test(n, sp)
        and not _within(n, binding)
        for n in descendants(scope, "named"))


def _read_of(ref: Node, sp: LangSpec) -> Node:
    """The outermost node of the read taken off this reference: `S.kv.get(k)` for `S`, with
    any `await` or transparent wrapper around it. The reference itself when nothing reads it."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        on_it = (
            (parent.type in sp["member_types"] and _same(_field(parent, sp["mem_object"]), cur))
            or (parent.type in sp["call_types"] and _same(
                _field(parent, sp["call_recv"] if sp["flat_call"] else sp["call_fn"]), cur))
            or (parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), cur))
            or parent.type in sp["passthrough_types"] or parent.type in sp["value_wrapper_types"]
            or parent.type in sp["suspension_types"])
        if not on_it:
            return cur
        cur = parent
    return cur


def _bound_by(value: Node, sp: LangSpec) -> Node | None:
    """What binds this value, if it is bound whole to a local: the name or pattern of a
    declarator (`local_binding`), or the target of a plain assignment. Go wraps both sides of
    a short declaration in a list, so a value that is the list's only member is unwrapped
    first. None when the value is bound to nothing."""
    parent = value.parent
    if (parent is not None and sp["lvalue_wrapper"] and parent.type == sp["lvalue_wrapper"]
            and len(parent.named_children) == 1):
        value, parent = parent, parent.parent
    if parent is None:
        return None
    slots = sp["local_binding"].get(parent.type)
    if slots is not None:
        name_field, value_field = slots
        bound = _field(parent, value_field) if value_field else (
            parent.named_children[-1] if parent.named_children else None)
        return _field(parent, name_field) if _same(bound, value) else None
    if parent.type in sp["assign_types"] and _same(_field(parent, sp["assign_right"]), value):
        return _field(parent, sp["assign_left"])
    return None


def _names_in(binding: Node) -> set[str]:
    """The local names a binding binds: the name itself, or each name in a destructuring
    pattern or a list of targets. A member target, `this.x = ...`, binds no local and gives
    nothing."""
    if binding.type == "identifier":
        return {_text(binding)}
    if "pattern" not in binding.type and binding.type not in ("expression_list", "pointer_declarator"):
        return set()
    return {_text(n) for n in descendants(binding, "named")
            if n.type in ("identifier", "shorthand_property_identifier_pattern")}


def _enclosing_function(node: Node, sp: LangSpec) -> Node | None:
    """The innermost function holding a node, or None at module level."""
    cur = node.parent
    while cur is not None and cur.type not in sp["func_types"]:
        cur = cur.parent
    return cur


def _outermost(node: Node) -> Node:
    """The root of the tree a node sits in."""
    while node.parent is not None:
        node = node.parent
    return node


def _within(node: Node, ancestor: Node) -> bool:
    """Whether `ancestor` is `node` or holds it."""
    cur: Node | None = node
    while cur is not None:
        if _same(cur, ancestor):
            return True
        cur = cur.parent
    return False

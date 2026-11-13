"""Where a plain-name callee lives: in a package, in this repository, or nowhere we can say.

The state reader decides one reference at a time, and a reference handed to a call stopped
there with one of two answers. A name reached through another object was the adopter's
boundary; a bare name was ours, "a builtin missing from the lists, or a function defined in
the repository". In JavaScript a bare name is often neither. `ok(S)` comes from a package under
`node_modules`, which this reader never opens, so filing it as our backlog told the adopter we
could fix it, when only an explicit contract at that boundary would make it decidable. And
`daysBetween(S)` comes from a file in this repository that the reader could have opened and did
not.

This module answers both from the file and the project. A callee imported from a package the
project's own `package.json` declares, or from Node's own modules, is a package's. A callee
declared in the same file, or imported by a path or a `tsconfig` alias that resolves to a file
in this repository, is a FUNCTION WHOSE BODY CAN BE READ, and this module finds it and the
parameter the state became. Reading that parameter is the state reader's own job, done once
more inside the helper with following switched off, so it goes ONE LEVEL deep and no further.

Everything here is per run, never module state. The project's packages and aliases, the files
parsed so far and the reaches already read are carried in a `Project` built by the caller and
dropped when it returns, so the same input gives the same output and nothing outlives a run.
Resolution reads `package.json`, `tsconfig.json` and the repository's own source files; it
never reads `node_modules`.

WHAT IS NOT FOLLOWED, and keeps the silence it had: an import that resolves to no file, a
re-export, a name declared more than once with a body, a callee that is not a plain name, a
parameter that is destructured or gathered by a rest, and anything a second hop would need.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.boundary import boundary, text_or_empty
from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.state_partition import Reach
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import text as _text

# Node's own modules, by the first segment of a bare specifier. `node:` spells any of them
# explicitly, and the bare spelling names the same module.
NODE_BUILTINS = frozenset({
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants",
    "crypto", "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http",
    "http2", "https", "inspector", "module", "net", "os", "path", "perf_hooks", "process",
    "punycode", "querystring", "readline", "repl", "stream", "string_decoder", "sys",
    "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
    "worker_threads", "zlib",
})

# The four tables a package can be declared in.
_DEPENDENCY_TABLES = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")

# What a resolved import may be spelled as on disk, in the order a bundler tries them. An
# import written `./a.js` names `a.ts` in a TypeScript project, so the `.js` is tried as a
# stem as well.
_SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
_SCRIPT_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")


class Followed(TypedDict):
    """What a helper does with one parameter: the reach of its references, and whether the
    value comes back out of the helper, returned or stored, so the caller should follow the
    call's own value on."""
    reach: Reach
    comes_back: bool


class Project(TypedDict):
    """What one run knows about the repository a reader is in.

    `aliases` is `tsconfig`'s `paths`, each pattern split at its `*` into the prefix it matches
    and the directories it maps to; the aliases are the project's own code, so an import
    through one is never a package's. `trees` and `reaches` are this run's caches: a file is
    parsed once however many calls reach it, and a helper's parameter is read once per (file,
    function, parameter, cell bound)."""
    root: Path
    lang: str
    packages: frozenset[str]
    aliases: list[tuple[str, list[Path]]]
    trees: dict[Path, Node | None]
    reaches: dict[tuple[str, int, int, int | None], Followed]


class CallContext(TypedDict):
    """One file's calls, readable: the run's project, the file, what it imports as {local
    name: (specifier, imported name)}, and the functions it declares at its top level.

    `follow` is False inside a helper already being read, which is what keeps the reading
    one level deep."""
    project: Project
    path: Path
    imports: dict[str, tuple[str, str]]
    functions: dict[str, Node | None]
    follow: bool


def project(repo: Path, lang: str, sp: LangSpec) -> Project | None:
    """The run's knowledge of the repository, or None for a language whose module system
    this module does not read. Reads `package.json` and `tsconfig.json` here; source files
    are read later, only when a call resolves to one."""
    if not sp["module_resolution"]:
        return None
    root = repo.resolve()
    return {"root": root, "lang": lang, "packages": packages_in(text_or_empty(repo / "package.json")),
            "aliases": _aliases(root), "trees": {}, "reaches": {}}


def packages_in(manifest: str) -> frozenset[str]:
    """Every package name a `package.json` declares, across its four dependency tables. A
    manifest that does not parse declares nothing, which leaves every import ours."""
    try:
        data = json.loads(manifest) if manifest else {}
    # honest-code-allow: L1.21.8 - a manifest that does not parse declares no packages, so no import is taken for a package's and each keeps the silence it had: the direction that moves nothing out of our backlog
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    return frozenset(name for table in _DEPENDENCY_TABLES
                     if isinstance(data.get(table), dict) for name in data[table])


def _aliases(root: Path) -> list[tuple[str, list[Path]]]:
    """`compilerOptions.paths` from the repository's `tsconfig.json`, following `extends`
    through files in the repository, never into `node_modules`, until a `paths` is found.
    Targets resolve from `baseUrl` when the config sets one and from the config file's own
    directory when it does not."""
    config = root / "tsconfig.json"
    for _ in range(4):
        options = _config(text_or_empty(config))
        compiler = options.get("compilerOptions")
        compiler = compiler if isinstance(compiler, dict) else {}
        paths = compiler.get("paths")
        if isinstance(paths, dict):
            base = config.parent / str(compiler.get("baseUrl", "."))
            return [(pattern.split("*", 1)[0],
                     [(base / t.split("*", 1)[0]).resolve() for t in targets if isinstance(t, str)])
                    for pattern, targets in sorted(paths.items()) if isinstance(targets, list)]
        parent = options.get("extends")
        if not isinstance(parent, str) or not parent.startswith("."):
            return []
        config = (config.parent / parent).resolve()
        if config.suffix != ".json":
            config = config.with_name(config.name + ".json")
    return []


def _config(text: str) -> dict[str, object]:
    """A `tsconfig` as data. It is JSON with comments and trailing commas, so both are removed
    outside strings before it is parsed; a file that still does not parse says nothing."""
    out: list[str] = []
    i, n, in_string = 0, len(text), False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    cleaned = "".join(out)
    for closer in ("}", "]"):
        cleaned = _without_trailing_commas(cleaned, closer)
    try:
        data = json.loads(cleaned) if cleaned.strip() else {}
    # honest-code-allow: L1.21.8 - a tsconfig that does not parse yields no aliases, so an alias import is never taken for a package and keeps the silence it had: the direction that moves nothing out of our backlog
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _without_trailing_commas(text: str, closer: str) -> str:
    """`[1, 2,]` and `{"a": 1,}` with the trailing comma dropped. Run after comments are
    gone, so a comma before whitespace and the closer is the only shape left to remove."""
    out: list[str] = []
    for chunk in text.split(closer):
        stripped = chunk.rstrip()
        out.append(stripped[:-1] + chunk[len(stripped):] if stripped.endswith(",") else chunk)
    return closer.join(out)


def context(project_: Project, path: Path, root: Node, sp: LangSpec, follow: bool) -> CallContext:
    """One file's calls, readable: what it imports and which functions it declares."""
    return {"project": project_, "path": path.resolve(), "imports": imports_in(root),
            "functions": functions_in(root, sp), "follow": follow}


def imports_in(root: Node) -> dict[str, tuple[str, str]]:
    """Every name an ES module imports, as {local name: (specifier, imported name)}. The
    imported name is `default` for a default import and `*` for a namespace."""
    found: dict[str, tuple[str, str]] = {}
    for statement in (c for c in root.children if c.type == "import_statement"):
        source = _field(statement, "source")
        if source is None:
            continue
        specifier = _text(source).strip("'\"`")
        for clause in (c for c in statement.named_children if c.type == "import_clause"):
            for part in clause.named_children:
                if part.type == "identifier":
                    found[_text(part)] = (specifier, "default")
                elif part.type == "namespace_import":
                    for name in (c for c in part.named_children if c.type == "identifier"):
                        found[_text(name)] = (specifier, "*")
                elif part.type == "named_imports":
                    for spec in (c for c in part.named_children if c.type == "import_specifier"):
                        imported = _text(_field(spec, "name"))
                        local = _field(spec, "alias")
                        found[_text(local) if local is not None else imported] = (specifier, imported)
    return found


def functions_in(root: Node, sp: LangSpec) -> dict[str, Node | None]:
    """The functions a module declares at its top level, by name, as `function f` or
    `const f = (...) => ...`. A name with two bodies is None: which one runs is a question
    this reader does not answer."""
    found: dict[str, Node | None] = {}
    for statement in root.children:
        declaration = _field(statement, "declaration") if statement.type == "export_statement" else statement
        if declaration is None:
            continue
        for name, fn in _declared_functions(declaration, sp):
            found[name] = None if name in found else fn
    return found


def _declared_functions(declaration: Node, sp: LangSpec) -> list[tuple[str, Node]]:
    """The (name, function) pairs one top-level declaration binds, each with a body."""
    if declaration.type in sp["func_types"] and _field(declaration, "body") is not None:
        name = _field(declaration, "name")
        return [(_text(name), declaration)] if name is not None else []
    pairs = []
    for declarator in (c for c in declaration.named_children if c.type in sp["local_binding"]):
        name_field, value_field = sp["local_binding"][declarator.type]
        name = _field(declarator, name_field)
        value = _field(declarator, value_field) if value_field else None
        if (name is not None and name.type == "identifier" and value is not None
                and value.type in sp["func_types"] and _field(value, "body") is not None):
            pairs.append((_text(name), value))
    return pairs


def exports_in(root: Node, sp: LangSpec) -> dict[str, Node | None]:
    """The functions a module exports, by exported name. A re-export from another module is
    None: it names a function somewhere else, and reading it would be a second hop."""
    local = functions_in(root, sp)
    found: dict[str, Node | None] = {}
    for statement in (c for c in root.children if c.type == "export_statement"):
        declaration = _field(statement, "declaration")
        is_default = any(c.type == "default" for c in statement.children)
        if declaration is not None:
            for name, fn in _declared_functions(declaration, sp):
                found["default" if is_default else name] = fn
            continue
        value = _field(statement, "value")
        if is_default and value is not None:
            found["default"] = _exported_value(value, local, sp)
            continue
        re_export = _field(statement, "source") is not None
        for clause in (c for c in statement.named_children if c.type == "export_clause"):
            for spec in (c for c in clause.named_children if c.type == "export_specifier"):
                name = _text(_field(spec, "name"))
                alias = _field(spec, "alias")
                found[_text(alias) if alias is not None else name] = None if re_export else local.get(name)
    return found


def _exported_value(value: Node, local: dict[str, Node | None], sp: LangSpec) -> Node | None:
    """The function `export default <value>` exports: the value itself when it is a function
    with a body, the module's function of that name when it is a name, and nothing else."""
    if value.type in sp["func_types"] and _field(value, "body") is not None:
        return value
    return local.get(_text(value)) if value.type == "identifier" else None


def imported_from_a_package(call: Node | None, calls: CallContext, sp: LangSpec) -> bool:
    """Whether this call's callee is a plain name the file imports from a package or from
    Node's own modules."""
    name = _plain_callee(call, sp)
    imported = calls["imports"].get(name) if name else None
    return imported is not None and is_external(imported[0], calls["project"])


def _plain_callee(call: Node | None, sp: LangSpec) -> str:
    """The callee's name when it is a plain identifier, and nothing otherwise."""
    fn = _field(call, sp["call_fn"]) if call is not None and not sp["flat_call"] else None
    return _text(fn) if fn is not None and fn.type == "identifier" else ""


def is_external(specifier: str, project_: Project) -> bool:
    """Whether an import names code under `node_modules` or Node's own: a package the
    project's manifest declares, or a Node built-in. A path, or a specifier one of the
    project's own aliases matches, is the project's."""
    if specifier.startswith((".", "/")) or any(prefix and specifier.startswith(prefix)
                                               for prefix, _targets in project_["aliases"]):
        return False
    if specifier.startswith("node:"):
        return True
    return package_of(specifier) in project_["packages"] or specifier.split("/", 1)[0] in NODE_BUILTINS


def package_of(specifier: str) -> str:
    """The package a bare specifier names: `@scope/name` for a scoped one, the first segment
    otherwise, and the part before the colon for a bundler's virtual module such as
    `astro:middleware`, which the `astro` package provides."""
    if ":" in specifier.split("/", 1)[0]:
        return specifier.split(":", 1)[0]
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") else parts[0]


def callee_function(call: Node | None, calls: CallContext, sp: LangSpec) -> tuple[Node, CallContext] | None:
    """The function in this repository a call's plain-name callee is, and the context its
    own body is read in, with following switched off. None when the callee is not a plain
    name, or resolves to no single function with a body this reader can open."""
    name = _plain_callee(call, sp)
    if not name:
        return None
    if name in calls["functions"]:
        fn = calls["functions"][name]
        return (fn, {**calls, "follow": False}) if fn is not None else None
    imported = calls["imports"].get(name)
    if imported is None or imported[1] == "*" or is_external(imported[0], calls["project"]):
        return None
    path = _first_on_disk(candidates(imported[0], calls["path"], calls["project"]))
    root = _tree(path, calls["project"]) if path is not None else None
    if path is None or root is None:
        return None
    fn = exports_in(root, sp).get(imported[1])
    return (fn, context(calls["project"], path, root, sp, follow=False)) if fn is not None else None


def _tree(path: Path, project_: Project) -> Node | None:
    """One repository file, parsed once per run. A file that cannot be read, or that the
    grammar parses with an error, is None: a body the reader cannot parse is not read."""
    if path not in project_["trees"]:
        source = _source(path)
        project_["trees"][path] = None if source is None else _parsed(source, path.suffix, project_["lang"])
    return project_["trees"][path]


@boundary
def _source(path: Path) -> bytes | None:
    """One file's bytes, or nothing when it cannot be read."""
    try:
        return path.read_bytes()
    # honest-code-allow: L1.21.8 - a helper whose file cannot be read is not followed, and the call keeps the silence it had: the direction that clears nothing
    except OSError:
        return None


def _parsed(source: bytes, suffix: str, lang: str) -> Node | None:
    """A file's parse tree, or nothing when the grammar reports an error in it."""
    from l1_analyzer.indicators import parser_for

    root = parser_for(suffix, lang).parse(source).root_node
    return None if root.has_error else root


def candidates(specifier: str, importer: Path, project_: Project) -> list[Path]:
    """Every file an import could name, in the order a bundler tries them: relative to the
    importing file, or through a `tsconfig` alias; as written, with each source suffix, and as
    a directory's index. Only source files inside the repository and outside `node_modules`
    are candidates. Which of them exists is `_first_on_disk`'s question."""
    if specifier.startswith("."):
        bases = [importer.parent / specifier]
    else:
        bases = [target / specifier[len(prefix):]
                 for prefix, targets in project_["aliases"] if prefix and specifier.startswith(prefix)
                 for target in targets]
    found = []
    for base in bases:
        stem = base.with_suffix("") if base.suffix in _SCRIPT_SUFFIXES else base
        for candidate in [base, *(Path(str(stem) + s) for s in _SOURCE_SUFFIXES),
                          *(stem / f"index{s}" for s in _SOURCE_SUFFIXES)]:
            path = Path(os.path.normpath(candidate))
            if (path.suffix in _SOURCE_SUFFIXES and project_["root"] in path.parents
                    and "node_modules" not in path.parts):
                found.append(path)
    return found


@boundary
def _first_on_disk(paths: list[Path]) -> Path | None:
    """The first of these paths that is a file."""
    return next((p for p in paths if p.is_file()), None)


def parameter(fn: Node, index: int, sp: LangSpec) -> Node | None:
    """The NAME a function binds its `index`th argument to, or None when that parameter is
    not one plain name: destructured, gathered by a rest, or not there at all. A typed or a
    defaulted parameter is still one plain name."""
    single = _field(fn, "parameter")
    listed = _field(fn, "parameters")
    params = [single] if single is not None else (
        [c for c in listed.named_children if c.type != "comment"] if listed is not None else [])
    if index >= len(params):
        return None
    node: Node | None = params[index]
    for _ in range(3):
        if node is None or node.type == "identifier":
            return node
        if node.type in sp["destructuring_types"] or "rest" in node.type:
            return None
        node = _field(node, "pattern") or _field(node, "left")
    return None


def binds(fn: Node, name: str, sp: LangSpec) -> bool:
    """Whether a function takes a parameter of this name, so a reference to the name inside
    it means its own parameter and not one from further out."""
    listed = _field(fn, "parameters")
    count = len(listed.named_children) if listed is not None else 1
    return any(p is not None and _text(p) == name for p in (parameter(fn, i, sp) for i in range(count)))

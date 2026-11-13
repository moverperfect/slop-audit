"""Where a plain-name callee lives: in a package, or somewhere this reader still calls ours.

The state reader decides one reference at a time, and a reference handed to a call stopped
there with one of two answers. A name reached through another object was the adopter's
boundary; a bare name was ours, "a builtin missing from the lists, or a function defined in
the repository". In JavaScript a bare name is often neither. `ok(S)` comes from a package under
`node_modules`, which this reader never opens, so filing it as our backlog told the adopter we
could fix it, when only an explicit contract at that boundary would make it decidable.

This module answers that from the file and the project: a callee imported from a package the
project's own `package.json` declares, or from Node's own modules, is a package's.

Everything here is per run, never module state. The project's packages and aliases are carried
in a `Project` built by the caller and dropped when it returns, so the same input gives the
same output and nothing outlives a run. Resolution reads `package.json` and `tsconfig.json`;
it never reads `node_modules`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.boundary import text_or_empty
from l1_analyzer.lang_spec import LangSpec
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


class Project(TypedDict):
    """What one run knows about the repository a reader is in: the packages its manifest
    declares, and `tsconfig`'s `paths`, each pattern split at its `*` into the prefix it
    matches and the directories it maps to. The aliases are the project's own code, so an
    import through one is never a package's, whatever the package names look like."""
    root: Path
    packages: frozenset[str]
    aliases: list[tuple[str, list[Path]]]


class CallContext(TypedDict):
    """One file's calls, readable: the run's project, and what this file imports, as
    {local name: (specifier, imported name)}."""
    project: Project
    imports: dict[str, tuple[str, str]]


def project(repo: Path, sp: LangSpec) -> Project | None:
    """The run's knowledge of the repository, or None for a language whose module system
    this module does not read. Reads `package.json` and `tsconfig.json`, and nothing else."""
    if not sp["module_resolution"]:
        return None
    root = repo.resolve()
    return {"root": root, "packages": packages_in(text_or_empty(repo / "package.json")),
            "aliases": _aliases(root)}


def packages_in(manifest: str) -> frozenset[str]:
    """Every package name a `package.json` declares, across its four dependency tables. A
    manifest that does not parse declares nothing, which leaves every import ours."""
    try:
        data = json.loads(manifest) if manifest else {}
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


def context(project_: Project, root: Node) -> CallContext:
    """One file's calls, readable."""
    return {"project": project_, "imports": imports_in(root)}


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


def imported_from_a_package(call: Node | None, calls: CallContext, sp: LangSpec) -> bool:
    """Whether this call's callee is a plain name the file imports from a package or from
    Node's own modules."""
    fn = _field(call, sp["call_fn"]) if call is not None and not sp["flat_call"] else None
    if fn is None or fn.type != "identifier":
        return False
    imported = calls["imports"].get(_text(fn))
    return imported is not None and is_external(imported[0], calls["project"])


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

"""Finding the files in a repository that define a CI/CD pipeline, for L1.10.

L1.10 reads what those pipelines run (ci_gates); this module finds them. Until 2026-11-12 the
reader looked in `.github/workflows` and nowhere else, so a GitLab, Jenkins or Azure DevOps
project read zero pipelines and banded Slop. An Astro site built, tested and deployed by Azure
Pipelines on every change was told that every merge was a manual act of faith.

AZURE PIPELINES HAS NO FIXED PATH, which is why it takes most of this module. A definition is
`azure-pipelines*.yml` by convention, or a YAML file under a `pipelines/` or `.azure-pipelines/`
directory that opens a pipeline at its top level. The same directories hold TEMPLATES: steps,
jobs and stages another pipeline pulls in with `template:`. A template is a piece of a pipeline,
not a definition of one, so it is read where a definition includes it, with that definition's
parameters, and never as a pipeline of its own.

What this cannot see, said plainly. A pipeline whose definition lives in the CI service rather
than in the repository, which is every classic Azure DevOps release and every Jenkins job
configured in its UI. Nothing in the tree records those, so this reads zero for them.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import TypedDict

from l1_analyzer.boundary import boundary, text_or_empty
from l1_analyzer.scope import _in_ignored_dir, _rglob_files

# The directories Azure DevOps projects keep their pipeline YAML in by convention.
_AZURE_DIRS = frozenset({"pipelines", ".azure-pipelines"})
# The keys that open a pipeline. A template can carry `steps:` or `jobs:` as well, which is why
# a file another pipeline includes is set aside whatever its keys say.
_AZURE_TOP_LEVEL = re.compile(r"^(?:trigger|pr|schedules|resources|stages|jobs|steps|extends)\s*:",
                              re.MULTILINE)
# `- template: path`, with or without the list dash, quotes or a trailing comment. A path naming
# another repository (`x.yml@alias`) or built from an expression (`${{ ... }}`) is not a file in
# this tree and is not matched.
_TEMPLATE_REF = re.compile(r"""^\s*(?:-\s*)?template:\s*['"]?([^'"\s#@$]+)['"]?\s*(?:#.*)?$""",
                           re.MULTILINE)


class Pipelines(TypedDict):
    """The pipeline definitions found, by the system that runs them, each as a path from the
    repository root, and the Azure files set aside as templates, which a definition includes
    rather than runs on its own. ci_gates reads what every definition runs."""
    github: list[str]
    gitlab: list[str]
    jenkins: list[str]
    azure: list[str]
    azure_templates: list[str]


@boundary
def find(repo: Path) -> Pipelines:
    """Every pipeline definition file in the repository, by system.

    GitHub's workflows are read where GitHub runs them, `.github/workflows/*.yml` and `*.yaml`.
    GitLab and Jenkins each read one file at the root, where both look."""
    workflows = repo / ".github" / "workflows"
    definitions, templates = azure_pipeline_definitions(_azure_candidates(repo))
    return {
        "github": sorted(p.relative_to(repo).as_posix()
                         for pattern in ("*.yml", "*.yaml") for p in workflows.glob(pattern)),
        "gitlab": [".gitlab-ci.yml"] if (repo / ".gitlab-ci.yml").is_file() else [],
        "jenkins": ["Jenkinsfile"] if (repo / "Jenkinsfile").is_file() else [],
        "azure": definitions,
        "azure_templates": templates,
    }


def _azure_candidates(repo: Path) -> dict[str, str]:
    """Every YAML file that could be an Azure pipeline, by its path from the root, with its
    text: one named `azure-pipelines*`, or one under a conventional pipeline directory. Read
    through the shared walk, so a `.gitignore`d or vendored tree is not read."""
    found: dict[str, str] = {}
    for pattern in ("*.yml", "*.yaml"):
        for path in _rglob_files(repo, pattern):
            if _in_ignored_dir(path, ()):
                continue
            relative = path.relative_to(repo)
            if relative.name.lower().startswith("azure-pipelines") or set(relative.parts[:-1]) & _AZURE_DIRS:
                found[relative.as_posix()] = text_or_empty(path)
    return found


def azure_pipeline_definitions(files: dict[str, str]) -> tuple[list[str], list[str]]:
    """Which candidate files define a pipeline, and which are templates, each sorted.

    A file another candidate includes with `template:` is a template whatever its keys say.
    Of the rest, a file named `azure-pipelines*` is a definition by convention and any other
    is one when a pipeline key opens at its top level, so a variables file under `pipelines/`
    is neither. A template path is resolved the way Azure resolves it: from the including
    file's directory, or from the repository root when it starts with a slash."""
    included: set[str] = set()
    for path, text in files.items():
        directory = PurePosixPath(path).parent
        for reference in _TEMPLATE_REF.findall(text):
            target = reference.lstrip("/") if reference.startswith("/") else str(directory / reference)
            included.add(posixpath.normpath(target))
    definitions = sorted(
        path for path, text in files.items()
        if path not in included
        and (PurePosixPath(path).name.lower().startswith("azure-pipelines") or _AZURE_TOP_LEVEL.search(text)))
    return definitions, sorted(path for path in files if path in included)


def definitions(found: Pipelines) -> list[str]:
    """Every pipeline definition found, from every system, in a fixed order. Templates are not
    definitions: each is read where a definition includes it."""
    return found["github"] + found["gitlab"] + found["jenkins"] + found["azure"]

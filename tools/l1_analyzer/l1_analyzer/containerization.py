"""L1.11's reading: whether the repository ships a container config, or deploys somewhere none applies.

L1.11 asks whether the repository ships a container or orchestration config, so it runs the same
on every machine. It reads a Dockerfile or docker-compose.yml at the root, by presence alone.

A WRANGLER DEPLOYMENT IS NOT ASKED THAT QUESTION. A Cloudflare Workers or Pages app is deployed
with Wrangler, and the platform runs the code in its own isolate: there is no image to build and
no container to configure. Such a repository has no Dockerfile because its deployment target takes
none, and reading that absence as Slop charged it for not doing something its platform does not
do. So a root Wrangler config (`wrangler.toml`, `wrangler.json` or `wrangler.jsonc`) with no
container file reads n/a, with a sentence saying why, and an n/a row carries no points, so it
drops out of the hygiene score like every other row that did not apply. A repository with both
is measured exactly as one with a container file always was: the container is there to be read.

Wrangler alone, deliberately. Other serverless targets (Vercel, Netlify, AWS SAM) make the same
argument, and each would be a decision of its own about which file proves the target.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from l1_analyzer.boundary import boundary
from l1_analyzer.panel import L1Result

# The container files L1.11 has always read, and the Wrangler configs that name the target.
_CONTAINER_FILES = ("Dockerfile", "docker-compose.yml")
_WRANGLER_CONFIGS = ("wrangler.toml", "wrangler.json", "wrangler.jsonc")


class Found(TypedDict):
    """What sits at the repository root: whether a container file does, and which Wrangler
    configs do, in the order they are looked for."""
    container: bool
    wrangler: list[str]


@boundary
def find(repo: Path) -> Found:
    """The container files and Wrangler configs at the repository root, by name alone."""
    return {"container": any((repo / name).exists() for name in _CONTAINER_FILES),
            "wrangler": [name for name in _WRANGLER_CONFIGS if (repo / name).exists()]}


def reading(found: Found) -> L1Result:
    """L1.11 from what the root holds: present when a container file is there, n/a when only a
    Wrangler config is, and absent when neither is."""
    if found["container"]:
        return {"value": "present and parameterized", "band": "Healthy",
                "details": "a Dockerfile or docker-compose.yml is present at the repository root"}
    if found["wrangler"]:
        return {"value": "n/a", "band": "n/a",
                "details": (f"{found['wrangler'][0]} at the repository root deploys this app with "
                            "Wrangler to Cloudflare Workers or Pages, which runs no container, so "
                            "containerization does not apply to this deployment target")}
    return {"value": "absent", "band": "Slop",
            "details": "no Dockerfile and no docker-compose.yml at the repository root"}

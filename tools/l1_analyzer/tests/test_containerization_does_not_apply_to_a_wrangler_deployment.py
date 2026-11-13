"""L1.11 does not apply to an app deployed with Wrangler, so it reads n/a rather than Slop.

L1.11 asks whether the repository ships a container or orchestration config, so it runs the
same on every machine. A Cloudflare Workers or Pages app is deployed with Wrangler: the platform
runs the code in its own isolate, and there is no image to build. Such a repository has no
Dockerfile because its deployment target takes none, and grading that absence Slop charged it
for not doing something its platform does not do.

So a repository whose root holds a Wrangler config (`wrangler.toml`, `wrangler.json` or
`wrangler.jsonc`) and no Dockerfile or docker-compose.yml reads n/a, with a sentence naming the
config and saying containerization does not apply to that target. An n/a row carries no points,
so it drops out of the hygiene score the way every other n/a row does. A repository with both
a Wrangler config and a container file is measured exactly as before, and so is one with neither.
"""

from __future__ import annotations

import pathlib

import pytest
from l1_analyzer import card, report
from l1_analyzer.indicators import compute_config_indicators


def _l111(tmp_path: pathlib.Path, *names: str) -> dict:
    for name in names:
        (tmp_path / name).write_text("name = 'site'\n" if name.startswith("wrangler") else "FROM scratch\n")
    return compute_config_indicators(tmp_path)["L1.11"]


@pytest.mark.parametrize("config", ["wrangler.toml", "wrangler.json", "wrangler.jsonc"])
def test_a_wrangler_config_without_a_container_reads_not_applicable(tmp_path, config):
    row = _l111(tmp_path, config)
    assert (row["value"], row["band"]) == ("n/a", "n/a")
    assert config in row["details"]
    assert "does not apply" in row["details"]


@pytest.mark.parametrize("container", ["Dockerfile", "docker-compose.yml"])
def test_a_wrangler_config_beside_a_container_is_measured_as_before(tmp_path, container):
    row = _l111(tmp_path, "wrangler.toml", container)
    assert (row["value"], row["band"]) == ("present and parameterized", "Healthy")


def test_a_repository_with_neither_still_reads_absent(tmp_path):
    row = _l111(tmp_path)
    assert (row["value"], row["band"]) == ("absent", "Slop")


def test_a_wrangler_config_below_the_root_is_not_the_repository_s_deployment(tmp_path):
    (tmp_path / "tools").mkdir()
    row = _l111(tmp_path, "tools/wrangler.toml")
    assert row["band"] == "Slop"


def _panel(l111: dict) -> dict:
    healthy = {"value": 1, "band": "Healthy", "details": "x"}
    return {"L1.17": healthy, "L1.15": healthy, "L1.10": healthy, "L1.9": healthy, "L1.16": healthy,
            "L1.11": l111}


def test_the_not_applicable_row_drops_out_of_hygiene(tmp_path):
    """Scored, the absent container would cost a point of weight; dropped, hygiene is the
    other rows' alone, the same as a panel without an L1.11 row at all."""
    not_applicable = _l111(tmp_path, "wrangler.toml")
    without = {k: v for k, v in _panel(not_applicable).items() if k != "L1.11"}
    assert report._hygiene(_panel(not_applicable)) == report._hygiene(without) == 1.0
    assert report._hygiene(_panel({"value": "absent", "band": "Slop", "details": "x"})) < 1.0


def test_the_card_shows_the_row_as_an_unscored_n_a(tmp_path):
    [row] = [r for r in card._metrics(card._AUDIT, _panel(_l111(tmp_path, "wrangler.toml")), "audit")
             if r["tech"].startswith("L1.11")]
    assert (row["value"], row["band"], row["band_word"]) == ("n/a", "n/a", card.band_word("n/a"))

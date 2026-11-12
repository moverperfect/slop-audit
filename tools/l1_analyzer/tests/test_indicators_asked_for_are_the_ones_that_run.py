"""`--indicators 19,20` ran every source indicator, and took as long as the whole audit.

The flag's help says it takes the L1 numbers to run. It chose a STAGE: any source number asked
for the whole source pass, so asking for the two runtime readings also read the repository for
dead code, duplication, secrets, type escapes, whitespace, god files and both state meters
first. On an Astro site on Windows that was about seventy-eight minutes for a question whose
answer was two suite runs. The rows nobody asked for were then printed as well.

Each source indicator now runs only when its number was asked for. L1.18's refinements, the
state classifier, the path cover, the thread surface and the absolute-path check, travel with
18, which is how `--no-state-bounds` already groups them. Asking for nothing in particular runs
everything, in the order it always ran, so a full panel is unchanged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from l1_analyzer import cli, dead_code, indicators, state_bounds


@pytest.fixture
def small_repo(tmp_path: Path) -> Path:
    (tmp_path / "band.py").write_text("def band(n: int) -> str:\n    if n > 10:\n        return 'high'\n    return 'low'\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _refuse(*_args, **_kwargs):
    raise AssertionError("a reading nobody asked for was taken")


def test_asking_for_the_runtime_readings_reads_nothing_else(small_repo, monkeypatch, capsys):
    monkeypatch.setattr(dead_code, "analyze", _refuse)
    monkeypatch.setattr(state_bounds, "classify", _refuse)
    monkeypatch.setattr(indicators, "_god_files", _refuse)

    code = cli.main([str(small_repo), "--no-exec", "--indicators", "19,20", "--format", "json"])

    assert code == 0
    results = json.loads(capsys.readouterr().out)["results"]
    source_rows = sorted(key for key in results if key.startswith("L1.1") and len(key) > 4
                         or key in ("L1.18b", "path_cover", "thread_surface", "absolute_paths"))
    assert source_rows == ["L1.19"], sorted(results)
    assert "L1.20" in results


def test_the_state_meter_brings_its_refinements_with_it(small_repo):
    panel = indicators.compute_source_indicators(
        small_repo, lang="python", exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True,
        python_executable=None, build_args=(), selected=frozenset({"18"}))
    assert [key for key in panel if key != "lang"] == [
        "L1.18", "L1.18b", "path_cover", "thread_surface", "absolute_paths"]


def test_asking_for_everything_runs_everything_in_the_order_it_always_ran(small_repo):
    panel = indicators.compute_source_indicators(
        small_repo, lang="python", exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True,
        python_executable=None, build_args=(), selected=None)
    assert [key for key in panel if key != "lang"] == [
        "L1.16", "L1.17", "L1.18", "L1.15", "L1.12", "L1.14", "L1.13",
        "L1.18b", "path_cover", "thread_surface", "absolute_paths", "L1.19", "L1.20"]

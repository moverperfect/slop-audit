"""`--indicators 19,20` ran every source indicator, and took as long as the whole audit.

The flag's help says it takes the L1 numbers to run. It chose a STAGE: any source number asked
for the whole source pass, so asking for the two runtime readings also read the repository for
dead code, duplication, secrets, type escapes, whitespace, god files and both state meters
first. On an Astro site on Windows that was about seventy-eight minutes for a question whose
answer was two suite runs. The rows nobody asked for were then printed as well.

Each source indicator now runs only when its number was asked for. The refinements, the state
classifier, the path cover, the thread surface and the absolute-path check, carry no number of
their own: they run whenever any static reading is asked for, and are skipped only when the
selection is the runtime pair alone. Asking for nothing in particular runs everything, in the
order it always ran, so a full panel is unchanged.

Every row is written by the line that computes it, so a row that is absent is a reading that was
not taken. The tests read the panel rather than replacing anything inside the package.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from l1_analyzer import cli, indicators

_REFINEMENTS = ["L1.18b", "path_cover", "thread_surface", "absolute_paths"]


@pytest.fixture
def small_repo(tmp_path: Path) -> Path:
    (tmp_path / "band.py").write_text("def band(n: int) -> str:\n    if n > 10:\n        return 'high'\n    return 'low'\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _panel(repo: Path, selected: frozenset[str] | None) -> list[str]:
    panel = indicators.compute_source_indicators(
        repo, lang="python", exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True,
        python_executable=None, build_args=(), selected=selected)
    return [key for key in panel if key != "lang"]


def test_asking_for_the_runtime_readings_reads_nothing_else(small_repo, capsys):
    code = cli.main([str(small_repo), "--no-exec", "--indicators", "19,20", "--format", "json"])

    assert code == 0
    results = json.loads(capsys.readouterr().out)["results"]
    source_rows = sorted(key for key in results
                         if key.startswith("L1.") and int(key[3:5].rstrip("b")) >= 12 or key in _REFINEMENTS)
    assert source_rows == ["L1.19", "L1.20"], sorted(results)


def test_a_static_reading_brings_the_refinements_with_it(small_repo):
    assert _panel(small_repo, frozenset({"17"})) == ["L1.17", *_REFINEMENTS]


def test_asking_for_everything_runs_everything_in_the_order_it_always_ran(small_repo):
    assert _panel(small_repo, None) == [
        "L1.16", "L1.17", "L1.18", "L1.15", "L1.12", "L1.14", "L1.13",
        *_REFINEMENTS, "L1.19", "L1.20"]

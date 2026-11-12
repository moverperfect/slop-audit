"""git's output and a package.json are UTF-8, and were read in whatever the locale said.

The same fault 7fa6dc8 fixed for a test suite's output, in three more readers. git writes
paths and messages as UTF-8, and JSON is UTF-8 by definition, but `text=True` and a bare
`read_text()` decode with the locale's code page, which is cp1252 on a Windows machine. A byte
cp1252 leaves undefined (`❯` carries one) then raises, or loses the output, and the audit ran
on Windows only for somebody who knew to set PYTHONUTF8=1.

Each reader is exercised in a child interpreter with UTF-8 mode switched off, because this
suite itself runs in UTF-8 mode, where the locale question never comes up. On a machine whose
locale is already UTF-8 these pass either way, which is the point: the answer no longer
depends on the machine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_MARK = "❯"   # vitest's failure mark; its UTF-8 bytes include 0x9D, undefined in cp1252


def _in_the_locale(code: str, *args: str) -> str:
    """Run `code` in an interpreter that decodes with the locale, and return what it printed."""
    environment = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    environment["PYTHONIOENCODING"] = "utf-8"   # only the child's own print; not what is under test
    done = subprocess.run([sys.executable, "-X", "utf8=0", "-c", code, *args],
                          capture_output=True, encoding="utf-8", env=environment, check=False)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (("user.email", "a@b.c"), ("user.name", "T"), ("core.quotepath", "false")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)
    return root


def test_git_output_is_read_as_utf8(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"{_MARK} first"], check=True)

    printed = _in_the_locale(
        "import sys; from pathlib import Path; from l1_analyzer.indicators import _run_external;"
        "print(_run_external(['git', 'log', '-1', '--format=%s'], Path(sys.argv[1]))['output'])",
        str(repo))
    assert f"{_MARK} first" in printed


def test_the_history_reader_reads_a_path_git_wrote_unquoted(tmp_path):
    """`core.quotepath false` is a common setting, and with it `git log --numstat` writes a
    non-ASCII path as raw UTF-8."""
    repo = _repo(tmp_path)
    (repo / f"{_MARK}.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "one"], check=True)

    printed = _in_the_locale(
        "import json, sys; from pathlib import Path; from l1_analyzer import git_indicators;"
        "print(json.dumps(git_indicators.compute_git_indicators(Path(sys.argv[1]), None, None)['L1.2']))",
        str(repo))
    assert json.loads(printed)["band"] != "n/a", printed


def test_a_package_json_is_read_as_utf8(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"description": f"{_MARK} a site", "scripts": {"test": "vitest"}}, ensure_ascii=False),
        encoding="utf-8")

    printed = _in_the_locale(
        "import sys; from pathlib import Path; from l1_analyzer import js_trace;"
        "print(js_trace._package_json(Path(sys.argv[1]))['scripts']['test'])",
        str(tmp_path))
    assert printed.strip() == "vitest"

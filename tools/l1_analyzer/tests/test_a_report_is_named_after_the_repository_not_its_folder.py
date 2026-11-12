"""A report is named after the repository it audited, not after the folder it sat in.

`--report` named its files and its heading after the checkout's directory. A git worktree's
directory name is whatever made it: an Astro site audited on 2026-11-12 came back as
`t3-c14f53ce.md`, headed "Slop Audit — t3-c14f53ce". Audited as `.`, which is how this
repository's own hook runs it, the directory name is empty and the files were called `..md`.

The repository says its own name in its `origin` remote, so that is read first: the last
segment of the URL, URL-decoded, `.git` dropped. Only when the audit is of the whole working
copy, because a subdirectory audited on its own is not the repository and must not borrow
its name. With no remote, or no git, the directory's own name, resolved so `.` has one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from l1_analyzer import cli, git_indicators


@pytest.mark.parametrize("url,name", [
    ("git@ssh.dev.azure.com:v3/example-org/Example%20Project/example-site", "example-site"),
    ("https://example-org@dev.azure.com/example-org/Example%20Project/_git/Example%20Site", "Example Site"),
    ("https://github.com/openhonest/slop-audit.git", "slop-audit"),
    ("https://github.com/openhonest/slop-audit/", "slop-audit"),
    ("git@github.com:openhonest/slop-audit.git", "slop-audit"),
    ("C:\\repos\\local-mirror.git", "local-mirror"),
])
def test_the_name_is_the_last_segment_of_the_remote(url, name):
    assert git_indicators.name_from_remote(url) == name


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_a_worktree_folder_reports_under_the_repository_s_name(tmp_path):
    checkout = tmp_path / "t3-c14f53ce"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "remote", "add", "origin", "git@ssh.dev.azure.com:v3/example-org/Example%20Project/example-site")
    assert git_indicators.repository_name(checkout) == "example-site"


def test_a_subdirectory_keeps_its_own_name(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "remote", "add", "origin", "https://github.com/o/whole.git")
    (tmp_path / "part").mkdir()
    assert git_indicators.repository_name(tmp_path / "part") == "part"


def test_without_a_remote_the_folder_name_is_used(tmp_path):
    checkout = tmp_path / "plain"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    assert git_indicators.repository_name(checkout) == "plain"


def test_the_report_files_carry_the_repository_s_name(tmp_path, capsys):
    checkout = tmp_path / "t3-c14f53ce"
    checkout.mkdir()
    (checkout / "a.py").write_text("x = 1\n")
    _git(checkout, "init", "-q")
    _git(checkout, "remote", "add", "origin", "https://github.com/o/real-name.git")
    out = tmp_path / "out"

    assert cli.main([str(checkout), "--no-exec", "--indicators", "9", "--report", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["real-name.html", "real-name.md"]
    assert "real-name" in (out / "real-name.md").read_text(encoding="utf-8").splitlines()[0]

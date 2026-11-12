"""A `.gitignore`d tree is skipped as one entry, not resolved one file at a time.

Every scan in this package goes through `_rglob_files`, and every call asked git for the
repository's ignored paths and resolved each one against the filesystem. git listed every
ignored FILE, so a JavaScript project's `node_modules` came back as one entry per file.

Measured on 2026-11-12 on an Astro site's checkout under Windows: 138,468 ignored files, 128
seconds to resolve them, and about fifty calls in one source pass. The whole pass took 75
minutes; the same pass over a copy of the source with no `node_modules` took 20 seconds for a
third of the files. Almost all of the audit was spent asking the filesystem where files the
audit had already decided not to read were.

git can say it in one line: `--directory` names a wholly ignored directory once. The rule
does not change. A file is skipped when it, or a directory it sits in, is one the project
ignores, and a tracked file inside an ignored directory is still read, because git does not
collapse a directory that holds one.
"""

from __future__ import annotations

import pathlib
import subprocess

from l1_analyzer.scope import _rglob_files


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_large_ignored_tree_is_not_resolved_file_by_file(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("node_modules/\n")
    (repo / "app.ts").write_text("export const a = 1;\n")
    for package in range(30):
        directory = repo / "node_modules" / f"pkg{package}" / "dist"
        directory.mkdir(parents=True)
        for module in range(10):
            (directory / f"m{module}.ts").write_text("export {};\n")

    resolved = 0
    real_resolve = pathlib.Path.resolve

    def counting_resolve(self, strict=False):
        nonlocal resolved
        resolved += 1
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(pathlib.Path, "resolve", counting_resolve)
    found = [p.name for p in _rglob_files(repo, "*.ts")]

    assert found == ["app.ts"]
    assert resolved < 50, f"{resolved} resolutions to skip 300 ignored files"


def test_a_tracked_file_inside_an_ignored_directory_is_still_read(tmp_path):
    """Force-added past its own `.gitignore`, so the project has said this one belongs.
    The ignored file beside it does not."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("gen/\n")
    (repo / "gen").mkdir()
    (repo / "gen" / "kept.py").write_text("x = 1\n")
    (repo / "gen" / "dropped.py").write_text("y = 2\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-f", "gen/kept.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=repo, check=True)

    assert sorted(p.name for p in _rglob_files(repo, "*.py")) == ["kept.py"]


def test_an_ignored_directory_nested_below_a_kept_one_is_skipped(tmp_path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("dist/\n")
    (repo / "pkg" / "dist").mkdir(parents=True)
    (repo / "pkg" / "src.py").write_text("x = 1\n")
    (repo / "pkg" / "dist" / "built.py").write_text("y = 2\n")

    assert sorted(p.name for p in _rglob_files(repo, "*.py")) == ["src.py"]

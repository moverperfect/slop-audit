"""Every runtime reading starts a stranger's suite through one function, and on Windows that
function could not start one.

Three separate faults, all in `pytest_trace._run_untrusted`, and each was enough to lose the
audit rather than one reading of it:

  A bare `npx` is not a program Windows can start. npm installs it as `npx.cmd`, and
  CreateProcess does not consult PATHEXT the way a shell does, so Popen raised
  FileNotFoundError and nothing between it and the CLI caught it. Every JavaScript and
  TypeScript audit with execution on died at its first coverage probe.

  The timeout killed the suite with `os.killpg`, which Windows does not have. The first suite
  that hung raised AttributeError where the kill should have been, so the one path written for
  a runaway suite was the path that took the run down.

  The suite's output was decoded with the console's code page. vitest prints its marks in
  UTF-8, and cp1252 has no character for several of the bytes in them, so the reader thread
  raised and the run's output was lost. Decoding by whatever the locale happens to be also
  made one suite's output read differently on two machines, which a measurement cannot do.

Measured on 2026-11-12 on Windows 11 against an Astro and vitest repository. Each test below
fails there without its fix and passes on every platform with it.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from l1_analyzer.pytest_trace import _run_untrusted


def _launcher(directory: Path, name: str) -> None:
    """A program on PATH that is a script rather than an executable, written the way each
    platform writes one. On Windows that is a .cmd file, which is what npm installs for npx."""
    if os.name == "nt":
        (directory / f"{name}.cmd").write_text(f'@"{sys.executable}" -c "print(\'launched\')"\r\n')
    else:
        script = directory / name
        script.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c "print(\'launched\')"\n')
        script.chmod(0o755)


def test_a_program_installed_as_a_script_is_found_on_the_suites_path(tmp_path):
    """`npx` is spelled bare by every JavaScript route, and the name has to resolve the way a
    shell would resolve it, against the PATH the suite itself is given."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _launcher(bin_dir, "fakenpx")
    path = os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")])

    run = _run_untrusted(["fakenpx"], cwd=tmp_path, env={"PATH": path}, timeout_seconds=60)

    assert run.returncode == 0, run.stderr
    assert "launched" in run.stdout


def test_a_suite_that_hangs_is_stopped_and_reported_as_a_timeout(tmp_path):
    """The kill has to exist on the platform it runs on. The suite here starts a child of its
    own that holds the output pipe open, which is what a test runner's worker pool does: a kill
    that reached only the runner would leave the pipe open and the read below would wait for
    the worker's full sleep."""
    holds_the_pipe = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()

    run = _run_untrusted([sys.executable, "-c", holds_the_pipe], cwd=tmp_path, env={},
                         timeout_seconds=2)

    assert run.returncode == 124
    assert "timed out" in run.stderr
    assert time.monotonic() - started < 30, "the worker outlived the kill and held the pipe open"


def test_a_suites_output_is_read_as_utf8_whatever_the_console_says(tmp_path):
    """vitest marks a failing file with U+276F, whose UTF-8 bytes include 0x9D, a byte cp1252
    leaves undefined; the stray 0xFF is invalid in UTF-8 as well, so the output cannot be read
    strictly under any locale. Read with replacement, the marks survive and the run is not
    lost over one byte nobody needed."""
    prints = "import sys; sys.stdout.buffer.write('\\u2713 ok \\u276f fail \\u00d7'.encode('utf-8') + b' \\xff\\n')"

    run = _run_untrusted([sys.executable, "-c", prints], cwd=tmp_path, env={}, timeout_seconds=60)

    assert run.returncode == 0, run.stderr
    assert "✓ ok ❯ fail ×" in run.stdout
    assert "�" in run.stdout

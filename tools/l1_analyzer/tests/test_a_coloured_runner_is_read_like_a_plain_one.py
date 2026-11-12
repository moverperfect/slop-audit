"""vitest colours its output on Windows whether or not anyone is watching, and the reader
could not see a coloured FAIL line.

vitest's colour library turns colour on unconditionally when the platform is win32, terminal
or pipe. So the output this harness reads on Windows is wrapped in escape codes, `FAIL` sits
behind `\\x1b[41m`, and c900d96's rule, which reads a line that STARTS with the runner's FAIL,
matched nothing. Its fallback then quoted a passing test's line, escape codes and all, into
the published details. Measured on an Astro site on 2026-11-12: L1.20 read

    seed 3: \\x1b[32m✓\\x1b[39m \\x1b[30m\\x1b[42m unit \\x1b[49m\\x1b[39m src/utils/api.test.ts ...

when the run had failed on a ten-second timeout in another file entirely.

Two halves. The runner is asked for no colour (`NO_COLOR`, which vitest and jest both honour),
so the same suite prints the same bytes on every platform; and the reader removes escape codes
before it matches anything, because a runner that ignores the request must not be able to put
them in a published sentence.
"""

from __future__ import annotations

from l1_analyzer import js_trace
from l1_analyzer.pytest_trace import _first_line

_E = "\x1b"

# The shape of the real run: a passing test whose name mentions a failure, the failed test's
# own line, the runner's FAIL line, and the summary, each as vitest colours it on Windows.
_COLOURED = (
    f" {_E}[32m✓{_E}[39m {_E}[30m{_E}[42m unit {_E}[49m{_E}[39m src/utils/api.test.ts"
    f"{_E}[2m > {_E}[22mreturns ConfigurationError when getClient fails{_E}[32m 3{_E}[2mms{_E}[22m\n"
    f" {_E}[31m×{_E}[39m {_E}[30m{_E}[42m unit {_E}[49m{_E}[39m pipelines/scripts/parse-playwright-junit.test.ts"
    f"{_E}[2m > {_E}[22ma missing or empty report cannot report success: undefined{_E}[33m 21622{_E}[2mms{_E}[22m\n"
    f"{_E}[41m{_E}[1m FAIL {_E}[22m{_E}[49m {_E}[30m{_E}[42m unit {_E}[49m{_E}[39m "
    f"pipelines/scripts/parse-playwright-junit.test.ts{_E}[2m > {_E}[22ma missing or empty report "
    f"cannot report success: undefined\n"
    f"{_E}[31mError: Test timed out in 10000ms.{_E}[39m\n"
    f"{_E}[2m Test Files {_E}[22m {_E}[1m{_E}[31m1 failed{_E}[39m{_E}[22m{_E}[2m | {_E}[22m"
    f"{_E}[1m{_E}[32m124 passed{_E}[39m{_E}[22m{_E}[90m (125){_E}[39m\n"
)


def test_a_coloured_fail_line_is_the_one_quoted():
    assert js_trace._failure_summary(_COLOURED) == (
        "FAIL   unit  pipelines/scripts/parse-playwright-junit.test.ts > "
        "a missing or empty report cannot report success: undefined")


def test_no_escape_code_reaches_a_published_line():
    """Whatever line is chosen, including the fallback, carries no escape code."""
    assert _E not in js_trace._failure_summary(_COLOURED.replace("FAIL", "BAIL"))
    assert _first_line(f"{_E}[31mError: boom{_E}[39m") == "Error: boom"


def test_the_runner_is_asked_for_no_colour():
    """Every run this harness starts carries the request, so a suite prints the same bytes on
    a Windows laptop as in a Linux container."""
    assert js_trace._RUN_ENVIRONMENT == {"NO_COLOR": "1"}

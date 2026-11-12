"""L1.20's failure line quoted a test that passed.

It took the first output line containing "fail". vitest's verbose reporter prints every
passing test by name, so on an Astro site audited on 2026-10-29 it quoted a passing test
whose name said "failed", and left out the test that had timed out. The runner's own FAIL line
names the failing test, and its summary counts them, so those are read first.
"""

from __future__ import annotations

from l1_analyzer import js_trace

_VITEST_VERBOSE = """\
 RUN  v4.1.12 C:/work/site

 ✓  unit  src/utils/fetch.test.ts > returns the failed state when the request fails 3ms
 ×  unit  src/ui/dialog.test.ts > opens the dialog when the module fails to load 1071ms
   → Timed out in 1000ms.

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL   unit  src/ui/dialog.test.ts > opens the dialog when the module fails to load
Error: Timed out in 1000ms.

 Test Files  1 failed | 10 passed (11)
      Tests  1 failed | 100 passed (101)
"""


def test_the_failure_line_names_the_test_that_failed_not_one_that_passed():
    assert js_trace._failure_summary(_VITEST_VERBOSE) == (
        "FAIL   unit  src/ui/dialog.test.ts > opens the dialog when the module fails to load")


def test_jest_s_failure_line_is_read_the_same_way():
    out = ("PASS src/a.test.js\n  ✓ reports a failed login (2 ms)\n"
           "FAIL src/b.test.js\n  ● parses › rejects bad input\n"
           "Tests:       1 failed, 7 passed, 8 total\n")
    assert js_trace._failure_summary(out) == "FAIL src/b.test.js"


def test_a_crash_with_no_runner_lines_still_names_what_failed():
    out = " RUN  v4.1.12 /work\n\nError: Failed to load url ./missing (resolved id: ./missing)\n"
    assert js_trace._failure_summary(out) == "Error: Failed to load url ./missing (resolved id: ./missing)"

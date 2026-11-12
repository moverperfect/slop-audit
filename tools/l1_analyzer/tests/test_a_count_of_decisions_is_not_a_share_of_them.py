"""The card printed a count of decisions as a share of them.

"Decision-space coverage: 1443.0% of decisions exercised by the suite", on the card for an
Astro site whose coverage was never measured. When the runtime half of L1.19 cannot run, the
row it leaves behind is the static half: the NUMBER of decision points, 1,443, with band n/a
and a sentence saying coverage was not measured. The card's pairing read any number in that
row as a percentage. It is told apart by its band now, which is what says whether a share was
measured: the coverage verdict always bands a share, and the static count never has one.
"""

from __future__ import annotations

from l1_analyzer import card

_STATIC_ROW = {
    "value": 1443,
    "band": "n/a",
    "details": ("1443 finite decision points enumerated across 200 files; the share a test "
                "exercises is a different number and needs a test-execution trace; coverage not "
                "measured: needs c8 for coverage (npm i -D c8)"),
}


def test_a_count_of_decision_points_is_not_printed_as_coverage():
    pair = card._coverage_pair({"L1.19": _STATIC_ROW}, ran_tests=True)
    assert pair is not None
    assert pair["measured"] is False
    assert pair["value"] is None
    assert "needs c8" in pair["reason"]


def test_a_measured_share_is_still_printed():
    row = {"value": 81.4, "band": "Not Healthy", "details": "814/1000 decision branches exercised"}
    assert card._coverage_pair({"L1.19": row}, ran_tests=True) == {
        "measured": True, "value": 81.4, "reason": ""}

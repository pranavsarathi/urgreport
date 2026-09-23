"""
Tests for DiffAnalyzer, Before/After Comparison, and Gap Resolution Tracking.
"""

from urg_engine import (
    CoverageScore, CoverageReport, CoverageGap, TestbenchModel,
    DiffAnalyzer, BeforeAfterComparison
)


def make_dummy_report(score: float, line: float, gaps: list[str]) -> CoverageReport:
    return CoverageReport(
        design_name="dut",
        rtl_filename="dut.v",
        tb_filename="dut_tb.v",
        timestamp="2026-09-23 12:00:00",
        total_summary=CoverageScore(
            score=score,
            line_cov=line,
            cond_cov=60.0,
            toggle_cov=50.0,
            fsm_cov=None,
            branch_cov=55.0
        ),
        tb_model=TestbenchModel(),
        gaps=[CoverageGap(title=g, description="desc", severity="HIGH", evidence="ev", suggested_action="act") for g in gaps]
    )


def test_first_run_no_previous():
    rep = make_dummy_report(65.0, 70.0, ["Gap A", "Gap B"])
    diff = DiffAnalyzer.compare(None, rep)
    assert diff.has_previous is False
    assert diff.score_after == 65.0
    assert diff.score_delta == 0.0
    assert len(diff.remaining_gaps) == 2
    assert len(diff.resolved_gaps) == 0


def test_second_run_gap_resolution_and_positive_delta():
    rep1 = make_dummy_report(60.0, 50.0, ["Gap A", "Gap B", "Gap C"])
    rep2 = make_dummy_report(85.0, 80.0, ["Gap C"])

    diff = DiffAnalyzer.compare(rep1, rep2)
    assert diff.has_previous is True
    assert diff.score_before == 60.0
    assert diff.score_after == 85.0
    assert diff.score_delta == 25.0
    assert diff.line_delta == 30.0

    # Resolved gaps: Gap A and Gap B are gone
    assert "Gap A" in diff.resolved_gaps
    assert "Gap B" in diff.resolved_gaps
    assert "Gap C" in diff.remaining_gaps
    assert len(diff.new_gaps) == 0


def test_new_gap_introduction():
    rep1 = make_dummy_report(70.0, 70.0, ["Gap A"])
    rep2 = make_dummy_report(65.0, 60.0, ["Gap A", "New Gap X"])

    diff = DiffAnalyzer.compare(rep1, rep2)
    assert diff.score_delta == -5.0
    assert "New Gap X" in diff.new_gaps
    assert "Gap A" in diff.remaining_gaps

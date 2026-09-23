"""
Before / After Analysis and Run Diffing Engine.
Compares sequential analysis runs to track verification progress, coverage deltas,
and resolved versus remaining verification gaps.
"""

from typing import Optional, List, Set
from .ast_nodes import CoverageReport, BeforeAfterComparison


class DiffAnalyzer:
    @staticmethod
    def compare(previous: Optional[CoverageReport], current: CoverageReport) -> BeforeAfterComparison:
        """Compares previous and current reports, generating exact deltas and gap resolution list."""
        if not previous:
            return BeforeAfterComparison(
                has_previous=False,
                previous_timestamp="",
                score_before=0.0,
                score_after=current.total_summary.score or 0.0,
                score_delta=0.0,
                line_delta=0.0,
                cond_delta=0.0,
                toggle_delta=0.0,
                fsm_delta=None,
                branch_delta=0.0,
                total_gaps_before=0,
                total_gaps_after=len(current.gaps),
                resolved_gaps=[],
                remaining_gaps=[g.title for g in current.gaps],
                new_gaps=[]
            )

        prev_sum = previous.total_summary
        curr_sum = current.total_summary

        score_before = prev_sum.score or 0.0
        score_after = curr_sum.score or 0.0
        score_delta = round(score_after - score_before, 1)

        line_delta = round(curr_sum.line_cov - prev_sum.line_cov, 1)
        cond_delta = round(curr_sum.cond_cov - prev_sum.cond_cov, 1)
        toggle_delta = round(curr_sum.toggle_cov - prev_sum.toggle_cov, 1)
        branch_delta = round(curr_sum.branch_cov - prev_sum.branch_cov, 1)

        fsm_delta = None
        if curr_sum.fsm_cov is not None and prev_sum.fsm_cov is not None:
            fsm_delta = round(curr_sum.fsm_cov - prev_sum.fsm_cov, 1)
        elif curr_sum.fsm_cov is not None:
            fsm_delta = curr_sum.fsm_cov

        # Compare gaps
        prev_gap_titles = {g.title for g in previous.gaps}
        curr_gap_titles = {g.title for g in current.gaps}

        resolved_gaps = sorted(list(prev_gap_titles - curr_gap_titles))
        remaining_gaps = sorted(list(prev_gap_titles & curr_gap_titles))
        new_gaps = sorted(list(curr_gap_titles - prev_gap_titles))

        return BeforeAfterComparison(
            has_previous=True,
            previous_timestamp=previous.timestamp,
            score_before=score_before,
            score_after=score_after,
            score_delta=score_delta,
            line_delta=line_delta,
            cond_delta=cond_delta,
            toggle_delta=toggle_delta,
            fsm_delta=fsm_delta,
            branch_delta=branch_delta,
            total_gaps_before=len(previous.gaps),
            total_gaps_after=len(current.gaps),
            resolved_gaps=resolved_gaps,
            remaining_gaps=remaining_gaps,
            new_gaps=new_gaps
        )

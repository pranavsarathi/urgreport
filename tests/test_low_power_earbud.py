"""
Tests for low_power_earbud Reference Design and Before/After Verification Workflow.
"""

from pathlib import Path
from urg_engine import (
    VerilogParser, TestbenchAnalyzer, CoverageAnalyzer,
    DiffAnalyzer
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "low_power_earbud"


def test_low_power_earbud_analysis_flow():
    rtl_path = EXAMPLES_DIR / "low_power_earbud.v"
    tb_init_path = EXAMPLES_DIR / "low_power_earbud_tb.v"
    tb_enh_path = EXAMPLES_DIR / "low_power_earbud_tb_enhanced.v"

    assert rtl_path.exists()
    assert tb_init_path.exists()
    assert tb_enh_path.exists()

    rtl_code = rtl_path.read_text(encoding="utf-8")
    tb_init_code = tb_init_path.read_text(encoding="utf-8")
    tb_enh_code = tb_enh_path.read_text(encoding="utf-8")

    # Run 1: Initial Testbench
    parser = VerilogParser(filename="low_power_earbud.v")
    design = parser.parse(rtl_code)

    tb_analyzer = TestbenchAnalyzer(filename="low_power_earbud_tb.v")
    tb1_model = tb_analyzer.analyze(tb_init_code, design=design)

    cov_analyzer = CoverageAnalyzer()
    rep1 = cov_analyzer.analyze(design, tb1_model, rtl_code, tb_init_code)

    # Initial run should flag wake_irq gap
    wake_irq_gap = next((g for g in rep1.gaps if "wake_irq" in g.title), None)
    assert wake_irq_gap is not None
    assert wake_irq_gap.severity == "HIGH"
    assert wake_irq_gap.finding_id is not None

    # Check finding details for the gap
    finding = next((f for f in rep1.findings if f.id == wake_irq_gap.finding_id), None)
    assert finding is not None
    assert finding.confidence == "HIGH"
    assert len(finding.suggested_stimulus_snippet) > 0

    # Run 2: Enhanced Testbench
    tb2_model = tb_analyzer.analyze(tb_enh_code, design=design)
    rep2 = cov_analyzer.analyze(design, tb2_model, rtl_code, tb_enh_code)

    # In Run 2, wake_irq should be checked
    wake_irq_check = next((c for c in tb2_model.output_checks if c.dut_output == "wake_irq"), None)
    assert wake_irq_check is not None
    assert wake_irq_check.is_verified is True

    # Diff analysis between Run 1 and Run 2
    diff = DiffAnalyzer.compare(rep1, rep2)
    assert diff.has_previous is True
    assert diff.score_delta > 0
    assert any("wake_irq" in g for g in diff.resolved_gaps)

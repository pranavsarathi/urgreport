"""
Tests for Multi-File RTL Parsing, Hierarchy Detection, and Partial Analysis Resilience.
"""

from pathlib import Path
from urg_engine import VerilogParser, TestbenchAnalyzer, CoverageAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = BASE_DIR / "examples" / "pipeline_datapath"


def test_parse_multi_file_pipeline():
    fetch_code = (PIPELINE_DIR / "fetch.v").read_text(encoding="utf-8")
    decode_code = (PIPELINE_DIR / "decode.v").read_text(encoding="utf-8")
    execute_code = (PIPELINE_DIR / "execute.v").read_text(encoding="utf-8")
    top_code = (PIPELINE_DIR / "pipeline_top.v").read_text(encoding="utf-8")

    files = [
        ("fetch.v", fetch_code),
        ("decode.v", decode_code),
        ("execute.v", execute_code),
        ("pipeline_top.v", top_code)
    ]

    design = VerilogParser.parse_files(files)

    # 4 modules parsed
    assert len(design.modules) == 4
    module_names = {m.name for m in design.modules}
    assert module_names == {"fetch", "decode", "execute", "pipeline_top"}

    # Top module is pipeline_top
    assert design.top_module == "pipeline_top"
    assert design.hierarchy is not None
    assert design.hierarchy.module_name == "pipeline_top"
    assert design.hierarchy.is_top is True

    # 3 children under top module
    children_names = {c.module_name for c in design.hierarchy.children}
    assert children_names == {"fetch", "decode", "execute"}


def test_multi_file_full_coverage_analysis():
    fetch_code = (PIPELINE_DIR / "fetch.v").read_text(encoding="utf-8")
    decode_code = (PIPELINE_DIR / "decode.v").read_text(encoding="utf-8")
    execute_code = (PIPELINE_DIR / "execute.v").read_text(encoding="utf-8")
    top_code = (PIPELINE_DIR / "pipeline_top.v").read_text(encoding="utf-8")
    tb_code = (PIPELINE_DIR / "pipeline_tb.v").read_text(encoding="utf-8")

    files = [
        ("fetch.v", fetch_code),
        ("decode.v", decode_code),
        ("execute.v", execute_code),
        ("pipeline_top.v", top_code)
    ]

    design = VerilogParser.parse_files(files)
    tba = TestbenchAnalyzer("pipeline_tb.v")
    tb = tba.analyze(tb_code, design=design)

    ca = CoverageAnalyzer()
    raw_rtl = "\n\n".join(c for _, c in files)
    report = ca.analyze(design, tb, raw_rtl, tb_code)

    assert report.design_name == "pipeline_top"
    assert report.top_module == "pipeline_top"
    assert len(report.design_files) == 4
    assert len(report.modules) == 4
    assert report.scores.overall_score > 0
    assert len(report.findings) > 0


def test_partial_analysis_resilience():
    good_code = """
    module good_mod (input clk, input d, output reg q);
        always @(posedge clk) q <= d;
    endmodule
    """
    broken_code = """
    module broken_mod (input clk, input a
        // Missing closing parenthesis and semicolon, syntax error
        always @(posedge clk
    """

    files = [
        ("good.v", good_code),
        ("broken.v", broken_code)
    ]

    design = VerilogParser.parse_files(files)

    # Should not crash! Good module parsed, broken marked as partial
    assert len(design.modules) == 2
    good_m = next(m for m in design.modules if m.name == "good_mod")
    assert good_m.partial_analysis is False

    broken_m = next(m for m in design.modules if m.name == "broken_mod")
    assert broken_m.partial_analysis is True
    assert "Syntax error" in broken_m.partial_reason

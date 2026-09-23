"""
Comprehensive Test Suite for URG Pre-Simulation RTL & Testbench Coverage Engine.
"""

import pytest
from urg_engine.tokenizer import VerilogLexer, TokenStream
from urg_engine.verilog_parser import VerilogParser, VerilogParserError
from urg_engine.testbench_analyzer import TestbenchAnalyzer, normalize_val
from urg_engine.coverage_analyzer import CoverageAnalyzer
from urg_engine.exporter import ReportExporter


def test_tokenizer_basic():
    code = """
    // Single line comment
    /* Multi line
       comment */
    `timescale 1ns/1ps
    module test #(parameter WIDTH = 8) (input clk, input [WIDTH-1:0] data_in, output reg [7:0] data_out);
        always @(posedge clk) begin
            if (data_in == 8'hFF)
                data_out <= 8'd0;
            else
                data_out <= data_in + 1'b1;
        end
    endmodule
    """
    lexer = VerilogLexer(code)
    tokens = lexer.tokenize()
    assert len(tokens) > 20
    assert any(t.value == "module" for t in tokens)
    assert any(t.value == "test" for t in tokens)
    assert any(t.value == "parameter" for t in tokens)
    assert any(t.value == "posedge" for t in tokens)
    assert any(t.value == "8'hFF" for t in tokens)


def test_number_normalization():
    assert normalize_val("3'b010") == "2"
    assert normalize_val("8'hFF") == "255"
    assert normalize_val("8'h0A") == "10"
    assert normalize_val("4'd12") == "12"
    assert normalize_val("0") == "0"
    assert normalize_val("1") == "1"


def test_alu_rtl_parsing():
    rtl = open("examples/alu_8bit/alu_8bit.v").read()
    parser = VerilogParser("alu_8bit.v")
    design = parser.parse(rtl)

    assert len(design.modules) == 1
    mod = design.modules[0]
    assert mod.name == "alu_8bit"

    port_names = {p.name for p in mod.ports}
    assert "clk" in port_names
    assert "reset" in port_names
    assert "A" in port_names
    assert "B" in port_names
    assert "opcode" in port_names
    assert "result" in port_names
    assert "overflow" in port_names

    # Check widths
    p_a = next(p for p in mod.ports if p.name == "A")
    assert p_a.width == "[7:0]"

    # Check case statements and branches
    assert len(mod.case_statements) == 1
    assert mod.case_statements[0].expr == "opcode"
    assert len(mod.case_statements[0].items) >= 8

    # ALU opcode should NOT be classified as an FSM
    assert mod.fsm is None


def test_counter_rtl_parsing():
    rtl = open("examples/counter_4bit/counter_4bit.v").read()
    parser = VerilogParser("counter_4bit.v")
    design = parser.parse(rtl)

    assert len(design.modules) == 1
    mod = design.modules[0]
    assert mod.name == "counter_4bit"

    # Verify if/else branches
    assert len(mod.branches) >= 4
    assert len(mod.conditions) >= 2


def test_fsm_traffic_detection():
    rtl = open("examples/fsm_traffic/fsm_traffic.v").read()
    parser = VerilogParser("fsm_traffic.v")
    design = parser.parse(rtl)

    mod = design.modules[0]
    assert mod.fsm is not None
    assert mod.fsm.state_reg == "state"
    assert "IDLE" in mod.fsm.detected_states
    assert "RED" in mod.fsm.detected_states
    assert "EMERGENCY" in mod.fsm.detected_states
    assert mod.fsm.confidence in ("High", "Medium")


def test_testbench_analysis_alu():
    rtl = open("examples/alu_8bit/alu_8bit.v").read()
    tb = open("examples/alu_8bit/alu_8bit_tb.v").read()

    p = VerilogParser("alu_8bit.v")
    design = p.parse(rtl)

    tba = TestbenchAnalyzer("alu_8bit_tb.v")
    tb_model = tba.analyze(tb, design=design)

    # DUT instance detected
    assert len(tb_model.dut_instances) == 1
    assert tb_model.dut_instances[0].module_name == "alu_8bit"

    # Clock detected
    assert len(tb_model.clocks) == 1
    assert tb_model.clocks[0].signal_name == "clk"

    # Reset detected
    assert len(tb_model.resets) == 1
    assert tb_model.resets[0].signal_name == "reset"
    assert tb_model.resets[0].asserted is True
    assert tb_model.resets[0].released is True

    # Output checks: result checked, overflow unchecked
    chk_lookup = {c.dut_output: c for c in tb_model.output_checks}
    assert "result" in chk_lookup
    assert chk_lookup["result"].is_verified is True
    assert chk_lookup["overflow"].check_type == "NONE"


def test_coverage_and_gaps_alu():
    rtl = open("examples/alu_8bit/alu_8bit.v").read()
    tb = open("examples/alu_8bit/alu_8bit_tb.v").read()

    p = VerilogParser("alu_8bit.v")
    design = p.parse(rtl)

    tba = TestbenchAnalyzer("alu_8bit_tb.v")
    tb_model = tba.analyze(tb, design=design)

    ca = CoverageAnalyzer()
    report = ca.analyze(design, tb_model, raw_rtl=rtl, raw_tb=tb)

    # Total score should be non-empty and strictly < 100% due to missing cases
    assert report.total_summary.score is not None
    assert 50.0 < report.total_summary.score < 100.0
    assert report.total_summary.fsm_cov is None  # FSM is N/A for ALU

    # Gap checks
    high_gaps = [g for g in report.gaps if g.severity == "HIGH"]
    med_gaps = [g for g in report.gaps if g.severity == "MEDIUM"]

    assert any("overflow" in g.title for g in high_gaps)
    assert any("3'b111" in g.title or "SHR" in g.description for g in med_gaps)


def test_export_html_and_json():
    rtl = open("examples/alu_8bit/alu_8bit.v").read()
    tb = open("examples/alu_8bit/alu_8bit_tb.v").read()

    p = VerilogParser("alu_8bit.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("alu_8bit_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    report = ca.analyze(design, tb_model, raw_rtl=rtl, raw_tb=tb)

    json_str = ReportExporter.to_json(report)
    assert '"design_name": "alu_8bit"' in json_str

    html_str = ReportExporter.to_standalone_html(report)
    assert "URG REPORT FOR RTL CODE" in html_str
    assert "alu_8bit" in html_str
    assert "POTENTIAL COVERAGE GAPS" in html_str

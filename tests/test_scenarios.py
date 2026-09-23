"""
Direct test coverage for the 8 required test cases specified in the requirements:
1. Simple counter
2. 8-bit ALU
3. FSM
4. RTL with if/else
5. RTL with case
6. RTL with missing TB stimulus
7. RTL with unobserved output
8. Malformed Verilog
"""

import pytest
from urg_engine import (
    VerilogParser, TestbenchAnalyzer, CoverageAnalyzer,
    VerilogParserError
)


# 1. Simple Counter
def test_scenario_1_simple_counter():
    rtl = open("examples/counter_4bit/counter_4bit.v").read()
    tb = open("examples/counter_4bit/counter_4bit_tb.v").read()

    p = VerilogParser("counter_4bit.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("counter_4bit_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    assert rep.design_name == "counter_4bit"
    assert rep.total_summary.score > 0


# 2. 8-bit ALU
def test_scenario_2_alu_8bit():
    rtl = open("examples/alu_8bit/alu_8bit.v").read()
    tb = open("examples/alu_8bit/alu_8bit_tb.v").read()

    p = VerilogParser("alu_8bit.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("alu_8bit_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    assert rep.design_name == "alu_8bit"
    assert len(rep.branches) >= 8
    assert rep.total_summary.score < 100.0  # Intentional omissions detected


# 3. FSM
def test_scenario_3_fsm():
    rtl = open("examples/fsm_traffic/fsm_traffic.v").read()
    tb = open("examples/fsm_traffic/fsm_traffic_tb.v").read()

    p = VerilogParser("fsm_traffic.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("fsm_traffic_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    assert rep.total_summary.fsm_cov is not None
    assert rep.modules[0].fsm is not None
    assert len(rep.modules[0].fsm.detected_states) == 5


# 4. RTL with if/else
def test_scenario_4_if_else():
    rtl = """
    module if_test (input clk, input sel, input [7:0] a, b, output reg [7:0] y);
        always @(posedge clk) begin
            if (sel)
                y <= a;
            else
                y <= b;
        end
    endmodule
    """
    tb = """
    module if_test_tb;
        reg clk, sel;
        reg [7:0] a, b;
        wire [7:0] y;
        if_test dut (.clk(clk), .sel(sel), .a(a), .b(b), .y(y));
        always #5 clk = ~clk;
        initial begin
            clk = 0; sel = 1; a = 8'hAA; b = 8'h55; #10;
            // sel = 0 is never tested
            if (y !== 8'hAA) $display("fail");
            #20; $finish;
        end
    endmodule
    """
    p = VerilogParser("if_test.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("if_test_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    # sel=1 tested, sel=0 untested
    assert len(rep.branches) == 2
    assert rep.branches[0].status == "COVERED"
    assert rep.branches[1].status == "POTENTIALLY_UNTESTED"


# 5. RTL with case
def test_scenario_5_case():
    rtl = """
    module case_test (input [1:0] mode, output reg [3:0] out);
        always @* begin
            case (mode)
                2'b00: out = 4'd1;
                2'b01: out = 4'd2;
                2'b10: out = 4'd4;
                default: out = 4'd8;
            endcase
        end
    endmodule
    """
    tb = """
    module case_test_tb;
        reg [1:0] mode;
        wire [3:0] out;
        case_test dut (.mode(mode), .out(out));
        initial begin
            mode = 2'b00; #10;
            mode = 2'b01; #10;
            // 2'b10 never driven
            if (out != 4'd2) $display("err");
            #10;
        end
    endmodule
    """
    p = VerilogParser("case_test.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("case_test_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    case_items = rep.case_statements[0].items
    assert case_items[0].stimulated is True  # 2'b00
    assert case_items[1].stimulated is True  # 2'b01
    assert case_items[2].stimulated is False # 2'b10


# 6. RTL with missing TB stimulus
def test_scenario_6_missing_tb_stimulus():
    rtl = """
    module stim_test (input clk, input reset, input [7:0] data, output reg [7:0] q);
        always @(posedge clk) begin
            if (reset) q <= 0;
            else q <= data;
        end
    endmodule
    """
    tb = """
    module stim_test_tb;
        reg clk;
        // reset and data never driven
        wire [7:0] q;
        stim_test dut (.clk(clk), .reset(1'b0), .data(8'h00), .q(q));
        always #5 clk = ~clk;
        initial begin clk = 0; #50; end
    endmodule
    """
    p = VerilogParser("stim_test.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("stim_test_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    # Identifies missing reset stimulus gap
    assert any("Reset" in g.title for g in rep.gaps)


# 7. RTL with unobserved output
def test_scenario_7_unobserved_output():
    rtl = """
    module unobs_test (input clk, input [7:0] a, output reg [7:0] sum, output reg flag_err);
        always @(posedge clk) begin
            sum <= a + 1;
            flag_err <= (a == 8'hFF);
        end
    endmodule
    """
    tb = """
    module unobs_test_tb;
        reg clk; reg [7:0] a; wire [7:0] sum; wire flag_err;
        unobs_test dut (.clk(clk), .a(a), .sum(sum), .flag_err(flag_err));
        always #5 clk = ~clk;
        initial begin
            clk = 0; a = 8'h10; #10;
            if (sum !== 8'h11) $display("mismatch");
            // flag_err is NEVER checked
            #20;
        end
    endmodule
    """
    p = VerilogParser("unobs_test.v")
    design = p.parse(rtl)
    tba = TestbenchAnalyzer("unobs_test_tb.v")
    tb_model = tba.analyze(tb, design=design)
    ca = CoverageAnalyzer()
    rep = ca.analyze(design, tb_model, rtl, tb)

    # flag_err should be reported as unchecked HIGH gap
    high_gaps = [g for g in rep.gaps if g.severity == "HIGH"]
    assert any("flag_err" in g.title for g in high_gaps)


# 8. Malformed Verilog
def test_scenario_8_malformed_verilog():
    # Missing end / unexpected tokens
    malformed_rtl = """
    module bad_syntax (input clk, output reg q);
        always @(posedge clk) begin
            q <= 1
    // missing semicolon, missing end, missing endmodule
    """
    p = VerilogParser("bad_syntax.v")
    # Parser should safely finish or report clean AST without crashing
    design = p.parse(malformed_rtl)
    assert isinstance(design.modules, list)

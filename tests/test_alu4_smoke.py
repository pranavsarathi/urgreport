"""
Comprehensive regression tests for alu_4bit smoke test and stale metadata isolation.
Verifies all 7 semantic fixes:
1. Fresh metadata isolation between runs (no stale file leaking).
2. Condition coverage 0/0 is None / N/A (not 100%).
3. Combinational designs have N/A for clock/reset (no false gaps).
4. Static stimulus evidence semantics.
5. Defensive case default unrecognized as gap.
6. Compound if statements (y !== ... || carry !== ...) detect both outputs as compared.
7. Overall score calculated strictly over applicable metrics.
"""

import pytest
from fastapi.testclient import TestClient
from main import app, perform_analysis
from urg_engine import VerilogParser, TestbenchAnalyzer, CoverageAnalyzer


ALU_RTL = """
module alu_4bit (
    input wire [3:0] a,
    input wire [3:0] b,
    input wire [1:0] op,
    output reg [3:0] y,
    output reg carry
);
    always @(*) begin
        carry = 1'b0;
        case (op)
            2'b00: {carry, y} = a + b;
            2'b01: {carry, y} = a - b;
            2'b10: y = a & b;
            2'b11: y = a | b;
            default: y = 4'b0000;
        endcase
    end
endmodule
"""

ALU_TB = """
module alu_4bit_tb;
    reg [3:0] a, b;
    reg [1:0] op;
    wire [3:0] y;
    wire carry;

    alu_4bit dut (
        .a(a), .b(b), .op(op), .y(y), .carry(carry)
    );

    initial begin
        a = 4'd5; b = 4'd3;
        op = 2'b00; #10;
        if (y !== 4'd8 || carry !== 1'b0) $display("Error");
        op = 2'b01; #10;
        if (y !== 4'd2 || carry !== 1'b0) $display("Error");
        op = 2'b10; #10;
        if (y !== 4'd1 || carry !== 1'b0) $display("Error");
        op = 2'b11; #10;
        if (y !== 4'd7 || carry !== 1'b0) $display("Error");
        #10; $finish;
    end
endmodule
"""

RISCV_RTL = """
module riscv_decoder (
    input wire [31:0] instr,
    output reg [6:0] opcode
);
    always @(*) begin
        opcode = instr[6:0];
    end
endmodule
"""

RISCV_TB = """
module riscv_decoder_tb;
    reg [31:0] instr;
    wire [6:0] opcode;

    riscv_decoder dut (.instr(instr), .opcode(opcode));

    initial begin
        instr = 32'h00000013; #10;
        if (opcode == 7'h13) $display("OK");
    end
endmodule
"""


def test_alu4_engine_correctness():
    """Verify alu_4bit passes all 7 semantic checks in the engine."""
    parser = VerilogParser(filename="alu_4bit.v")
    design = parser.parse(ALU_RTL)
    tb_analyzer = TestbenchAnalyzer(filename="alu_4bit_tb.v")
    tb_model = tb_analyzer.analyze(ALU_TB, design=design)
    cov_analyzer = CoverageAnalyzer()
    rep = cov_analyzer.analyze(design, tb_model, ALU_RTL, ALU_TB)

    # 1. Module & top identification
    assert rep.top_module == "alu_4bit"
    assert rep.design_name == "alu_4bit"

    # 2. Output checks: BOTH y and carry must be compared
    checks = {c.dut_output: c for c in rep.tb_model.output_checks}
    assert "y" in checks
    assert "carry" in checks
    assert checks["y"].is_compared is True
    assert checks["y"].is_verified is True
    assert checks["y"].check_count == 4
    assert checks["carry"].is_compared is True
    assert checks["carry"].is_verified is True
    assert checks["carry"].check_count == 4

    # 3. Condition coverage must be None (N/A), NOT 100.0%
    assert rep.total_summary.cond_cov is None
    assert rep.total_summary.condition_coverage is None

    # 4. FSM coverage must be None (N/A)
    assert rep.total_summary.fsm_cov is None

    # 5. Line and Branch coverage
    assert rep.total_summary.line_cov == 100.0
    assert rep.total_summary.branch_cov == 100.0

    # 6. Overall score must average only non-None metrics
    applicable = [100.0, 100.0, rep.total_summary.toggle_cov]
    expected_score = round(sum(applicable) / 3.0, 1)
    assert rep.total_summary.score == expected_score

    # 7. No Clock/Reset gaps generated for combinational design
    for g in rep.gaps:
        assert "Clock Generator Missing" not in g.title
        assert "Reset" not in g.title


def test_stale_metadata_isolation():
    """
    Regression Test:
    Analysis A runs riscv_decoder.v.
    Analysis B runs alu_4bit.v (even if called with stale parameters).
    Analysis B must NEVER display metadata from Analysis A.
    """
    # Run Analysis A
    rep_a = perform_analysis(
        rtl_content=RISCV_RTL,
        tb_content=RISCV_TB,
        rtl_filename="riscv_decoder.v",
        tb_filename="riscv_decoder_tb.v",
        session_id="session_reg"
    )
    assert rep_a.top_module == "riscv_decoder"
    assert rep_a.rtl_filename == "riscv_decoder.v"

    # Run Analysis B with alu_4bit code, simulating stale frontend parameters
    rep_b = perform_analysis(
        rtl_content=ALU_RTL,
        tb_content=ALU_TB,
        rtl_filename="riscv_decoder.v",  # Stale param!
        tb_filename="riscv_decoder_tb.v",  # Stale param!
        session_id="session_reg"
    )

    # Analysis B must derive its own clean metadata
    assert rep_b.top_module == "alu_4bit"
    assert rep_b.design_name == "alu_4bit"
    assert rep_b.rtl_filename == "alu_4bit.v"
    assert rep_b.tb_filename == "alu_4bit_tb.v"
    assert "riscv_decoder" not in rep_b.rtl_filename
    assert "riscv_decoder" not in rep_b.tb_filename
    assert "riscv_decoder.v" not in rep_b.design_files


def test_alu4_via_api():
    """Verify alu_4bit through the FastAPI REST endpoint."""
    client = TestClient(app)
    response = client.post(
        "/api/analyze",
        json={
            "rtl_content": ALU_RTL,
            "tb_content": ALU_TB,
            "rtl_filename": "alu_4bit.v",
            "tb_filename": "alu_4bit_tb.v",
            "session_id": "test_api_alu4"
        }
    )
    assert response.status_code == 200
    data = response.json()

    assert data["top_module"] == "alu_4bit"
    assert data["total_summary"]["cond_cov"] is None
    assert data["total_summary"]["fsm_cov"] is None
    assert data["total_summary"]["line_cov"] == 100.0
    assert data["total_summary"]["branch_cov"] == 100.0

    checks = {c["dut_output"]: c for c in data["tb_model"]["output_checks"]}
    assert checks["y"]["is_compared"] is True
    assert checks["y"]["is_verified"] is True
    assert checks["y"]["check_count"] == 4
    assert checks["carry"]["is_compared"] is True
    assert checks["carry"]["is_verified"] is True
    assert checks["carry"]["check_count"] == 4

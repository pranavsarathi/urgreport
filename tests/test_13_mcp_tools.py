"""
Tests for all 13 Model Context Protocol (MCP) verification tools via FastAPI.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_RTL = """
module mcp_full_test (
    input wire clk,
    input wire rst_n,
    input wire enable,
    input wire [3:0] in_data,
    output reg [3:0] out_data,
    output wire alert
);
    assign alert = (out_data == 4'hF);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_data <= 4'h0;
        end else if (enable) begin
            out_data <= in_data;
        end
    end
endmodule
"""

SAMPLE_TB = """
module mcp_full_test_tb;
    reg clk;
    reg rst_n;
    reg enable;
    reg [3:0] in_data;
    wire [3:0] out_data;
    wire alert;

    mcp_full_test dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .in_data(in_data),
        .out_data(out_data),
        .alert(alert)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0; rst_n = 0; enable = 0; in_data = 4'h0;
        #20; rst_n = 1; #10;
        @(posedge clk);
        enable = 1; in_data = 4'h5;
        @(posedge clk);
        enable = 0;
        #20;
        if (out_data !== 4'h5) $display("Mismatch");
        #20; $finish;
    end
endmodule
"""


def test_all_13_mcp_tools():
    # Tool 1: analyze_design
    res = client.post("/api/mcp/execute", json={
        "tool": "analyze_design",
        "arguments": {
            "rtl_content": SAMPLE_RTL,
            "tb_content": SAMPLE_TB,
            "rtl_filename": "mcp_full_test.v",
            "tb_filename": "mcp_full_test_tb.v"
        },
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200, res.text
    summary = res.json()
    assert summary["status"] == "success"
    assert summary["top_module"] == "mcp_full_test"

    # Tool 2: get_design_summary
    res = client.post("/api/mcp/execute", json={
        "tool": "get_design_summary",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert res.json()["top_module"] == "mcp_full_test"

    # Tool 3: get_modules
    res = client.post("/api/mcp/execute", json={
        "tool": "get_modules",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    mods = res.json()["modules"]
    assert len(mods) == 1
    assert mods[0]["name"] == "mcp_full_test"

    # Tool 4: get_module
    res = client.post("/api/mcp/execute", json={
        "tool": "get_module",
        "arguments": {"module_name": "mcp_full_test"},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert res.json()["name"] == "mcp_full_test"

    # Tool 6: get_findings
    res = client.post("/api/mcp/execute", json={
        "tool": "get_findings",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    findings = res.json()["findings"]
    assert len(findings) > 0
    target_fid = findings[0]["id"]

    # Tool 5: get_finding
    res = client.post("/api/mcp/execute", json={
        "tool": "get_finding",
        "arguments": {"finding_id": target_fid},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert res.json()["id"] == target_fid

    # Tool 7: get_source_context
    res = client.post("/api/mcp/execute", json={
        "tool": "get_source_context",
        "arguments": {"file_type": "rtl", "line": 5, "window": 3},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert "lines" in res.json()

    # Tool 8: get_fsm
    res = client.post("/api/mcp/execute", json={
        "tool": "get_fsm",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200

    # Tool 9: get_dataflow
    res = client.post("/api/mcp/execute", json={
        "tool": "get_dataflow",
        "arguments": {"signal_name": "out_data"},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert "signal" in res.json()

    # Tool 10: get_signal_evidence
    res = client.post("/api/mcp/execute", json={
        "tool": "get_signal_evidence",
        "arguments": {"signal_name": "alert"},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert res.json()["dut_port"] == "alert"

    # Tool 11: get_verification_gaps
    res = client.post("/api/mcp/execute", json={
        "tool": "get_verification_gaps",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert "gaps" in res.json()

    # Tool 12: suggest_test
    res = client.post("/api/mcp/execute", json={
        "tool": "suggest_test",
        "arguments": {"finding_id": target_fid},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    assert "stimulus_snippet" in res.json()

    # Tool 13: compare_analysis
    res = client.post("/api/mcp/execute", json={
        "tool": "compare_analysis",
        "arguments": {},
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200

"""
Tests for Structured MCP Interface and REST Endpoints.
"""

from fastapi.testclient import TestClient
from main import app, perform_analysis
from urg_engine import URGToolInterface, VerilogParser, TestbenchAnalyzer, CoverageAnalyzer


client = TestClient(app)


def test_mcp_tools_list_endpoint():
    res = client.get("/api/mcp/tools")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    tools = [t["name"] for t in data["tools"]]
    assert "analyze_rtl" in tools
    assert "analyze_testbench" in tools
    assert "get_finding" in tools
    assert "suggest_test_scenario" in tools
    assert "compare_analysis" in tools


def test_mcp_execute_analyze_rtl():
    rtl = """
    module mcp_test (input clk, input d, output reg q);
        always @(posedge clk) q <= d;
    endmodule
    """
    res = client.post("/api/mcp/execute", json={
        "tool": "analyze_rtl",
        "arguments": {"rtl_content": rtl, "rtl_filename": "mcp_test.v"}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["top_module"] == "mcp_test"
    assert data["modules_count"] == 1


def test_mcp_execute_analyze_testbench():
    tb = """
    module mcp_test_tb;
        reg clk, d;
        wire q;
        mcp_test dut (.clk(clk), .d(d), .q(q));
        always #5 clk = ~clk;
        initial begin clk = 0; d = 0; #10 d = 1; #20 $finish; end
    endmodule
    """
    res = client.post("/api/mcp/execute", json={
        "tool": "analyze_testbench",
        "arguments": {"tb_content": tb, "tb_filename": "mcp_test_tb.v"}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "dut" in data["dut_instances"]
    assert "clk" in data["clocks_detected"]


def test_examples_catalog_includes_earbud():
    res = client.get("/api/examples")
    assert res.status_code == 200
    examples = res.json()
    ids = [e["id"] for e in examples]
    assert "low_power_earbud" in ids
    assert "low_power_earbud_enhanced" in ids

    # Test loading the example
    res_ex = client.get("/api/examples/low_power_earbud")
    assert res_ex.status_code == 200
    ex_data = res_ex.json()
    assert "low_power_earbud" in ex_data["rtl_filename"]
    assert "wake_irq" in ex_data["rtl_content"]


def test_finding_retrieval_and_session_reset():
    rtl = """
    module earbud (input clk, input sound_valid, output reg wake_irq);
        always @(posedge clk) begin
            if (sound_valid) wake_irq <= 1'b1;
        end
    endmodule
    """
    tb = """
    module earbud_tb;
        reg clk, sound_valid;
        wire wake_irq;
        earbud dut (.clk(clk), .sound_valid(sound_valid), .wake_irq(wake_irq));
        always #5 clk = ~clk;
        initial begin clk = 0; sound_valid = 1; #20 sound_valid = 0; #50 $finish; end
    endmodule
    """
    # Analyze with session
    res = client.post("/api/analyze", json={
        "rtl_content": rtl,
        "tb_content": tb,
        "rtl_filename": "earbud.v",
        "tb_filename": "earbud_tb.v",
        "session_id": "test_mcp_session"
    })
    assert res.status_code == 200
    rep = res.json()
    assert len(rep["findings"]) > 0
    first_fid = rep["findings"][0]["id"]

    # Test finding lookup endpoint
    res_find = client.get(f"/api/finding/{first_fid}?session_id=test_mcp_session")
    assert res_find.status_code == 200
    find_data = res_find.json()
    assert find_data["id"] == first_fid

    # Test MCP tool: suggest_test_scenario
    res_sug = client.post("/api/mcp/execute", json={
        "tool": "suggest_test_scenario",
        "arguments": {"finding_id": first_fid},
        "session_id": "test_mcp_session"
    })
    assert res_sug.status_code == 200
    sug_data = res_sug.json()
    assert "suggested_stimulus_snippet" in sug_data

    # Test session reset
    res_reset = client.post("/api/session/reset?session_id=test_mcp_session")
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "success"

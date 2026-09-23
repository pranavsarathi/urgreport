"""
Tests for Smart FSM Analysis, Reset Reachability, and Transition Graph Modeling.
"""

from urg_engine import VerilogParser, TestbenchAnalyzer, CoverageAnalyzer


def test_reset_reachability_inference():
    rtl = """
    module fsm_dev (
        input clk,
        input rst_n,
        input start,
        output reg ready
    );
        reg [1:0] state;
        parameter IDLE = 2'b00, BUSY = 2'b01, DONE = 2'b10;

        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                state <= IDLE;
                ready <= 1'b0;
            end else begin
                case (state)
                    IDLE: if (start) state <= BUSY;
                    BUSY: state <= DONE;
                    DONE: state <= IDLE;
                endcase
            end
        end
    endmodule
    """

    tb = """
    module fsm_dev_tb;
        reg clk, rst_n, start;
        wire ready;

        fsm_dev dut (.clk(clk), .rst_n(rst_n), .start(start), .ready(ready));

        always #5 clk = ~clk;

        initial begin
            clk = 0;
            rst_n = 0;  // Assert active-low reset
            start = 0;
            #20 rst_n = 1; // Release reset
            #100 $finish;
        end
    endmodule
    """

    parser = VerilogParser()
    design = parser.parse(rtl)
    tb_analyzer = TestbenchAnalyzer()
    tb_model = tb_analyzer.analyze(tb, design=design)
    cov_analyzer = CoverageAnalyzer()
    report = cov_analyzer.analyze(design, tb_model, rtl, tb)

    mod = report.modules[0]
    assert mod.fsm is not None
    assert "IDLE" in mod.fsm.detected_states

    # Check that IDLE state is marked as reachable via reset assertion
    idle_reach = next((r for r in mod.fsm.reachability if r.state_name == "IDLE"), None)
    assert idle_reach is not None
    assert idle_reach.is_reachable is True
    assert "reset" in idle_reach.evidence.lower()

    # Check graph nodes and edges
    assert len(mod.fsm.graph.nodes) == len(mod.fsm.detected_states)
    assert len(mod.fsm.graph.edges) > 0

    # The reset node should have is_reachable=True
    reset_node = next((n for n in mod.fsm.graph.nodes if n.id == "IDLE"), None)
    assert reset_node is not None
    assert reset_node.is_reachable is True

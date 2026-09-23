"""
Tests for Dataflow Analyzer, Parameter Resolution, and Stimulus Generation.
"""

from urg_engine.dataflow_analyzer import DataflowAnalyzer
from urg_engine.ast_nodes import ModuleModel, Port, Parameter, Branch, Condition, ConditionTerm


def test_parameter_resolution():
    code = """
    parameter WIDTH = 8;
    parameter MAX_COUNT = 16;
    localparam THRESHOLD = 4;
    localparam HEX_VAL = 8'hA0;
    localparam BIN_VAL = 4'b1010;
    """
    params = DataflowAnalyzer.extract_parameters(code)
    assert params["WIDTH"] == 8
    assert params["MAX_COUNT"] == 16
    assert params["THRESHOLD"] == 4
    assert params["HEX_VAL"] == 0xA0
    assert params["BIN_VAL"] == 10


def test_counter_boundary_analysis():
    mod = ModuleModel(
        name="test_mod",
        start_line=1,
        end_line=50,
        ports=[Port(name="clk", direction="input"), Port(name="valid", direction="input")],
        parameters=[
            Parameter(name="WINDOW_SIZE", default_value="16"),
            Parameter(name="THRESHOLD", default_value="4")
        ]
    )
    analyzer = DataflowAnalyzer(mod)

    # Test boundary detection for counter comparison
    boundaries = analyzer.analyze_counter_boundaries("sample_count >= THRESHOLD")
    assert len(boundaries) > 0
    assert any("4" in b for b in boundaries)

    # Test rollover comparison
    boundaries_rollover = analyzer.analyze_counter_boundaries("sample_count == WINDOW_SIZE - 1")
    assert len(boundaries_rollover) > 0
    assert any("15" in b for b in boundaries_rollover)


def test_dependency_chain_tracing():
    raw_rtl = """
    module earbud (
        input clk,
        input sound_valid,
        output reg wake_irq
    );
        parameter ACTIVITY_THRESHOLD = 4;
        reg [3:0] sound_counter;

        always @(posedge clk) begin
            if (sound_valid)
                sound_counter <= sound_counter + 1;
            if (sound_counter >= ACTIVITY_THRESHOLD)
                wake_irq <= 1'b1;
        end
    endmodule
    """
    mod = ModuleModel(
        name="earbud",
        start_line=1,
        end_line=80,
        ports=[
            Port(name="clk", direction="input"),
            Port(name="sound_valid", direction="input"),
            Port(name="wake_irq", direction="output")
        ],
        parameters=[Parameter(name="ACTIVITY_THRESHOLD", default_value="4")]
    )
    analyzer = DataflowAnalyzer(mod, raw_rtl=raw_rtl)
    chain = analyzer.trace_signal_origin("sound_counter >= 4")
    assert len(chain) >= 1
    assert any("sound_valid" in c or "sound_counter" in c for c in chain)


def test_verilog_stimulus_generation():
    mod = ModuleModel(
        name="test_unit",
        start_line=1,
        end_line=40,
        ports=[Port(name="clk", direction="input"), Port(name="enable", direction="input")]
    )
    analyzer = DataflowAnalyzer(mod)
    snippet = analyzer.generate_stimulus_snippet("enable", "enable == 1'b1")
    assert "enable" in snippet
    assert "1'b1" in snippet
    assert "clk" in snippet

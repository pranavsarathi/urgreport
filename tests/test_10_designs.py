"""
Tests for General Verification Across 10 Diverse Reference Designs.
Verifies that analysis is completely domain-agnostic, stable, and produces meaningful coverage metrics.
"""

from pathlib import Path
from urg_engine import VerilogParser, TestbenchAnalyzer, CoverageAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = BASE_DIR / "examples"


def run_design_analysis(rtl_rel: str, tb_rel: str):
    rtl_path = EXAMPLES_DIR / rtl_rel
    tb_path = EXAMPLES_DIR / tb_rel

    assert rtl_path.exists(), f"RTL file not found: {rtl_path}"
    assert tb_path.exists(), f"TB file not found: {tb_path}"

    rtl_code = rtl_path.read_text(encoding="utf-8")
    tb_code = tb_path.read_text(encoding="utf-8")

    parser = VerilogParser(filename=rtl_path.name)
    design = parser.parse(rtl_code)

    tba = TestbenchAnalyzer(filename=tb_path.name)
    tb_model = tba.analyze(tb_code, design=design)

    ca = CoverageAnalyzer()
    report = ca.analyze(design, tb_model, rtl_code, tb_code)

    assert report.total_rtl_lines > 0
    assert report.total_tb_lines > 0
    assert len(report.findings) > 0
    assert report.scores.overall_score >= 0.0
    return report


def test_design_1_alu_8bit():
    rep = run_design_analysis("alu_8bit/alu_8bit.v", "alu_8bit/alu_8bit_tb.v")
    assert rep.design_name == "alu_8bit"
    # TB omits opcode SHR and overflow check
    assert any(g.category == "BRANCH" or g.category == "OUTPUT_CHECK" for g in rep.gaps)


def test_design_2_counter_4bit():
    rep = run_design_analysis("counter_4bit/counter_4bit.v", "counter_4bit/counter_4bit_tb.v")
    assert rep.design_name == "counter_4bit"
    # Count down is omitted in TB
    assert any("up_down" in g.description or "BRANCH" in g.category for g in rep.gaps)


def test_design_3_fsm_traffic():
    rep = run_design_analysis("fsm_traffic/fsm_traffic.v", "fsm_traffic/fsm_traffic_tb.v")
    assert rep.design_name == "fsm_traffic"
    assert rep.scores.fsm_coverage > 0
    # Emergency transition untested
    assert any("EMERGENCY" in g.description or "FSM" in g.category for g in rep.gaps)


def test_design_4_low_power_earbud():
    rep = run_design_analysis("low_power_earbud/low_power_earbud.v", "low_power_earbud/low_power_earbud_tb.v")
    assert rep.design_name == "low_power_earbud"
    assert any(g.category == "OUTPUT_CHECK" and "wake_irq" in g.description for g in rep.gaps)


def test_design_5_fifo_sync():
    rep = run_design_analysis("fifo_sync/fifo_sync.v", "fifo_sync/fifo_sync_tb.v")
    assert rep.design_name == "fifo_sync"
    # Full flag boundary not reached with 3 writes
    assert any("full" in g.description.lower() or "OUTPUT_CHECK" in g.category for g in rep.gaps)


def test_design_6_uart_tx():
    rep = run_design_analysis("uart_tx/uart_tx.v", "uart_tx/uart_tx_tb.v")
    assert rep.design_name == "uart_tx"
    # FSM detected
    top_mod = rep.modules[0]
    assert top_mod.fsm is not None
    assert set(top_mod.fsm.detected_states) == {"STATE_IDLE", "STATE_START", "STATE_DATA", "STATE_STOP"}
    assert rep.scores.fsm_coverage > 50.0


def test_design_7_spi_master():
    rep = run_design_analysis("spi_master/spi_master.v", "spi_master/spi_master_tb.v")
    assert rep.design_name == "spi_master"
    top_mod = rep.modules[0]
    assert top_mod.fsm is not None
    assert "IDLE" in top_mod.fsm.detected_states
    assert rep.scores.overall_score > 40.0


def test_design_8_riscv_decoder():
    rep = run_design_analysis("riscv_decoder/riscv_decoder.v", "riscv_decoder/riscv_decoder_tb.v")
    assert rep.design_name == "riscv_decoder"
    # Branch coverage: some opcodes tested, others untested
    assert rep.scores.branch_coverage > 0
    assert rep.scores.branch_coverage < 100.0


def test_design_9_reg_file():
    rep = run_design_analysis("reg_file/reg_file.v", "reg_file/reg_file_tb.v")
    assert rep.design_name == "reg_file"
    assert rep.scores.overall_score > 50.0


def test_design_10_pwm_controller():
    rep = run_design_analysis("pwm_controller/pwm_controller.v", "pwm_controller/pwm_controller_tb.v")
    assert rep.design_name == "pwm_controller"
    assert len(rep.signals) > 0

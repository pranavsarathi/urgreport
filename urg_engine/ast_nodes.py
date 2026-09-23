"""
Data structures and AST models for URG Pre-Simulation RTL & Testbench Analysis.
Includes Unified Evidence Model, Dataflow Tracking, Smart FSM, and Before/After Diff.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Port(BaseModel):
    name: str
    direction: str  # 'input', 'output', 'inout'
    width: str = "[0:0]"
    data_type: str = "wire"
    line: int = 1


class Signal(BaseModel):
    name: str
    data_type: str  # 'reg', 'wire', 'logic', 'integer'
    width: str = "[0:0]"
    line: int = 1


class Parameter(BaseModel):
    name: str
    default_value: str = ""
    line: int = 1


class AlwaysBlock(BaseModel):
    block_type: str  # 'always', 'always_ff', 'always_comb', 'always_latch'
    sensitivity: str  # e.g., 'posedge clk or negedge reset'
    start_line: int
    end_line: int
    is_clocked: bool = False
    clock_signal: Optional[str] = None
    reset_signal: Optional[str] = None


class ContinuousAssign(BaseModel):
    target: str
    expr: str
    line: int


class Branch(BaseModel):
    id: str
    branch_type: str  # 'if_then', 'if_else', 'case_item', 'case_default'
    condition_expr: str
    line: int
    start_line: int
    end_line: int
    stimulated_true: bool = False
    stimulated_false: bool = False
    status: str = "POTENTIALLY_UNTESTED"  # 'COVERED', 'POTENTIALLY_UNTESTED', 'PARTIAL'
    finding_id: Optional[str] = None


class ConditionTerm(BaseModel):
    variable: str
    comparison_op: str
    target_value: str
    stimulated_high: bool = False
    stimulated_low: bool = False
    details: str = ""


class TruthTableRow(BaseModel):
    combination: str  # e.g. "enable=1, valid=1"
    expected_outcome: str  # "TRUE", "FALSE"
    status: str  # '✓ STIMULUS EVIDENCE FOUND', '⚠ POTENTIALLY UNTESTED', '? INSUFFICIENT EVIDENCE'
    evidence_detail: str = ""


class Condition(BaseModel):
    id: str
    line: int
    raw_expression: str
    terms: List[ConditionTerm] = []
    missing_scenarios: List[str] = []
    status: str = "POTENTIALLY_UNTESTED"  # 'COVERED', 'PARTIALLY_TESTED', 'POTENTIALLY_UNTESTED'
    truth_table: List[TruthTableRow] = []
    boundary_variable: Optional[str] = None
    boundary_threshold: Optional[str] = None
    inferred_range: Optional[str] = None
    finding_id: Optional[str] = None


class CaseItem(BaseModel):
    label: str
    values: List[str] = []
    start_line: int
    end_line: int
    stimulated: bool = False
    is_default: bool = False
    finding_id: Optional[str] = None


class CaseStatement(BaseModel):
    id: str
    line: int
    expr: str
    case_type: str = "case"  # 'case', 'casex', 'casez'
    items: List[CaseItem] = []
    has_default: bool = False
    default_line: Optional[int] = None
    total_branches: int = 0
    stimulated_branches: int = 0


class FsmTransition(BaseModel):
    from_state: str
    to_state: str
    condition_expr: str = ""
    trigger_condition: str = ""
    evidence: str = ""
    status: str = "NO_EVIDENCE"  # 'EVIDENCE_FOUND', 'UNCERTAIN', 'NO_EVIDENCE'
    line: int = 1
    finding_id: Optional[str] = None


class FsmStateReachability(BaseModel):
    state_name: str
    state_value: str = ""
    reachable: bool = False
    is_reachable: bool = False
    reachability_evidence: str = "NO_EVIDENCE"  # 'RESET_ASSERTION', 'TRANSITION_STIMULUS', 'NO_EVIDENCE'
    evidence: str = ""
    reason: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if "is_reachable" in data and not self.reachable:
            self.reachable = data["is_reachable"]
        if "reachable" in data and not self.is_reachable:
            self.is_reachable = data["reachable"]
        if "evidence" in data and not self.reachability_evidence:
            self.reachability_evidence = data["evidence"]
        if "reachability_evidence" in data and not self.evidence:
            self.evidence = data["reachability_evidence"]


class FsmGraphNode(BaseModel):
    id: str
    label: str
    status: str = "NO_EVIDENCE"  # 'EVIDENCE_FOUND', 'UNCERTAIN', 'NO_EVIDENCE'
    is_reset_state: bool = False
    is_reachable: bool = False


class FsmGraphEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str
    status: str = "NO_EVIDENCE"  # 'EVIDENCE_FOUND', 'UNCERTAIN', 'NO_EVIDENCE'
    line: int = 1
    finding_id: Optional[str] = None


class FsmModel(BaseModel):
    state_reg: str
    detected_states: List[str] = []
    reset_state: Optional[str] = None
    state_reachability: List[FsmStateReachability] = []
    transitions: List[FsmTransition] = []
    graph_nodes: List[FsmGraphNode] = []
    graph_edges: List[FsmGraphEdge] = []
    confidence: str = "High"  # 'High', 'Medium', 'Low', 'None'
    stimulus_evidence: str = ""

    @property
    def reachability(self) -> List[FsmStateReachability]:
        return self.state_reachability

    @property
    def graph(self) -> Any:
        class _GraphWrapper:
            def __init__(self, nodes, edges):
                self.nodes = nodes
                self.edges = edges
        return _GraphWrapper(self.graph_nodes, self.graph_edges)


class EvidenceItem(BaseModel):
    source: str = "RTL_STRUCTURE"  # 'RTL_STRUCTURE', 'TB_ASSIGNMENT', 'TB_TRANSITION', 'DUT_CONNECTION', 'RESET_BEHAVIOR', 'CLOCK_BEHAVIOR', 'DATAFLOW', 'CONTROL_FLOW', 'CASE_ITEM', 'ASSERTION', 'OUTPUT_OBSERVATION', 'MONITOR', 'DISPLAY', 'COMPARISON'
    type: str = "INFERENCE"  # 'STIMULUS', 'OBSERVATION', 'STRUCTURAL', 'INFERENCE'
    location: str = ""  # e.g. "tb.v:45" or "rtl.v:12"
    observed_value: Optional[str] = None
    inferred_value: Optional[str] = None
    relationship: str = ""
    confidence: str = "HIGH"  # 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
    explanation: str = ""


class ModuleInstantiation(BaseModel):
    module_name: str
    instance_name: str
    connections: List["TBPortConnection"] = []
    line: int = 1
    file: str = ""


class HierarchyNode(BaseModel):
    module_name: str
    instance_name: str = ""
    file: str = ""
    is_top: bool = False
    children: List["HierarchyNode"] = []


class ModuleModel(BaseModel):
    name: str
    filename: str = ""
    start_line: int = 1
    end_line: int = 1
    ports: List[Port] = []
    signals: List[Signal] = []
    parameters: List[Parameter] = []
    always_blocks: List[AlwaysBlock] = []
    continuous_assigns: List[ContinuousAssign] = []
    branches: List[Branch] = []
    conditions: List[Condition] = []
    case_statements: List[CaseStatement] = []
    fsm: Optional[FsmModel] = None
    executable_lines: List[int] = []
    instantiations: List[ModuleInstantiation] = []
    is_top: bool = False
    partial_analysis: bool = False
    partial_reason: str = ""


class DesignModel(BaseModel):
    modules: List[ModuleModel] = []
    top_module: Optional[str] = None
    filename: str = ""
    files: List[str] = []
    hierarchy: Optional[HierarchyNode] = None
    total_rtl_lines: int = 0


# Testbench Models
class TBPortConnection(BaseModel):
    port_name: str
    tb_expr: str
    line: int = 1


class DUTInstance(BaseModel):
    module_name: str
    instance_name: str
    connections: List[TBPortConnection] = []
    line: int = 1


class ClockGenerator(BaseModel):
    signal_name: str
    period: float = 10.0
    frequency_mhz: Optional[float] = None
    duty_cycle: float = 50.0
    source_type: str = "ALWAYS"  # 'ALWAYS', 'INITIAL', 'CONTINUOUS'
    pattern: str = ""
    line: int = 1


class ResetSequence(BaseModel):
    signal_name: str
    polarity: str = "ACTIVE_HIGH"  # 'ACTIVE_HIGH', 'ACTIVE_LOW'
    reset_type: str = "ASYNCHRONOUS"  # 'ASYNCHRONOUS', 'SYNCHRONOUS'
    asserted: bool = False
    released: bool = False
    line: int = 1


class StimulusAssignment(BaseModel):
    signal_name: str
    value: str
    time_delay: Optional[int] = None
    line: int = 1


class SignalToggle(BaseModel):
    signal_name: str
    values_seen: List[str] = []
    has_0_to_1: bool = False
    has_1_to_0: bool = False
    status: str = "NONE"  # 'FULL', 'LIMITED', 'NONE'


class OutputCheck(BaseModel):
    dut_output: str
    check_type: str  # 'ASSERTION', 'IF_CHECK', 'DISPLAY', 'MONITOR', 'NONE'
    details: str = ""
    line: int = 1
    is_verified: bool = False
    is_compared: bool = False
    is_asserted: bool = False
    is_displayed: bool = False
    check_count: int = 0
    verification_status: str = "UNCHECKED"  # 'VERIFIED_ASSERTION', 'VERIFIED_COMPARISON', 'OBSERVED_DISPLAY', 'UNCHECKED'
    finding_id: Optional[str] = None


class TestbenchModel(BaseModel):
    __test__ = False
    dut_instances: List[DUTInstance] = []
    clocks: List[ClockGenerator] = []
    resets: List[ResetSequence] = []
    stimulus: List[StimulusAssignment] = []
    toggles: Dict[str, SignalToggle] = {}
    output_checks: List[OutputCheck] = []
    initial_blocks_count: int = 0
    always_blocks_count: int = 0
    tasks_count: int = 0
    total_assertions: int = 0
    filename: str = ""
    raw_text: str = ""


# Unified Evidence Model: Powers the [ WHY? ] signature feature
class Finding(BaseModel):
    id: str  # e.g., 'FIND-COND-03', 'FIND-BR-02', 'FIND-FSM-01', 'FIND-OUT-01'
    category: str = "GENERAL"  # 'CONDITION', 'BRANCH', 'FSM_TRANSITION', 'OUTPUT_CHECK', 'RESET', 'DATAFLOW', 'CLOCK', 'CASE', 'ASSERTION', 'DUT/TB MAPPING'
    title: str = ""
    expression: str = ""
    rtl_file: str = "rtl.v"
    rtl_line: int = 1
    rtl_column: Optional[int] = None
    module: str = ""
    statement: str = ""
    tb_file: str = "testbench.v"
    tb_line: Optional[int] = None
    what_was_found: str = ""
    description: str = ""
    where_found: str = ""
    tb_evidence: str = ""
    tb_evidence_status: str = "⚠ POTENTIALLY UNTESTED"
    tb_evidence_details: str = ""
    dataflow_chain: List[str] = []
    evidence_items: List[EvidenceItem] = []
    source_context: List[str] = []
    reasoning: str = ""
    confidence: str = "HIGH"  # 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'
    status: str = "POTENTIALLY_UNTESTED"
    severity: str = "MEDIUM"  # 'INFO', 'LOW', 'MEDIUM', 'HIGH'
    recommendation: str = ""
    suggested_action: str = ""
    suggested_scenario: str = ""
    suggested_next_scenario: str = ""
    stimulus_snippet: str = ""
    suggested_stimulus_snippet: str = ""

    def __init__(self, **data):
        if "description" in data and "what_was_found" not in data:
            data["what_was_found"] = data["description"]
        elif "what_was_found" in data and "description" not in data:
            data["description"] = data["what_was_found"]

        if "suggested_next_scenario" in data and "suggested_scenario" not in data:
            data["suggested_scenario"] = data["suggested_next_scenario"]
        elif "suggested_scenario" in data and "suggested_next_scenario" not in data:
            data["suggested_next_scenario"] = data["suggested_scenario"]

        if "suggested_action" in data and "recommendation" not in data:
            data["recommendation"] = data["suggested_action"]
        elif "recommendation" in data and "suggested_action" not in data:
            data["suggested_action"] = data["recommendation"]

        if "suggested_stimulus_snippet" in data and "stimulus_snippet" not in data:
            data["stimulus_snippet"] = data["suggested_stimulus_snippet"]
        elif "stimulus_snippet" in data and "suggested_stimulus_snippet" not in data:
            data["suggested_stimulus_snippet"] = data["stimulus_snippet"]

        if "tb_evidence_details" in data and "tb_evidence" not in data:
            data["tb_evidence"] = data["tb_evidence_details"]
        elif "tb_evidence" in data and "tb_evidence_details" not in data:
            data["tb_evidence_details"] = data["tb_evidence"]

        if "tb_evidence_status" in data and "status" not in data:
            data["status"] = data["tb_evidence_status"]
        elif "status" in data and "tb_evidence_status" not in data:
            data["tb_evidence_status"] = data["status"]

        super().__init__(**data)


# Coverage and Report Models
class CoverageScore(BaseModel):
    score: Optional[float] = None
    line_cov: float = 0.0
    cond_cov: Optional[float] = None  # None indicates N/A
    toggle_cov: float = 0.0
    fsm_cov: Optional[float] = None  # None indicates N/A
    branch_cov: float = 0.0

    @property
    def overall_score(self) -> float:
        return self.score if self.score is not None else 0.0

    @property
    def fsm_coverage(self) -> Optional[float]:
        return self.fsm_cov

    @property
    def branch_coverage(self) -> float:
        return self.branch_cov

    @property
    def line_coverage(self) -> float:
        return self.line_cov

    @property
    def condition_coverage(self) -> Optional[float]:
        return self.cond_cov

    @property
    def toggle_coverage(self) -> float:
        return self.toggle_cov


class CoverageGap(BaseModel):
    id: str = ""
    severity: str = "HIGH"  # 'HIGH', 'MEDIUM', 'LOW'
    category: str = ""
    title: str = ""
    description: str = ""
    rtl_file: str = ""
    rtl_line: int = 0
    tb_file: str = ""
    tb_line: int = 0
    evidence: str = ""
    suggested_action: str = ""
    finding_id: Optional[str] = None

    def __init__(self, **data):
        if "category" not in data and "finding_id" in data and data.get("finding_id"):
            fid = data["finding_id"]
            if "BRAN" in fid:
                data["category"] = "BRANCH"
            elif "COND" in fid:
                data["category"] = "CONDITION"
            elif "FSM" in fid:
                data["category"] = "FSM_TRANSITION"
            elif "OUTP" in fid:
                data["category"] = "OUTPUT_CHECK"
            elif "REST" in fid or "RST" in fid:
                data["category"] = "RESET"
            elif "LINE" in fid:
                data["category"] = "LINE"
            elif "TOGG" in fid:
                data["category"] = "TOGGLE"
        super().__init__(**data)


class ModuleCoverage(BaseModel):
    module_name: str
    score: Optional[float] = None
    line_cov: float = 0.0
    cond_cov: Optional[float] = None
    toggle_cov: float = 0.0
    fsm_cov: Optional[float] = None
    branch_cov: float = 0.0


class AnalysisLog(BaseModel):
    stage: str
    message: str
    level: str = "INFO"  # 'INFO', 'WARN', 'SUCCESS', 'ERROR'
    timestamp: str = ""


class SignalMappingItem(BaseModel):
    dut_port: str
    direction: str
    width: str
    tb_connection: str
    stimulus_status: str  # 'DRIVEN_FULL', 'DRIVEN_PARTIAL', 'NOT_STIMULATED', 'N/A_OUTPUT'
    observation_status: str  # 'CHECKED_ASSERT', 'CHECKED_IF', 'OBSERVED_DISPLAY', 'UNCHECKED', 'N/A_INPUT'
    status: str  # 'OK', 'WARNING', 'CRITICAL'
    rtl_line: int = 0
    tb_line: int = 0
    finding_id: Optional[str] = None

    @property
    def tb_signal(self) -> str:
        return self.tb_connection


# Before / After Run Comparison Model
class BeforeAfterComparison(BaseModel):
    has_previous: bool = False
    previous_timestamp: str = ""
    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0
    line_delta: float = 0.0
    cond_delta: float = 0.0
    toggle_delta: float = 0.0
    fsm_delta: Optional[float] = None
    branch_delta: float = 0.0
    total_gaps_before: int = 0
    total_gaps_after: int = 0
    resolved_gaps: List[str] = []
    remaining_gaps: List[str] = []
    new_gaps: List[str] = []


class CoverageReport(BaseModel):
    design_name: str
    rtl_filename: str
    tb_filename: str
    timestamp: str
    total_summary: CoverageScore
    hierarchical_coverage: List[ModuleCoverage] = []
    modules: List[ModuleModel] = []
    tb_model: TestbenchModel
    branches: List[Branch] = []
    conditions: List[Condition] = []
    case_statements: List[CaseStatement] = []
    signal_mapping: List[SignalMappingItem] = []
    gaps: List[CoverageGap] = []
    findings: List[Finding] = []
    before_after: Optional[BeforeAfterComparison] = None
    dataflow_graph: Dict[str, Any] = {}
    logs: List[AnalysisLog] = []
    design_files: List[str] = []
    top_module: str = ""
    hierarchy: Optional[HierarchyNode] = None
    total_rtl_lines: int = 0
    total_tb_lines: int = 0
    partial_analysis: bool = False
    partial_reasons: List[str] = []
    raw_rtl: str = ""
    raw_tb: str = ""
    version: str = "2.0.0"

    @property
    def score(self) -> CoverageScore:
        return self.total_summary

    @property
    def scores(self) -> CoverageScore:
        return self.total_summary

    @property
    def signals(self) -> List[SignalMappingItem]:
        return self.signal_mapping

"""
Enhanced Coverage and Verification Gap Analyzer with Deep Reasoning.
Includes:
- Unified Evidence Model with [ WHY? ] explanations
- Lightweight Dataflow signal tracing
- Smart FSM with Reset Reachability and Visual Graph
- Truth Table matrix for compound conditions
- Boundary analysis for counter comparisons
- Actionable Verilog stimulus suggestions
"""

from typing import List, Dict, Optional, Tuple, Any, Set
from datetime import datetime
import re
from .ast_nodes import (
    DesignModel, ModuleModel, TestbenchModel, CoverageReport,
    CoverageScore, ModuleCoverage, CoverageGap, SignalMappingItem,
    Branch, Condition, ConditionTerm, TruthTableRow, CaseStatement,
    FsmModel, FsmTransition, FsmStateReachability, FsmGraphNode, FsmGraphEdge,
    Finding, AnalysisLog, EvidenceItem
)
from .testbench_analyzer import normalize_val
from .dataflow_analyzer import DataflowAnalyzer


class CoverageAnalyzer:
    def __init__(self):
        self.logs: List[AnalysisLog] = []
        self.findings: List[Finding] = []
        self.finding_counter = 0

    def _log(self, stage: str, message: str, level: str = "INFO"):
        self.logs.append(AnalysisLog(
            stage=stage,
            message=message,
            level=level,
            timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3]
        ))

    def _create_finding(
        self,
        category: str,
        title: str,
        expression: str,
        rtl_file: str,
        rtl_line: int,
        what_was_found: str,
        where_found: str,
        tb_evidence: str,
        reasoning: str,
        confidence: str,
        status: str,
        suggested_scenario: str,
        stimulus_snippet: str,
        dataflow_chain: List[str] = None,
        tb_file: str = "",
        tb_line: Optional[int] = None,
        severity: Optional[str] = None,
        module: str = "",
        statement: str = ""
    ) -> Finding:
        self.finding_counter += 1
        finding_id = f"FIND-{category[:4]}-{self.finding_counter:03d}"
        if not severity:
            if "Never Checked" in title or "Never Released" in title or "Not Stimulated" in title or category in ("OUTPUT_CHECK", "RESET"):
                severity = "HIGH"
            elif category in ("BRANCH", "CONDITION", "CASE_ITEM", "FSM_TRANSITION"):
                severity = "MEDIUM"
            else:
                severity = "LOW"

        ev_type = "STIMULUS" if "STIMULUS" in status or "FOUND" in status else ("OBSERVATION" if "OUTPUT" in category else "INFERENCE")
        ev_item = EvidenceItem(
            source=category,
            type=ev_type,
            location=where_found or f"{rtl_file}:{rtl_line}",
            observed_value=tb_evidence,
            inferred_value=status,
            relationship=title,
            confidence=confidence,
            explanation=reasoning
        )

        finding = Finding(
            id=finding_id,
            category=category,
            title=title,
            expression=expression,
            rtl_file=rtl_file,
            rtl_line=rtl_line,
            module=module,
            statement=statement,
            tb_file=tb_file,
            tb_line=tb_line,
            what_was_found=what_was_found,
            where_found=where_found,
            tb_evidence=tb_evidence,
            dataflow_chain=dataflow_chain or [f"{expression} (Direct Evaluation)"],
            evidence_items=[ev_item],
            reasoning=reasoning,
            confidence=confidence,
            status=status,
            severity=severity,
            recommendation=suggested_scenario,
            suggested_action=suggested_scenario,
            suggested_scenario=suggested_scenario,
            stimulus_snippet=stimulus_snippet
        )
        self.findings.append(finding)
        return finding

    def analyze(self, design: DesignModel, tb: TestbenchModel, raw_rtl: str = "", raw_tb: str = "") -> CoverageReport:
        self.logs = []
        self.findings = []
        self.finding_counter = 0

        self._log("Reading RTL", f"Parsed {len(design.modules)} module(s) from {design.filename}", "SUCCESS")
        top_module = None
        if design.top_module:
            top_module = next((m for m in design.modules if m.name == design.top_module), None)
        if not top_module and design.modules:
            top_module = next((m for m in design.modules if m.is_top), design.modules[0])
        design_name = top_module.name if top_module else (design.top_module or "Unknown")

        # Initialize Dataflow Analyzer
        dataflow = DataflowAnalyzer(top_module, tb) if top_module else None

        self._log("Detecting DUT ports", f"Found {len(top_module.ports) if top_module else 0} port(s)", "INFO")
        self._log("Parsing procedural blocks", f"Detected {len(top_module.always_blocks) if top_module else 0} always block(s)", "INFO")
        self._log("Detecting branches", f"Found {len(top_module.branches) if top_module else 0} branch path(s)", "INFO")
        self._log("Detecting conditions", f"Found {len(top_module.conditions) if top_module else 0} condition expression(s)", "INFO")
        self._log("Detecting case statements", f"Found {len(top_module.case_statements) if top_module else 0} case statement(s)", "INFO")

        self._log("Reading testbench", f"Read {tb.filename} with {len(tb.stimulus)} stimulus assignments", "SUCCESS")
        self._log("Detecting stimulus", f"Extracted {len(tb.toggles)} active testbench net(s)", "INFO")

        # 1. Map DUT Ports to TB Signals
        signal_mapping = self._build_signal_mapping(top_module, tb, dataflow)
        self._log("Mapping DUT connections", f"Mapped {len(signal_mapping)} port connection(s)", "SUCCESS")

        # Quick lookup of TB stimulated values for each DUT port name
        dut_to_tb_vals: Dict[str, List[str]] = {}
        for item in signal_mapping:
            tb_sig = item.tb_connection
            vals = []
            if tb_sig in tb.toggles:
                vals = tb.toggles[tb_sig].values_seen
            dut_to_tb_vals[item.dut_port] = vals

        # 2. Smart FSM Analysis (Reset Reachability & Visual Graph)
        if top_module and top_module.fsm:
            self._log("Analyzing FSM", f"Analyzing state machine on '{top_module.fsm.state_reg}' with reset correlation", "INFO")
            self._evaluate_smart_fsm(top_module, tb, dut_to_tb_vals, dataflow)

        # 3. Correlate Branches
        branches = []
        if top_module:
            branches = self._evaluate_branches(top_module, tb, dut_to_tb_vals, signal_mapping, dataflow)
        self._log("Checking branch coverage", f"Evaluated {len(branches)} branch condition(s)", "INFO")

        # 4. Correlate Conditions with Truth Table and Boundary Analysis
        conditions = []
        if top_module:
            conditions = self._evaluate_conditions(top_module, dut_to_tb_vals, dataflow)
        self._log("Checking condition coverage", f"Evaluated {len(conditions)} logical condition(s)", "INFO")

        # 5. Check Case Statements
        case_stmts = []
        if top_module:
            case_stmts = self._evaluate_case_statements(top_module, dut_to_tb_vals, dataflow)

        # 6. Check Output Observation
        self._log("Checking output observation", f"Inspected {len(tb.output_checks)} DUT output check(s)", "INFO")

        # 7. Generate Coverage Gaps with Linked Findings
        gaps = self._identify_coverage_gaps(top_module, tb, signal_mapping, branches, conditions, case_stmts, dataflow)
        self._log("Generating report", f"Identified {len(gaps)} potential verification gap(s)", "SUCCESS" if not any(g.severity == 'HIGH' for g in gaps) else "WARN")

        # 8. Calculate Module and Hierarchical Coverage
        hierarchical_coverage: List[ModuleCoverage] = []
        for mod in design.modules:
            mod_cov = self._calculate_module_coverage(mod, tb, signal_mapping, branches, conditions)
            hierarchical_coverage.append(mod_cov)

        total_summary = hierarchical_coverage[0] if hierarchical_coverage else ModuleCoverage(module_name=design_name)
        total_score_obj = CoverageScore(
            score=total_summary.score,
            line_cov=total_summary.line_cov,
            cond_cov=total_summary.cond_cov,
            toggle_cov=total_summary.toggle_cov,
            fsm_cov=total_summary.fsm_cov,
            branch_cov=total_summary.branch_cov
        )

        return CoverageReport(
            design_name=design_name,
            rtl_filename=design.filename,
            tb_filename=tb.filename,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_summary=total_score_obj,
            hierarchical_coverage=hierarchical_coverage,
            modules=design.modules,
            tb_model=tb,
            branches=branches,
            conditions=conditions,
            case_statements=case_stmts,
            signal_mapping=signal_mapping,
            gaps=gaps,
            findings=self.findings,
            dataflow_graph={"dependencies": {k: list(v) for k, v in dataflow.dependencies.items()}} if dataflow else {},
            logs=self.logs,
            design_files=design.files if design.files else ([design.filename] if design.filename else []),
            top_module=design.top_module or (design.modules[0].name if design.modules else ""),
            hierarchy=design.hierarchy,
            total_rtl_lines=design.total_rtl_lines or (raw_rtl.count('\n') + 1 if raw_rtl else 0),
            total_tb_lines=raw_tb.count('\n') + 1 if raw_tb else 0,
            partial_analysis=any(m.partial_analysis for m in design.modules),
            partial_reasons=[m.partial_reason for m in design.modules if m.partial_reason],
            raw_rtl=raw_rtl,
            raw_tb=raw_tb,
            version="2.0.0"
        )

    def _evaluate_smart_fsm(self, mod: ModuleModel, tb: TestbenchModel, dut_to_tb_vals: Dict[str, List[str]], dataflow: Optional[DataflowAnalyzer]):
        """
        Smart FSM reasoning:
        1. Identifies reset state (e.g. if (reset) state <= ACTIVE).
        2. Asserts that RESET assertion provides evidence for that reset state!
        3. Analyzes transitions and their trigger conditions.
        4. Builds interactive SVG graph nodes and edges.
        """
        fsm = mod.fsm
        if not fsm:
            return

        # 1. Detect Reset State
        reset_state = None
        for b in mod.always_blocks:
            if b.is_clocked and b.reset_signal:
                # Look for reset assignment in text
                pass
        # Common reset state: first detected state or one named IDLE, RESET, ACTIVE, INIT
        for st in fsm.detected_states:
            if st.upper() in ("IDLE", "RESET", "ACTIVE", "INIT", "START"):
                reset_state = st
                break
        if not reset_state and fsm.detected_states:
            reset_state = fsm.detected_states[0]
        fsm.reset_state = reset_state

        # Check if reset was asserted in TB
        reset_asserted = len(tb.resets) > 0 and tb.resets[0].asserted

        # 2. State Reachability
        reachability_list: List[FsmStateReachability] = []
        reachable_states_set: Set[str] = set()

        for st in fsm.detected_states:
            if st == reset_state:
                if reset_asserted:
                    reachability_list.append(FsmStateReachability(
                        state_name=st,
                        reachable=True,
                        reachability_evidence="RESET_ASSERTION",
                        reason=f"Testbench asserts reset sequence ({tb.resets[0].signal_name}), initializing state to '{st}'."
                    ))
                    reachable_states_set.add(st)
                else:
                    reachability_list.append(FsmStateReachability(
                        state_name=st,
                        reachable=False,
                        reachability_evidence="NO_EVIDENCE",
                        reason=f"Initial state '{st}' not confirmed because reset is never exercised in testbench."
                    ))
            else:
                # Other states: check if transitions leading into this state have stimulus
                reachability_list.append(FsmStateReachability(
                    state_name=st,
                    reachable=False,  # will update after transitions
                    reachability_evidence="NO_EVIDENCE",
                    reason="Checking transition conditions..."
                ))

        # 3. Transitions Evaluation Helper
        def _check_transition_evidence(cond_str: str) -> Tuple[bool, str]:
            if not cond_str or "unconditional" in cond_str.lower():
                return True, "Unconditional state advance."

            if dataflow:
                reach, _, expl = dataflow.evaluate_condition_reachability(cond_str, dut_to_tb_vals)
                if reach:
                    return True, expl

            cond_vars = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", cond_str)
            for var in cond_vars:
                if var in dut_to_tb_vals and dut_to_tb_vals[var]:
                    vals = dut_to_tb_vals[var]
                    active_vals = [v for v in vals if normalize_val(v) not in ("0", "1'b0", "0'b0")]
                    if active_vals:
                        return True, f"TB drives activating stimulus for '{var}': {active_vals[:3]}"
                elif dataflow:
                    upstreams = dataflow.get_upstream_inputs(var)
                    active_ups = [u for u in upstreams if any(normalize_val(v) not in ("0", "1'b0") for v in dut_to_tb_vals.get(u, []))]
                    if active_ups:
                        return True, f"Dataflow trace: '{var}' driven via upstream input(s): {', '.join(active_ups)}"

            return False, f"No activating stimulus driven for transition trigger '{cond_str}'."

        # Multi-pass reachability propagation
        changed = True
        while changed:
            changed = False
            for tr in fsm.transitions:
                from_st = tr.from_state
                to_st = tr.to_state
                ev_found, _ = _check_transition_evidence(tr.condition_expr)
                if from_st in reachable_states_set and ev_found and to_st not in reachable_states_set:
                    reachable_states_set.add(to_st)
                    changed = True

        updated_transitions: List[FsmTransition] = []
        graph_edges: List[FsmGraphEdge] = []

        for tr in fsm.transitions:
            from_st = tr.from_state
            to_st = tr.to_state
            cond_str = tr.condition_expr
            has_evidence, evidence_msg = _check_transition_evidence(cond_str)

            # If from_st is reachable and condition has evidence, then transition is stimulated!
            if from_st in reachable_states_set and has_evidence:
                tr_status = "EVIDENCE_FOUND"
            elif from_st in reachable_states_set:
                tr_status = "UNCERTAIN"
            else:
                tr_status = "NO_EVIDENCE"

            # Create finding for transition
            scenario, snippet = dataflow.generate_stimulus_suggestion(cond_str, f"{from_st} -> {to_st}", "FSM_TRANSITION") if dataflow else ("", "")
            finding = self._create_finding(
                category="FSM_TRANSITION",
                title=f"FSM Transition {from_st} → {to_st}",
                expression=f"state transition ({from_st} -> {to_st}) upon {cond_str}",
                rtl_file=mod.filename,
                rtl_line=tr.line,
                what_was_found=f"State transition from {from_st} to {to_st} triggered by '{cond_str}'.",
                where_found=f"{mod.filename}:{tr.line}",
                tb_evidence=evidence_msg if evidence_msg else f"No stimulus driven for transition trigger '{cond_str}'.",
                reasoning=(
                    f"Transition from {from_st} to {to_st} requires {from_st} to be active and condition '{cond_str}' to be true. "
                    f"Source state is {'reachable' if from_st in reachable_states_set else 'unreachable'}. "
                    f"Trigger stimulus {'found' if has_evidence else 'missing'}."
                ),
                confidence="HIGH" if has_evidence else "MEDIUM",
                status="✓ STIMULUS EVIDENCE FOUND" if tr_status == "EVIDENCE_FOUND" else "⚠ POTENTIALLY UNTESTED",
                suggested_scenario=scenario,
                stimulus_snippet=snippet,
                dataflow_chain=[f"State: {from_st}", f"Condition: {cond_str}", f"Next State: {to_st}"]
            )

            updated_transitions.append(FsmTransition(
                from_state=from_st,
                to_state=to_st,
                condition_expr=cond_str,
                trigger_condition=cond_str,
                evidence=evidence_msg if evidence_msg else "No trigger stimulus",
                status=tr_status,
                line=tr.line,
                finding_id=finding.id
            ))

            graph_edges.append(FsmGraphEdge(
                from_node=from_st,
                to_node=to_st,
                condition=cond_str,
                status=tr_status,
                line=tr.line,
                finding_id=finding.id
            ))

        # Update reachability reasons
        for r in reachability_list:
            if r.state_name in reachable_states_set:
                r.reachable = True
                r.is_reachable = True
                if r.state_name != reset_state:
                    r.reachability_evidence = "TRANSITION_STIMULUS"
                    r.evidence = "Reached via stimulated transition paths from initial state."
                    r.reason = "Reached via stimulated transition paths from initial state."

        # 4. Graph Nodes
        graph_nodes: List[FsmGraphNode] = []
        for st in fsm.detected_states:
            is_rst = (st == reset_state)
            is_reach = st in reachable_states_set
            graph_nodes.append(FsmGraphNode(
                id=st,
                label=st,
                status="EVIDENCE_FOUND" if is_reach else "NO_EVIDENCE",
                is_reset_state=is_rst,
                is_reachable=is_reach
            ))

        fsm.state_reachability = reachability_list
        fsm.transitions = updated_transitions
        fsm.graph_nodes = graph_nodes
        fsm.graph_edges = graph_edges

    def _build_signal_mapping(self, mod: Optional[ModuleModel], tb: TestbenchModel, dataflow: Optional[DataflowAnalyzer]) -> List[SignalMappingItem]:
        mapping: List[SignalMappingItem] = []
        if not mod:
            return mapping

        instance_conns: Dict[str, str] = {}
        inst_line = 1
        for inst in tb.dut_instances:
            if inst.module_name == mod.name or len(tb.dut_instances) == 1:
                inst_line = inst.line
                for conn in inst.connections:
                    instance_conns[conn.port_name] = conn.tb_expr
                break

        checks_lookup = {c.dut_output: c for c in tb.output_checks}

        for port in mod.ports:
            tb_conn = instance_conns.get(port.name, port.name if port.name in tb.toggles else "UNCONNECTED")
            rtl_line = port.line
            tb_line = inst_line

            if port.direction == "input":
                observation_status = "N/A (INPUT)"
                if tb_conn == "UNCONNECTED":
                    stimulus_status = "NOT_STIMULATED"
                    status = "CRITICAL"
                elif tb_conn in tb.toggles:
                    tog = tb.toggles[tb_conn]
                    if tog.status == "FULL":
                        stimulus_status = "DRIVEN_FULL"
                        status = "OK"
                    elif tog.status == "LIMITED":
                        stimulus_status = "DRIVEN_PARTIAL"
                        status = "WARNING"
                    else:
                        stimulus_status = "NOT_STIMULATED"
                        status = "CRITICAL"
                else:
                    stimulus_status = "NOT_STIMULATED"
                    status = "CRITICAL"

                finding_id = None
                if status != "OK":
                    scenario, snippet = dataflow.generate_stimulus_suggestion(port.name, f"Port {port.name}", "INPUT_STIMULUS") if dataflow else ("", "")
                    finding = self._create_finding(
                        category="INPUT",
                        title=f"Input Port '{port.name}' Stimulus Status",
                        expression=f"input {port.width} {port.name}",
                        rtl_file=mod.filename,
                        rtl_line=port.line,
                        what_was_found=f"Input port '{port.name}' stimulus is {stimulus_status}.",
                        where_found=f"{mod.filename}:{port.line}",
                        tb_evidence=f"Connected to '{tb_conn}'. Stimulus status: {stimulus_status}.",
                        reasoning=f"Inputs require both 0→1 and 1→0 transitions to guarantee complete toggle stimulation.",
                        confidence="HIGH",
                        status="⚠ POTENTIALLY UNTESTED" if status == "WARNING" else "? INSUFFICIENT EVIDENCE",
                        suggested_scenario=scenario,
                        stimulus_snippet=snippet,
                        dataflow_chain=[f"{tb_conn} (TB net)", f"{port.name} (DUT Port)"]
                    )
                    finding_id = finding.id

            elif port.direction == "output":
                stimulus_status = "N/A (OUTPUT)"
                chk = checks_lookup.get(port.name)
                if chk:
                    if chk.check_type == "ASSERTION":
                        observation_status = "CHECKED_ASSERT"
                        status = "OK"
                    elif chk.check_type == "IF_CHECK":
                        observation_status = "CHECKED_IF"
                        status = "OK"
                    elif chk.check_type == "DISPLAY":
                        observation_status = "OBSERVED_DISPLAY"
                        status = "WARNING"
                    else:
                        observation_status = "UNCHECKED"
                        status = "CRITICAL"
                else:
                    observation_status = "UNCHECKED"
                    status = "CRITICAL"

                finding_id = None
                if status != "OK":
                    scenario, snippet = dataflow.generate_stimulus_suggestion(port.name, f"Output {port.name}", "OUTPUT_CHECK") if dataflow else ("", "")
                    finding = self._create_finding(
                        category="OUTPUT_CHECK",
                        title=f"DUT Output '{port.name}' Verification Status",
                        expression=f"output {port.width} {port.name}",
                        rtl_file=mod.filename,
                        rtl_line=port.line,
                        what_was_found=f"DUT output '{port.name}' observation is {observation_status}.",
                        where_found=f"{mod.filename}:{port.line}",
                        tb_evidence=f"Observation check type: {observation_status}. No expected-value assertion detected.",
                        reasoning=f"Having stimulus drive internal logic is insufficient; the output response must be asserted or compared against expected values.",
                        confidence="HIGH",
                        status="⚠ POTENTIALLY UNTESTED",
                        suggested_scenario=scenario,
                        stimulus_snippet=snippet,
                        dataflow_chain=[f"{port.name} (DUT Output)", "Expected-value checker (Missing in TB)"]
                    )
                    finding_id = finding.id

            else:
                stimulus_status = "INOUT_OBSERVED"
                observation_status = "INOUT_UNCHECKED"
                status = "WARNING"
                finding_id = None

            mapping.append(SignalMappingItem(
                dut_port=port.name,
                direction=port.direction,
                width=port.width,
                tb_connection=tb_conn,
                stimulus_status=stimulus_status,
                observation_status=observation_status,
                status=status,
                rtl_line=rtl_line,
                tb_line=tb_line,
                finding_id=finding_id
            ))

        return mapping

    def _evaluate_branches(
        self,
        mod: ModuleModel,
        tb: TestbenchModel,
        dut_to_tb_vals: Dict[str, List[str]],
        signal_mapping: List[SignalMappingItem],
        dataflow: Optional[DataflowAnalyzer]
    ) -> List[Branch]:
        updated_branches: List[Branch] = []
        reset_ports = [p.name for p in mod.ports if any(k in p.name.lower() for k in ("rst", "reset"))]
        reset_seq = tb.resets[0] if tb.resets else None

        for br in mod.branches:
            br_copy = br.model_copy()
            cond = br.condition_expr

            if br.branch_type == "case_item":
                val_match = False
                for case_stmt in mod.case_statements:
                    if case_stmt.line <= br.line <= case_stmt.items[-1].end_line if case_stmt.items else case_stmt.line + 20:
                        var = case_stmt.expr.strip()

                        # Check if this case statement is on the FSM state register
                        if mod.fsm and var == mod.fsm.state_reg:
                            for item in case_stmt.items:
                                if item.start_line <= br.line <= item.end_line:
                                    for r in mod.fsm.state_reachability:
                                        if (r.state_name in item.values or r.state_name in item.label) and r.reachable:
                                            val_match = True
                                            break
                                    item.stimulated = val_match
                                    break
                        else:
                            driven_vals = dut_to_tb_vals.get(var, [])
                            norm_driven = [normalize_val(v) for v in driven_vals]

                            for item in case_stmt.items:
                                if item.start_line <= br.line <= item.end_line:
                                    for v in item.values:
                                        if normalize_val(v) in norm_driven or v in driven_vals:
                                            val_match = True
                                            break
                                    item.stimulated = val_match
                                    break
                        break

                br_copy.stimulated_true = val_match
                br_copy.stimulated_false = True
                br_copy.status = "COVERED" if val_match else "POTENTIALLY_UNTESTED"

            elif br.branch_type == "case_default":
                br_copy.stimulated_true = True
                br_copy.status = "COVERED"

            elif br.branch_type in ("if_then", "if_else"):
                is_rst_cond = any(rp in cond for rp in reset_ports)
                if is_rst_cond:
                    if reset_seq:
                        br_copy.stimulated_true = reset_seq.asserted
                        br_copy.stimulated_false = reset_seq.released
                    else:
                        br_copy.stimulated_true = False
                        br_copy.stimulated_false = True
                else:
                    boundary = dataflow.evaluate_boundary_condition(cond) if dataflow else {"has_boundary": False}
                    if boundary.get("has_boundary") and boundary.get("threshold_val") is not None:
                        is_reachable = (boundary.get("boundary_status") == "✓ STATICALLY REACHABLE")
                        br_copy.stimulated_true = is_reachable
                        br_copy.stimulated_false = True
                    else:
                        cond_vars = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", cond)
                        var_driven = False
                        for var in cond_vars:
                            if var in dut_to_tb_vals and dut_to_tb_vals[var]:
                                vals = dut_to_tb_vals[var]
                                var_driven = True
                                active_vals = [v for v in vals if normalize_val(v) not in ("0", "1'b0", "0'b0")]
                                zero_vals = [v for v in vals if normalize_val(v) in ("0", "1'b0", "0'b0")]
                                br_copy.stimulated_true = len(active_vals) > 0
                                br_copy.stimulated_false = len(zero_vals) > 0 or len(set(vals)) > 1
                                break
                            elif dataflow:
                                reach, _, _ = dataflow.evaluate_condition_reachability(var, dut_to_tb_vals)
                                if reach:
                                    var_driven = True
                                    br_copy.stimulated_true = True
                                    br_copy.stimulated_false = True
                                    break
                        if not var_driven:
                            br_copy.stimulated_true = False
                            br_copy.stimulated_false = False

                if br_copy.branch_type == "if_then":
                    br_copy.status = "COVERED" if br_copy.stimulated_true else "POTENTIALLY_UNTESTED"
                else:
                    br_copy.status = "COVERED" if br_copy.stimulated_false else "POTENTIALLY_UNTESTED"

            # Create Finding with [ WHY? ] info
            df_chain = dataflow.trace_dataflow(cond) if dataflow else [f"{cond} (Direct branch)"]
            scenario, snippet = dataflow.generate_stimulus_suggestion(cond, f"Branch L{br.line}", "BRANCH") if dataflow else ("", "")
            
            finding = self._create_finding(
                category="BRANCH",
                title=f"Branch {br.id} ({br.branch_type})",
                expression=br.condition_expr,
                rtl_file=mod.filename,
                rtl_line=br.line,
                what_was_found=f"Execution branch {br.id} with condition '{br.condition_expr}'.",
                where_found=f"{mod.filename}:{br.line}",
                tb_evidence=f"TRUE path: {'Stimulated' if br_copy.stimulated_true else 'Not stimulated'}, FALSE path: {'Stimulated' if br_copy.stimulated_false else 'Not stimulated'}.",
                reasoning=(
                    f"Branch was evaluated against static TB stimulus vectors. "
                    f"Status is {br_copy.status} because required condition states "
                    f"{'were verified in TB assignments' if br_copy.status == 'COVERED' else 'could not be verified in TB assignments'}."
                ),
                confidence="HIGH",
                status="✓ STIMULUS EVIDENCE FOUND" if br_copy.status == "COVERED" else "⚠ POTENTIALLY UNTESTED",
                suggested_scenario=scenario,
                stimulus_snippet=snippet,
                dataflow_chain=df_chain
            )
            br_copy.finding_id = finding.id
            updated_branches.append(br_copy)

        return updated_branches

    def _evaluate_conditions(
        self,
        mod: ModuleModel,
        dut_to_tb_vals: Dict[str, List[str]],
        dataflow: Optional[DataflowAnalyzer]
    ) -> List[Condition]:
        updated_conditions: List[Condition] = []

        for cond in mod.conditions:
            cond_copy = cond.model_copy()
            all_terms_covered = True
            missing_scenarios = []

            for term in cond_copy.terms:
                var_vals = dut_to_tb_vals.get(term.variable, [])
                norm_vals = [normalize_val(v) for v in var_vals]
                target_norm = normalize_val(term.target_value)

                if target_norm in norm_vals or (term.target_value != "0" and any(v != "0" for v in norm_vals)):
                    term.stimulated_high = True
                else:
                    term.stimulated_high = False

                if "0" in norm_vals or any(v != target_norm for v in norm_vals):
                    term.stimulated_low = True
                else:
                    term.stimulated_low = False

                if not (term.stimulated_high and term.stimulated_low):
                    all_terms_covered = False
                    if not term.stimulated_high:
                        missing_scenarios.append(f"{term.variable} == {term.target_value} (HIGH/MATCH)")
                    if not term.stimulated_low:
                        missing_scenarios.append(f"{term.variable} != {term.target_value} (LOW/INACTIVE)")

            # Generate Truth Table rows for compound conditions
            truth_table_rows: List[TruthTableRow] = []
            if len(cond_copy.terms) >= 2:
                # 2-term boolean condition: a && b
                t1, t2 = cond_copy.terms[0], cond_copy.terms[1]
                combos = [
                    (f"{t1.variable}=1, {t2.variable}=1", "TRUE" if "&&" in cond_copy.raw_expression else "TRUE", t1.stimulated_high and t2.stimulated_high),
                    (f"{t1.variable}=1, {t2.variable}=0", "FALSE" if "&&" in cond_copy.raw_expression else "TRUE", t1.stimulated_high and t2.stimulated_low),
                    (f"{t1.variable}=0, {t2.variable}=1", "FALSE" if "&&" in cond_copy.raw_expression else "TRUE", t1.stimulated_low and t2.stimulated_high),
                    (f"{t1.variable}=0, {t2.variable}=0", "FALSE", t1.stimulated_low and t2.stimulated_low),
                ]
                for combo_str, outcome, has_ev in combos:
                    truth_table_rows.append(TruthTableRow(
                        combination=combo_str,
                        expected_outcome=outcome,
                        status="✓ STIMULUS EVIDENCE FOUND" if has_ev else ("⚠ POTENTIALLY UNTESTED" if outcome == "TRUE" else "? INSUFFICIENT EVIDENCE"),
                        evidence_detail=f"Stimulus {'observed' if has_ev else 'not observed'} for pair"
                    ))
            elif len(cond_copy.terms) == 1:
                t1 = cond_copy.terms[0]
                truth_table_rows.append(TruthTableRow(
                    combination=f"{t1.variable} == {t1.target_value}",
                    expected_outcome="TRUE",
                    status="✓ STIMULUS EVIDENCE FOUND" if t1.stimulated_high else "⚠ POTENTIALLY UNTESTED",
                    evidence_detail=f"Stimulus {'verified' if t1.stimulated_high else 'missing'}"
                ))
                truth_table_rows.append(TruthTableRow(
                    combination=f"{t1.variable} != {t1.target_value}",
                    expected_outcome="FALSE",
                    status="✓ STIMULUS EVIDENCE FOUND" if t1.stimulated_low else "⚠ POTENTIALLY UNTESTED",
                    evidence_detail=f"Stimulus {'verified' if t1.stimulated_low else 'missing'}"
                ))

            cond_copy.truth_table = truth_table_rows

            # Boundary evaluation for counter expressions
            if dataflow:
                boundary_info = dataflow.evaluate_boundary_condition(cond_copy.raw_expression)
                if boundary_info["has_boundary"]:
                    cond_copy.boundary_variable = boundary_info["variable"]
                    cond_copy.boundary_threshold = str(boundary_info["threshold_val"]) if boundary_info["threshold_val"] is not None else boundary_info["threshold_raw"]
                    cond_copy.inferred_range = boundary_info["inferred_range"]

            cond_copy.missing_scenarios = missing_scenarios
            cond_copy.status = "COVERED" if all_terms_covered else ("PARTIALLY_TESTED" if any(t.stimulated_high or t.stimulated_low for t in cond_copy.terms) else "POTENTIALLY_UNTESTED")

            # Create Finding for Condition
            df_chain = dataflow.trace_dataflow(cond_copy.raw_expression) if dataflow else []
            scenario, snippet = dataflow.generate_stimulus_suggestion(cond_copy.raw_expression, f"Condition L{cond_copy.line}", "CONDITION") if dataflow else ("", "")
            
            finding = self._create_finding(
                category="CONDITION",
                title=f"Condition {cond_copy.id}",
                expression=cond_copy.raw_expression,
                rtl_file=mod.filename,
                rtl_line=cond_copy.line,
                what_was_found=f"Logical condition expression with {len(cond_copy.terms)} term(s).",
                where_found=f"{mod.filename}:{cond_copy.line}",
                tb_evidence=(
                    f"Truth table coverage: {sum(1 for r in truth_table_rows if 'EVIDENCE' in r.status)}/{len(truth_table_rows)} combinations exercised."
                    if truth_table_rows else "Evaluated against TB stimulus."
                ),
                reasoning=(
                    f"Condition breakdown showed {len(missing_scenarios)} unexercised combination(s): {', '.join(missing_scenarios) if missing_scenarios else 'None'}."
                ),
                confidence="HIGH" if cond_copy.status == "COVERED" else "MEDIUM",
                status="✓ STIMULUS EVIDENCE FOUND" if cond_copy.status == "COVERED" else "⚠ POTENTIALLY UNTESTED",
                suggested_scenario=scenario,
                stimulus_snippet=snippet,
                dataflow_chain=df_chain
            )
            cond_copy.finding_id = finding.id
            updated_conditions.append(cond_copy)

        return updated_conditions

    def _evaluate_case_statements(
        self,
        mod: ModuleModel,
        dut_to_tb_vals: Dict[str, List[str]],
        dataflow: Optional[DataflowAnalyzer]
    ) -> List[CaseStatement]:
        evaluated = []
        for cs in mod.case_statements:
            cs_copy = cs.model_copy()
            selector_var = cs.expr.strip()
            driven = dut_to_tb_vals.get(selector_var, [])
            norm_driven = [normalize_val(v) for v in driven]

            # Detect selector width and 2^N completeness under 2-state assumptions
            selector_width = 1
            found_sig = False
            for p in mod.ports:
                if p.name == selector_var:
                    m_w = re.search(r'\[\s*(\d+)\s*:\s*(\d+)\s*\]', p.width)
                    if m_w:
                        selector_width = abs(int(m_w.group(1)) - int(m_w.group(2))) + 1
                    found_sig = True
                    break
            if not found_sig:
                for s in mod.signals:
                    if s.name == selector_var:
                        m_w = re.search(r'\[\s*(\d+)\s*:\s*(\d+)\s*\]', s.width)
                        if m_w:
                            selector_width = abs(int(m_w.group(1)) - int(m_w.group(2))) + 1
                        break

            max_combos = 2 ** selector_width if selector_width <= 8 else 999999
            explicit_covered = sum(len(it.values) for it in cs_copy.items if not it.is_default)
            all_2n_covered = (explicit_covered >= max_combos)

            stim_count = 0
            for item in cs_copy.items:
                if item.is_default:
                    item.stimulated = True
                    stim_count += 1
                    if all_2n_covered:
                        reasoning = f"Defensive default — unreachable under 2-state inputs (all {max_combos} values of {selector_width}-bit selector covered)."
                        item_status = "✓ COVERED (DEFENSIVE DEFAULT)"
                    else:
                        reasoning = "Default case item reached as fallback branch."
                        item_status = "✓ STIMULUS EVIDENCE FOUND"
                else:
                    hit = False
                    for v in item.values:
                        if normalize_val(v) in norm_driven or v in driven:
                            hit = True
                            break
                    item.stimulated = hit
                    if hit:
                        stim_count += 1
                    reasoning = f"Case item {item.label} was {'reached by TB assignment' if item.stimulated else 'never matched by driven values'}."
                    item_status = "✓ STIMULUS EVIDENCE FOUND" if item.stimulated else "⚠ POTENTIALLY UNTESTED"

                # Finding for case item
                scenario, snippet = dataflow.generate_stimulus_suggestion(f"{cs.expr} == {item.label}", f"Case Item L{item.start_line}", "CASE_ITEM") if dataflow else ("", "")
                finding = self._create_finding(
                    category="BRANCH",
                    title=f"Case Item '{item.label}' in {cs.expr}",
                    expression=f"case ({cs.expr}) -> {item.label}",
                    rtl_file=mod.filename,
                    rtl_line=item.start_line,
                    what_was_found=f"Case item for value(s) {item.values} in case({cs.expr}).",
                    where_found=f"{mod.filename}:{item.start_line}",
                    tb_evidence=f"Driven values for {cs.expr}: {driven[:5] if driven else 'None'}.",
                    reasoning=reasoning,
                    confidence="HIGH",
                    status=item_status,
                    suggested_scenario=scenario,
                    stimulus_snippet=snippet,
                    dataflow_chain=[f"{cs.expr} (Selector)", f"Value: {item.label}"]
                )
                item.finding_id = finding.id

            cs_copy.total_branches = len(cs_copy.items)
            cs_copy.stimulated_branches = stim_count
            evaluated.append(cs_copy)

        return evaluated

    def _identify_coverage_gaps(
        self,
        mod: Optional[ModuleModel],
        tb: TestbenchModel,
        signal_mapping: List[SignalMappingItem],
        branches: List[Branch],
        conditions: List[Condition],
        case_stmts: List[CaseStatement],
        dataflow: Optional[DataflowAnalyzer]
    ) -> List[CoverageGap]:
        gaps: List[CoverageGap] = []
        gap_id = 0

        if not mod:
            return gaps

        # Gap 1: Clock not detected but clocked logic exists
        has_clocked = any(b.is_clocked for b in mod.always_blocks)
        if has_clocked and not tb.clocks:
            gap_id += 1
            scenario, snippet = (
                "Add a standard clock oscillator: 'always #5 clk = ~clk;' inside your testbench.",
                "// 100MHz clock oscillator\nalways #5 clk = ~clk;"
            )
            f = self._create_finding(
                category="RESET",
                title="Clock Generator Missing in Testbench",
                expression="always @(posedge clk)",
                rtl_file=mod.filename,
                rtl_line=mod.always_blocks[0].start_line if mod.always_blocks else 1,
                what_was_found="Clocked procedural block in RTL without active TB clock generator.",
                where_found=f"{mod.filename}:1",
                tb_evidence="No 'always #half_period clk = ~clk;' pattern detected in TB.",
                reasoning="Synchronous sequential registers will not advance without an active clock oscillator.",
                confidence="HIGH",
                status="⚠ POTENTIALLY UNTESTED",
                suggested_scenario=scenario,
                stimulus_snippet=snippet
            )
            gaps.append(CoverageGap(
                id=f"GAP-{gap_id:03d}",
                severity="HIGH",
                title="Clock Generator Missing in Testbench",
                description="RTL contains clocked procedural blocks, but no clock generator was identified in testbench.",
                rtl_file=mod.filename,
                rtl_line=mod.always_blocks[0].start_line if mod.always_blocks else 1,
                tb_file=tb.filename,
                tb_line=1,
                evidence="No 'always #half_period clk = ~clk;' pattern detected in TB.",
                suggested_action=scenario,
                finding_id=f.id
            ))

        # Gap 2: Reset exists in RTL but never stimulated in TB
        reset_ports = [p for p in mod.ports if any(k in p.name.lower() for k in ("rst", "reset"))]
        if reset_ports:
            rst_p = reset_ports[0]
            if not tb.resets:
                gap_id += 1
                scenario, snippet = dataflow.generate_stimulus_suggestion(rst_p.name, f"Reset {rst_p.name}", "RESET") if dataflow else ("", "")
                f = self._create_finding(
                    category="RESET",
                    title=f"Reset Port '{rst_p.name}' Not Stimulated in TB",
                    expression=f"input {rst_p.name}",
                    rtl_file=mod.filename,
                    rtl_line=rst_p.line,
                    what_was_found=f"Reset port '{rst_p.name}' is declared in RTL but testbench contains no reset sequence.",
                    where_found=f"{mod.filename}:{rst_p.line}",
                    tb_evidence="No initial sequence driving reset signal found.",
                    reasoning="Without reset initialization, flip-flops power up in unknown/x state.",
                    confidence="HIGH",
                    status="⚠ POTENTIALLY UNTESTED",
                    suggested_scenario=scenario,
                    stimulus_snippet=snippet
                )
                gaps.append(CoverageGap(
                    id=f"GAP-{gap_id:03d}",
                    severity="HIGH",
                    title=f"Reset Port '{rst_p.name}' Not Stimulated in TB",
                    description=f"RTL expects reset signal '{rst_p.name}', but testbench never executes an assertion/release reset sequence.",
                    rtl_file=mod.filename,
                    rtl_line=rst_p.line,
                    tb_file=tb.filename,
                    tb_line=1,
                    evidence="No initial sequence driving reset signal found.",
                    suggested_action=scenario,
                    finding_id=f.id
                ))
            elif not tb.resets[0].released:
                gap_id += 1
                scenario, snippet = "Deassert reset after 20 time units: '#20 reset = 0;'", "#20 reset = 0; // Release reset"
                f = self._create_finding(
                    category="RESET",
                    title=f"Reset Signal '{tb.resets[0].signal_name}' Never Released",
                    expression=f"{tb.resets[0].signal_name} = 1",
                    rtl_file=mod.filename,
                    rtl_line=rst_p.line,
                    what_was_found="Reset asserted without subsequent release event.",
                    where_found=f"{tb.filename}:{tb.resets[0].line}",
                    tb_evidence="Reset asserted once but never cleared.",
                    reasoning="The DUT will remain in permanent reset and cannot execute normal functional logic.",
                    confidence="HIGH",
                    status="⚠ POTENTIALLY UNTESTED",
                    suggested_scenario=scenario,
                    stimulus_snippet=snippet
                )
                gaps.append(CoverageGap(
                    id=f"GAP-{gap_id:03d}",
                    severity="HIGH",
                    title=f"Reset Signal '{tb.resets[0].signal_name}' Never Released",
                    description="Reset signal was asserted in testbench but never de-asserted, causing DUT to remain in permanent reset.",
                    rtl_file=mod.filename,
                    rtl_line=rst_p.line,
                    tb_file=tb.filename,
                    tb_line=tb.resets[0].line,
                    evidence="Reset asserted without corresponding release event.",
                    suggested_action=scenario,
                    finding_id=f.id
                ))

        # Gap 3: Unchecked DUT Outputs (HIGH SEVERITY)
        for chk in tb.output_checks:
            if chk.check_type == "NONE":
                gap_id += 1
                scenario, snippet = dataflow.generate_stimulus_suggestion(chk.dut_output, f"Output {chk.dut_output}", "OUTPUT_CHECK") if dataflow else ("", "")
                f = self._create_finding(
                    category="OUTPUT_CHECK",
                    title=f"DUT Output '{chk.dut_output}' is Never Checked or Observed",
                    expression=f"output {chk.dut_output}",
                    rtl_file=mod.filename,
                    rtl_line=[p.line for p in mod.ports if p.name == chk.dut_output][0] if any(p.name == chk.dut_output for p in mod.ports) else 1,
                    what_was_found=f"Output port '{chk.dut_output}' declared but has 0 observation or checking evidence in TB.",
                    where_found=f"{mod.filename}",
                    tb_evidence=f"Zero $display, $monitor, if-checks, or assertions refer to '{chk.dut_output}'.",
                    reasoning="Simulating inputs without asserting expected output response creates a false sense of verification.",
                    confidence="HIGH",
                    status="⚠ POTENTIALLY UNTESTED",
                    suggested_scenario=scenario,
                    stimulus_snippet=snippet
                )
                chk.finding_id = f.id
                gaps.append(CoverageGap(
                    id=f"GAP-{gap_id:03d}",
                    severity="HIGH",
                    title=f"DUT Output '{chk.dut_output}' is Never Checked or Observed",
                    description=f"The DUT output '{chk.dut_output}' is declared in RTL but is completely unreferenced and unverified in the testbench.",
                    rtl_file=mod.filename,
                    rtl_line=[p.line for p in mod.ports if p.name == chk.dut_output][0] if any(p.name == chk.dut_output for p in mod.ports) else 1,
                    tb_file=tb.filename,
                    tb_line=1,
                    evidence=f"Zero $display, $monitor, if-checks, or assertions refer to '{chk.dut_output}'.",
                    suggested_action=f"Add an expected-value check or assertion for '{chk.dut_output}'.",
                    finding_id=f.id
                ))

        # Gap 4: Case statement items untested (MEDIUM SEVERITY)
        for cs in case_stmts:
            for item in cs.items:
                if not item.is_default and not item.stimulated:
                    gap_id += 1
                    scenario, snippet = dataflow.generate_stimulus_suggestion(f"{cs.expr} == {item.label}", f"Case Item L{item.start_line}", "CASE_ITEM") if dataflow else ("", "")
                    f = self._create_finding(
                        category="BRANCH",
                        title=f"Case Item '{item.label}' in '{cs.expr}' Potentially Untested",
                        expression=f"case ({cs.expr}) -> {item.label}",
                        rtl_file=mod.filename,
                        rtl_line=item.start_line,
                        what_was_found=f"Unvisited case arm '{item.label}' in {cs.expr}.",
                        where_found=f"{mod.filename}:{item.start_line}",
                        tb_evidence=f"Testbench drives values for '{cs.expr}', but '{item.label}' was omitted.",
                        reasoning=f"Functional branch for opcode/mode '{item.label}' was not driven in TB vectors.",
                        confidence="HIGH",
                        status="⚠ POTENTIALLY UNTESTED",
                        suggested_scenario=scenario,
                        stimulus_snippet=snippet
                    )
                    gaps.append(CoverageGap(
                        id=f"GAP-{gap_id:03d}",
                        severity="MEDIUM",
                        title=f"Case Item '{item.label}' in '{cs.expr}' Potentially Untested",
                        description=f"In case ({cs.expr}) at line {cs.line}, item '{item.label}' does not appear to be stimulated by any testbench vector.",
                        rtl_file=mod.filename,
                        rtl_line=item.start_line,
                        tb_file=tb.filename,
                        tb_line=1,
                        evidence=f"Testbench drives values for '{cs.expr}', but '{item.label}' is never driven.",
                        suggested_action=f"Drive {cs.expr} = {item.values[0] if item.values else item.label} in a test vector to exercise this branch.",
                        finding_id=f.id
                    ))

        # Gap 5: Untested Branches (MEDIUM SEVERITY)
        for br in branches:
            if br.status == "POTENTIALLY_UNTESTED" and br.branch_type in ("if_then", "if_else"):
                gap_id += 1
                gaps.append(CoverageGap(
                    id=f"GAP-{gap_id:03d}",
                    severity="MEDIUM",
                    title=f"Branch {br.id} at line {br.line} Potentially Untested",
                    description=f"Branch {br.id} ({br.condition_expr}) has no detected stimulus path in the testbench.",
                    rtl_file=mod.filename,
                    rtl_line=br.line,
                    tb_file=tb.filename,
                    tb_line=1,
                    evidence="Condition terms were not driven to the required polarity in TB.",
                    suggested_action=f"Provide testbench inputs that trigger condition '{br.condition_expr}'.",
                    finding_id=br.finding_id
                ))

        # Gap 6: Signals with Limited Stimulus (MEDIUM SEVERITY)
        for item in signal_mapping:
            if item.direction == "input" and item.stimulus_status == "DRIVEN_PARTIAL":
                gap_id += 1
                gaps.append(CoverageGap(
                    id=f"GAP-{gap_id:03d}",
                    severity="MEDIUM",
                    title=f"Input Port '{item.dut_port}' Has Limited Toggle Stimulus",
                    description=f"Signal '{item.dut_port}' was driven in the testbench, but static analysis detected only a single value or one-way transition.",
                    rtl_file=mod.filename,
                    rtl_line=item.rtl_line,
                    tb_file=tb.filename,
                    tb_line=item.tb_line,
                    evidence="Signal lacks both 0->1 and 1->0 stimulus transitions.",
                    suggested_action=f"Ensure '{item.dut_port}' is stimulated with both HIGH and LOW transitions during simulation.",
                    finding_id=item.finding_id
                ))

        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        gaps.sort(key=lambda g: order.get(g.severity, 3))
        return gaps

    def _calculate_module_coverage(
        self,
        mod: ModuleModel,
        tb: TestbenchModel,
        signal_mapping: List[SignalMappingItem],
        branches: List[Branch],
        conditions: List[Condition]
    ) -> ModuleCoverage:
        # Branch Coverage %
        mod_branches = [b for b in branches if mod.start_line <= b.line <= mod.end_line]
        branch_cov = round((sum(1 for b in mod_branches if b.status == "COVERED") / len(mod_branches)) * 100.0, 1) if mod_branches else 100.0

        # Condition Coverage % (N/A if no condition expressions)
        mod_conds = [c for c in conditions if mod.start_line <= c.line <= mod.end_line]
        if mod_conds:
            cond_cov = round((sum(1 for c in mod_conds if c.status == "COVERED") / len(mod_conds)) * 100.0, 1)
        else:
            cond_cov = None

        # Toggle Coverage %
        mod_inputs = [p for p in mod.ports if p.direction == "input"]
        if mod_inputs:
            tog_score = 0
            for p in mod_inputs:
                matching = [m for m in signal_mapping if m.dut_port == p.name]
                if matching:
                    st = matching[0].stimulus_status
                    if st == "DRIVEN_FULL":
                        tog_score += 100.0
                    elif st == "DRIVEN_PARTIAL":
                        tog_score += 50.0
            toggle_cov = round(tog_score / len(mod_inputs), 1)
        else:
            toggle_cov = 100.0

        # Line Coverage %
        total_exec_lines = len(mod.executable_lines)
        if total_exec_lines > 0:
            uncovered_branch_lines = set()
            for b in mod_branches:
                if b.status == "POTENTIALLY_UNTESTED":
                    for l in range(b.start_line, b.end_line + 1):
                        uncovered_branch_lines.add(l)
            covered_lines = sum(1 for l in mod.executable_lines if l not in uncovered_branch_lines)
            line_cov = round((covered_lines / total_exec_lines) * 100.0, 1)
        else:
            line_cov = 100.0

        # Smart FSM Coverage % (N/A if no FSM)
        fsm_cov = None
        if mod.fsm and mod.fsm.detected_states:
            reach_states = sum(1 for s in mod.fsm.state_reachability if s.reachable)
            stim_trans = sum(1 for t in mod.fsm.transitions if t.status == "EVIDENCE_FOUND")
            tot_items = len(mod.fsm.detected_states) + len(mod.fsm.transitions)
            fsm_cov = round(((reach_states + stim_trans) / tot_items) * 100.0, 1) if tot_items > 0 else 100.0

        # Average ONLY applicable metrics whose denominator > 0 (excluding None)
        applicable = [m for m in [line_cov, cond_cov, toggle_cov, branch_cov, fsm_cov] if m is not None]
        total_score = round(sum(applicable) / len(applicable), 1) if applicable else 100.0

        return ModuleCoverage(
            module_name=mod.name,
            score=total_score,
            line_cov=line_cov,
            cond_cov=cond_cov,
            toggle_cov=toggle_cov,
            fsm_cov=fsm_cov,
            branch_cov=branch_cov
        )

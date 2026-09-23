"""
Lightweight RTL to Testbench Dataflow and Signal Dependency Reasoning Engine.
Traces signal propagation chains, evaluates parameter boundaries, counter ranges,
and generates actionable Verilog stimulus suggestions.
"""

import re
from typing import Dict, List, Set, Optional, Tuple, Any
from .ast_nodes import ModuleModel, TestbenchModel, Parameter, Signal, Port
from .testbench_analyzer import normalize_val


class DataflowChain(dict):
    """Represents a dataflow path from a TB-driven input to an internal condition."""
    pass


class DataflowAnalyzer:
    @staticmethod
    def extract_parameters(code: str) -> Dict[str, int]:
        params = {}
        for line in code.split("\n"):
            line = line.strip()
            m = re.search(r"(?:parameter|localparam)\s+(?:\[[^\]]+\]\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^;]+);", line)
            if m:
                p_name = m.group(1).strip()
                p_val_str = m.group(2).strip()
                try:
                    norm = normalize_val(p_val_str)
                    params[p_name] = int(norm)
                except Exception:
                    try:
                        params[p_name] = int(p_val_str)
                    except Exception:
                        pass
        return params

    def __init__(self, module: ModuleModel, tb: Optional[TestbenchModel] = None, raw_rtl: str = ""):
        self.module = module
        self.tb = tb
        self.raw_rtl = raw_rtl
        self.parameters: Dict[str, int] = {}
        self.dependencies: Dict[str, Set[str]] = {}  # signal -> set of signals that drive it
        self.counters: Dict[str, Dict[str, Any]] = {}  # signal -> counter metadata
        self.assignments: List[Dict[str, Any]] = []

        if raw_rtl:
            self.parameters.update(self.extract_parameters(raw_rtl))
        self._resolve_parameters()
        self._build_dependency_graph()
        self._detect_counters()

    def _resolve_parameters(self):
        """Resolves module parameters and localparams to integer values when possible."""
        for param in self.module.parameters:
            val_str = param.default_value.strip() if hasattr(param, "default_value") else str(param).strip()
            # Try parsing integer
            try:
                # Handle hex/bin like 3'b010 or 8'd16
                norm = normalize_val(val_str)
                self.parameters[param.name] = int(norm)
            except (ValueError, TypeError):
                # Simple math expression e.g. 16
                m = re.match(r"^\d+$", val_str)
                if m:
                    self.parameters[param.name] = int(val_str)

    def analyze_counter_boundaries(self, expr: str, parameters: Optional[Dict[str, int]] = None) -> List[str]:
        if parameters:
            self.parameters.update(parameters)
        res = self.evaluate_boundary_condition(expr)
        boundaries = []
        if res.get("threshold_val") is not None:
            boundaries.append(f"{res['variable']} == {res['threshold_val']}")
            boundaries.append(f"{res['variable']} == {res['threshold_val'] + 1}")
        return boundaries

    def generate_stimulus_snippet(self, target_signal: str, condition_expr: str) -> str:
        _, snippet = self.generate_stimulus_suggestion(condition_expr, "target", "CONDITION")
        return snippet

    def trace_signal_origin(self, target_expr: str) -> List[str]:
        return self.trace_dataflow(target_expr)

    def _build_dependency_graph(self):
        """Builds lightweight LHS <- RHS dependency mapping from assignments."""
        all_signals = {p.name for p in self.module.ports} | {s.name for s in self.module.signals}

        # 1. Continuous assigns: assign target = expr;
        for ca in self.module.continuous_assigns:
            target = ca.target.strip()
            # Extract RHS signal names
            rhs_signals = self._extract_signal_identifiers(ca.expr, all_signals)
            if target not in self.dependencies:
                self.dependencies[target] = set()
            self.dependencies[target].update(rhs_signals)
            self.assignments.append({
                "target": target,
                "expr": ca.expr,
                "line": ca.line,
                "type": "continuous"
            })

        # 2. Procedural assignments from raw_rtl
        if self.raw_rtl:
            for m in re.finditer(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<=|=)\s*([^;]+);", self.raw_rtl):
                target = m.group(1).strip()
                expr = m.group(2).strip()
                if target in all_signals:
                    rhs_signals = self._extract_signal_identifiers(expr, all_signals)
                    if target not in self.dependencies:
                        self.dependencies[target] = set()
                    self.dependencies[target].update(rhs_signals)
                    self.assignments.append({
                        "target": target,
                        "expr": expr,
                        "type": "procedural"
                    })

    def get_upstream_inputs(self, target_signal: str, max_depth: int = 4) -> Set[str]:
        """Returns primary DUT inputs that drive target_signal through dependency graph."""
        known_inputs = {p.name for p in self.module.ports if p.direction == "input"}
        if target_signal in known_inputs:
            return {target_signal}

        visited = set()
        queue = [target_signal]
        upstream_inputs = set()
        depth = 0

        while queue and depth < max_depth:
            depth += 1
            next_q = []
            for sig in queue:
                if sig in visited:
                    continue
                visited.add(sig)
                deps = self.dependencies.get(sig, set())
                for dep in deps:
                    if dep in known_inputs:
                        upstream_inputs.add(dep)
                    else:
                        next_q.append(dep)
            queue = next_q

        return upstream_inputs

    def _extract_signal_identifiers(self, expr: str, known_signals: Set[str]) -> Set[str]:
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
        return {t for t in tokens if t in known_signals}

    def _detect_counters(self):
        """Detects counter and accumulator patterns (e.g. count <= count + 1)."""
        # Look for parameters and ports that act as counters
        for s in self.module.signals:
            name_lower = s.name.lower()
            if any(k in name_lower for k in ("count", "cnt", "acc", "sum", "timer", "index", "ptr")):
                self.counters[s.name] = {
                    "signal": s.name,
                    "width": s.width,
                    "line": s.line,
                    "step": 1
                }

    def trace_dataflow(self, target_expr: str) -> List[str]:
        """
        Traces the backward dataflow chain from target_expr to primary inputs.
        Example return:
        ['PDM_DATA (TB Input)', 'pdm_count (Accumulator)', 'pdm_count >= ACTIVITY_THRESHOLD', 'activity_detected']
        """
        known_inputs = {p.name: p for p in self.module.ports if p.direction == "input"}
        all_signals = {p.name for p in self.module.ports} | {s.name for s in self.module.signals}

        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", target_expr)
        ref_signals = [t for t in tokens if t in all_signals]

        chain = []
        visited = set()

        for sig in ref_signals:
            if sig in known_inputs:
                chain.append(f"{sig} (DUT Input)")
            elif sig in self.counters:
                # Check what drives this counter
                dep_inputs = []
                for inp_name in known_inputs:
                    dep_inputs.append(f"{inp_name} (TB Input)")
                if dep_inputs:
                    chain.append(dep_inputs[0])
                chain.append(f"{sig} (Internal Counter/Accumulator)")
            else:
                chain.append(f"{sig} (Internal Logic)")

        # Add target evaluation step
        chain.append(f"Evaluates: {target_expr}")
        # Deduplicate while preserving order
        unique_chain = []
        for c in chain:
            if c not in unique_chain:
                unique_chain.append(c)

        return unique_chain if len(unique_chain) > 1 else [f"{target_expr} (Direct input evaluation)"]

    def evaluate_boundary_condition(self, expr: str) -> Dict[str, Any]:
        """
        Analyzes comparison boundaries like:
        sample_count == WINDOW_SIZE - 1
        count >= THRESHOLD
        """
        # Check comparison operator
        m = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(==|>=|<=|>|<|!=)\s*(.*)", expr.strip())
        if not m:
            return {
                "has_boundary": False,
                "variable": None,
                "operator": None,
                "threshold_raw": None,
                "threshold_val": None,
                "inferred_range": "Unknown",
                "boundary_status": "? INSUFFICIENT EVIDENCE"
            }

        var = m.group(1).strip()
        op = m.group(2).strip()
        rhs = m.group(3).strip()

        # Try to resolve RHS value
        threshold_val = None
        for p_name, p_val in self.parameters.items():
            if p_name in rhs:
                # Replace param name with value and evaluate
                eval_rhs = rhs.replace(p_name, str(p_val))
                try:
                    threshold_val = eval(eval_rhs)
                except Exception:
                    threshold_val = p_val
                break

        if threshold_val is None:
            try:
                threshold_val = int(normalize_val(rhs))
            except Exception:
                pass

        # Estimate inferred range from TB cycles
        inferred_max = 0
        if self.tb:
            # Count repeats, assignments, or delay blocks
            # Look at stimulus count or delay total
            clock_cycles = 0
            if self.tb.clocks:
                total_delay = max([s.time_delay or 0 for s in self.tb.stimulus], default=100)
                clock_period = self.tb.clocks[0].period or 10
                clock_cycles = int(total_delay / clock_period)

            repeat_cycles = 0
            raw_tb = getattr(self.tb, "raw_text", "")
            if raw_tb:
                for rep_m in re.finditer(r"repeat\s*\(\s*(\d+)\s*\)", raw_tb):
                    try:
                        repeat_cycles += int(rep_m.group(1))
                    except ValueError:
                        pass

            inferred_max = max(len(self.tb.stimulus), clock_cycles, repeat_cycles, 8)

        # Boundary status
        if threshold_val is not None:
            if inferred_max > threshold_val:
                status = "✓ STATICALLY REACHABLE"
                confidence = "HIGH"
            elif inferred_max == threshold_val:
                status = "⚠ POTENTIALLY UNTESTED"
                confidence = "MEDIUM"
            else:
                status = "⚠ POTENTIALLY UNTESTED"
                confidence = "HIGH"
        else:
            status = "? INSUFFICIENT EVIDENCE"
            confidence = "LOW"

        return {
            "has_boundary": True,
            "variable": var,
            "operator": op,
            "threshold_raw": rhs,
            "threshold_val": threshold_val,
            "inferred_range": f"[0 .. {inferred_max}]" if inferred_max > 0 else "Not driven",
            "boundary_status": status,
            "confidence": confidence
        }

    def evaluate_condition_reachability(self, cond_expr: str, dut_to_tb_vals: Dict[str, List[str]]) -> Tuple[bool, str, str]:
        """
        Domain-agnostic evaluation of whether a condition is statically reachable based on AST dataflow.
        Returns: (is_reachable, confidence, explanation)
        """
        clean_cond = cond_expr.replace("== TRUE", "").replace("== FALSE", "").strip()
        if not clean_cond or "unconditional" in clean_cond.lower():
            return True, "HIGH", "Unconditional state advance."

        # 1. Check direct boundary / comparison conditions: e.g. count >= LIMIT or count == MAX
        boundary = self.evaluate_boundary_condition(clean_cond)
        if boundary.get("has_boundary") and boundary.get("threshold_val") is not None:
            if boundary.get("boundary_status") == "✓ STATICALLY REACHABLE":
                return True, "HIGH", f"Counter boundary '{boundary['variable']} ({boundary['operator']} {boundary['threshold_val']})' is statically reachable within testbench duration ({boundary['inferred_range']})."
            else:
                return False, "MEDIUM", f"Counter boundary '{boundary['variable']} ({boundary['operator']} {boundary['threshold_val']})' is not crossed within testbench duration ({boundary['inferred_range']})."

        # 2. Extract referenced variables in condition
        cond_vars = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", clean_cond)
        known_inputs = {p.name for p in self.module.ports if p.direction == "input"}

        for var in cond_vars:
            # Case A: Variable is a primary DUT input
            if var in dut_to_tb_vals and dut_to_tb_vals[var]:
                vals = dut_to_tb_vals[var]
                active_vals = [v for v in vals if normalize_val(v) not in ("0", "1'b0", "0'b0")]
                if active_vals:
                    return True, "HIGH", f"Primary input '{var}' is driven with activating stimulus: {active_vals[:3]}."

            # Case B: Variable is an internal register or wire
            if var not in known_inputs:
                upstreams = self.get_upstream_inputs(var)
                active_ups = [u for u in upstreams if any(normalize_val(v) not in ("0", "1'b0") for v in dut_to_tb_vals.get(u, []))]

                # Look up assignments that compute this internal variable
                for asgn in self.assignments:
                    if asgn.get("target") == var:
                        rhs_expr = asgn.get("expr", "")
                        b_info = self.evaluate_boundary_condition(rhs_expr)
                        if b_info.get("has_boundary") and b_info.get("threshold_val") is not None:
                            if b_info.get("boundary_status") == "✓ STATICALLY REACHABLE" and active_ups:
                                return True, "HIGH", f"Internal condition '{var}' is reached via dataflow: upstream inputs ({', '.join(active_ups)}) satisfy boundary '{b_info['variable']} {b_info['operator']} {b_info['threshold_val']}'."
                            elif b_info.get("boundary_status") != "✓ STATICALLY REACHABLE":
                                return False, "MEDIUM", f"Internal condition '{var}' depends on boundary '{b_info['variable']}' which is not reached in testbench."

                if active_ups:
                    return True, "HIGH", f"Internal signal '{var}' is driven via active upstream primary inputs: {', '.join(active_ups)}."

        return False, "MEDIUM", f"No activating stimulus driven for condition trigger '{clean_cond}'."

    def generate_stimulus_suggestion(self, expr: str, location_desc: str, finding_type: str) -> Tuple[str, str]:
        """
        Generates actionable verification advice and a copyable Verilog stimulus snippet.
        Returns: (suggested_scenario_text, verilog_stimulus_snippet)
        """
        # 1. Output checking gap
        if finding_type == "OUTPUT_CHECK":
            out_name = expr
            scenario = (
                f"DUT output '{out_name}' is driven by internal logic but never inspected in the testbench. "
                f"Add an expected-value assertion or self-checking equality comparison."
            )
            snippet = (
                f"// Verify DUT output '{out_name}' against expected behavior\n"
                f"if ({out_name} !== expected_{out_name}) begin\n"
                f"    $error(\"[TB ASSERTION FAILED] Time=%0t | {out_name} mismatch: Expected %h, Got %h\", $time, expected_{out_name}, {out_name});\n"
                f"end else begin\n"
                f"    $display(\"[TB PASS] Time=%0t | {out_name} verified: %h\", $time, {out_name});\n"
                f"end"
            )
            return scenario, snippet

        # 2. Reset gap
        if finding_type == "RESET":
            rst_name = expr
            scenario = f"Execute a complete reset sequence asserting and deasserting '{rst_name}' to properly initialize sequential registers."
            snippet = (
                f"// Proper power-on reset pulse\n"
                f"{rst_name} = 1;\n"
                f"#20;\n"
                f"{rst_name} = 0; // Release reset\n"
                f"#10;"
            )
            return scenario, snippet

        # 3. FSM Transition gap
        if finding_type == "FSM_TRANSITION":
            scenario = f"Drive stimulus that satisfies condition '{location_desc}' to exercise this state machine transition."
            snippet = (
                f"// Stimulus to trigger FSM transition ({location_desc})\n"
                f"#10;\n"
                f"// Drive required trigger signals\n"
                f"#20;\n"
                f"// Wait for clock edge to verify state change\n"
                f"@(posedge clk);"
            )
            return scenario, snippet

        # 4. Counter / Boundary condition
        boundary = self.evaluate_boundary_condition(expr)
        if boundary["has_boundary"] and boundary["threshold_val"] is not None:
            var = boundary["variable"]
            th = boundary["threshold_val"]
            raw_th = boundary["threshold_raw"]
            scenario = (
                f"Condition '{expr}' requires '{var}' to reach {raw_th} ({th}). "
                f"Supply sufficient active clock cycles or input pulses in a repeat loop to cross this boundary."
            )
            snippet = (
                f"// Stimulate boundary for '{expr}'\n"
                f"repeat ({th + 2}) begin\n"
                f"    @(posedge clk);\n"
                f"    // Drive active enable / pulse\n"
                f"end\n"
                f"#10;\n"
                f"// Check that boundary condition triggered"
            )
            return scenario, snippet

        # 5. Generic Branch or Condition
        scenario = f"Drive testbench inputs to satisfy '{expr}' to exercise this execution path."
        snippet = (
            f"// Stimulus scenario for: {expr}\n"
            f"#10;\n"
            f"// Set input vectors\n"
            f"#10;\n"
            f"@(posedge clk);"
        )
        return scenario, snippet

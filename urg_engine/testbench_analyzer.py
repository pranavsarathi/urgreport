"""
Testbench Stimulus, Connection, and Output Observation Analyzer.
Analyzes TB constructs without running simulation.
"""

import re
from typing import List, Dict, Set, Optional, Tuple, Any
from .ast_nodes import (
    DUTInstance, TBPortConnection, ClockGenerator, ResetSequence,
    StimulusAssignment, SignalToggle, OutputCheck, TestbenchModel,
    DesignModel, ModuleModel
)
from .tokenizer import Token, VerilogLexer, TokenStream


def normalize_val(val_str: str) -> str:
    """Normalizes Verilog literals for comparison (e.g., 3'b010 -> 2, 8'h0A -> 10)."""
    s = val_str.strip().lower().replace("_", "")
    # Check for sized: <size>'[bhd]<val>
    m = re.match(r"(\d+)?'([bhod])([0-9a-fxz]+)", s)
    if m:
        base = m.group(2)
        digits = m.group(3)
        try:
            if base == 'b':
                return str(int(digits, 2))
            elif base == 'h':
                return str(int(digits, 16))
            elif base == 'o':
                return str(int(digits, 8))
            elif base == 'd':
                return str(int(digits, 10))
        except ValueError:
            return digits
    try:
        return str(int(s))
    except ValueError:
        return s


class TestbenchAnalyzer:
    __test__ = False

    def __init__(self, filename: str = "testbench.v"):
        self.filename = filename

    def analyze(self, tb_text: str, design: Optional[DesignModel] = None) -> TestbenchModel:
        lexer = VerilogLexer(tb_text)
        tokens = lexer.tokenize()
        stream = TokenStream(tokens)

        dut_instances: List[DUTInstance] = []
        clocks: List[ClockGenerator] = []
        resets: List[ResetSequence] = []
        stimulus: List[StimulusAssignment] = []
        signal_values: Dict[str, List[Tuple[str, int]]] = {}  # sig -> list of (val, line)
        output_checks: List[OutputCheck] = []
        initial_blocks_count = 0
        always_blocks_count = 0
        tasks_count = 0
        total_assertions = 0

        known_modules = {m.name: m for m in design.modules} if design else {}

        # 1. First Pass: Detect DUT Instantiations
        dut_instances = self._detect_dut_instances(tokens, known_modules)

        # 2. Detect Clocks
        clocks = self._detect_clocks(tokens, tb_text)

        # 3. Detect Resets
        resets = self._detect_resets(tokens, tb_text)

        # 4. Detect Stimulus Assignments (e.g. sig = val; or sig <= val;)
        stimulus, signal_values = self._detect_stimulus(tokens)

        # 5. Detect Initial, Always, Task, Assertion counts
        for i, tok in enumerate(tokens):
            if tok.value == "initial":
                initial_blocks_count += 1
            elif tok.value in ("always", "always_comb", "always_ff"):
                always_blocks_count += 1
            elif tok.value == "task":
                tasks_count += 1
            elif tok.value == "assert":
                total_assertions += 1

        # 6. Compute Toggles from signal_values
        toggles: Dict[str, SignalToggle] = {}
        for sig, val_entries in signal_values.items():
            vals = [v for v, l in val_entries]
            norm_vals = [normalize_val(v) for v in vals]
            has_01 = False
            has_10 = False

            # Check consecutive transitions
            for i in range(len(norm_vals) - 1):
                v1, v2 = norm_vals[i], norm_vals[i + 1]
                if v1 == "0" and v2 != "0":
                    has_01 = True
                elif v1 != "0" and v2 == "0":
                    has_10 = True
                elif v1 != v2:
                    # Non-zero change
                    has_01 = True
                    has_10 = True

            # If clock, toggle is definitely FULL
            if any(c.signal_name == sig for c in clocks):
                has_01 = True
                has_10 = True

            if has_01 and has_10:
                st = "FULL"
            elif has_01 or has_10 or len(set(vals)) > 1:
                st = "LIMITED"
            elif len(vals) == 1:
                st = "LIMITED"
            else:
                st = "NONE"

            toggles[sig] = SignalToggle(
                signal_name=sig,
                values_seen=vals,
                has_0_to_1=has_01,
                has_1_to_0=has_10,
                status=st
            )

        # 7. Output Checking Analysis
        # Determine DUT outputs from design
        dut_outputs: Dict[str, str] = {}  # dut_port_name -> tb_signal_name
        if dut_instances:
            primary_dut = dut_instances[0]
            dut_mod = known_modules.get(primary_dut.module_name)
            if dut_mod:
                out_ports = {p.name for p in dut_mod.ports if p.direction == "output"}
                for conn in primary_dut.connections:
                    if conn.port_name in out_ports:
                        dut_outputs[conn.port_name] = conn.tb_expr
                    elif not conn.port_name:
                        pass
            elif design and design.modules:
                # Fallback to top module ports
                top_m = design.modules[0]
                out_ports = {p.name for p in top_m.ports if p.direction == "output"}
                for conn in primary_dut.connections:
                    if conn.port_name in out_ports:
                        dut_outputs[conn.port_name] = conn.tb_expr
        elif design and design.modules:
            # If no instantiation explicitly found, match output names directly
            top_m = design.modules[0]
            for p in top_m.ports:
                if p.direction == "output":
                    dut_outputs[p.name] = p.name

        output_checks = self._detect_output_checks(tokens, tb_text, dut_outputs)

        return TestbenchModel(
            dut_instances=dut_instances,
            clocks=clocks,
            resets=resets,
            stimulus=stimulus,
            toggles=toggles,
            output_checks=output_checks,
            initial_blocks_count=initial_blocks_count,
            always_blocks_count=always_blocks_count,
            tasks_count=tasks_count,
            total_assertions=total_assertions,
            filename=self.filename,
            raw_text=tb_text
        )

    def _detect_dut_instances(self, tokens: List[Token], known_modules: Dict[str, ModuleModel]) -> List[DUTInstance]:
        instances: List[DUTInstance] = []
        i = 0
        n = len(tokens)

        while i < n:
            tok = tokens[i]
            # Check if this token matches a known module name, or looks like a module instantiation
            is_mod_match = tok.value in known_modules
            if (is_mod_match or tok.type == "IDENTIFIER") and i + 2 < n:
                next_tok = tokens[i + 1]
                third_tok = tokens[i + 2]

                # Pattern: ModName [#(params)] inst_name ( ... )
                # Skip parameters if present: #( ... )
                param_offset = 0
                if next_tok.value == "#" and third_tok.value == "(":
                    depth = 1
                    j = i + 3
                    while j < n and depth > 0:
                        if tokens[j].value == "(":
                            depth += 1
                        elif tokens[j].value == ")":
                            depth -= 1
                        j += 1
                    param_offset = j - i - 1

                idx_after_params = i + 1 + param_offset
                if idx_after_params + 1 < n:
                    inst_tok = tokens[idx_after_params]
                    paren_tok = tokens[idx_after_params + 1]

                    # Verify it's an instantiation: Module inst ( ... );
                    if (is_mod_match or tok.value not in ("module", "input", "output", "wire", "reg", "logic", "assign", "always", "initial", "begin")) \
                       and inst_tok.type == "IDENTIFIER" and paren_tok.value == "(":
                        
                        mod_name = tok.value
                        inst_name = inst_tok.value
                        inst_line = tok.line

                        # Collect tokens inside ( ... )
                        conn_tokens: List[Token] = []
                        depth = 1
                        k = idx_after_params + 2
                        while k < n and depth > 0:
                            if tokens[k].value == "(":
                                depth += 1
                            elif tokens[k].value == ")":
                                depth -= 1
                                if depth == 0:
                                    break
                            if depth > 0:
                                conn_tokens.append(tokens[k])
                            k += 1

                        # Parse connections
                        conns = self._parse_instance_connections(conn_tokens, mod_name, known_modules)
                        if conns or is_mod_match:
                            instances.append(DUTInstance(
                                module_name=mod_name,
                                instance_name=inst_name,
                                connections=conns,
                                line=inst_line
                            ))
                            i = k
            i += 1

        return instances

    def _parse_instance_connections(self, conn_tokens: List[Token], mod_name: str, known_modules: Dict[str, ModuleModel]) -> List[TBPortConnection]:
        conns: List[TBPortConnection] = []
        if not conn_tokens:
            return conns

        # Check if named port connections: .port(tb_net)
        has_dot = any(t.value == "." for t in conn_tokens)
        if has_dot:
            i = 0
            n = len(conn_tokens)
            while i < n:
                if conn_tokens[i].value == "." and i + 1 < n:
                    port_name = conn_tokens[i + 1].value
                    line = conn_tokens[i].line
                    i += 2
                    if i < n and conn_tokens[i].value == "(":
                        i += 1
                        inner = []
                        depth = 1
                        while i < n and depth > 0:
                            if conn_tokens[i].value == "(":
                                depth += 1
                            elif conn_tokens[i].value == ")":
                                depth -= 1
                                if depth == 0:
                                    break
                            if depth > 0:
                                inner.append(conn_tokens[i].value)
                            i += 1
                        tb_expr = " ".join(inner).strip()
                        conns.append(TBPortConnection(port_name=port_name, tb_expr=tb_expr, line=line))
                i += 1
        else:
            # Positional connections: a, b, c
            parts = []
            curr = []
            depth = 0
            for t in conn_tokens:
                if t.value in ("(", "[", "{"):
                    depth += 1
                elif t.value in (")", "]", "}"):
                    depth -= 1
                if t.value == "," and depth == 0:
                    parts.append(curr)
                    curr = []
                else:
                    curr.append(t)
            if curr:
                parts.append(curr)

            mod = known_modules.get(mod_name)
            port_list = mod.ports if mod else []

            for idx, p in enumerate(parts):
                tb_expr = " ".join(t.value for t in p).strip()
                port_name = port_list[idx].name if idx < len(port_list) else f"port_{idx}"
                line = p[0].line if p else 1
                conns.append(TBPortConnection(port_name=port_name, tb_expr=tb_expr, line=line))

        return conns

    def _detect_clocks(self, tokens: List[Token], tb_text: str) -> List[ClockGenerator]:
        clocks: List[ClockGenerator] = []
        seen = set()

        # Regex scan for common clock generation patterns
        # 1. always #5 clk = ~clk;
        clk_patterns = [
            r'always\s*#(\d+)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*~([a-zA-Z_][a-zA-Z0-9_]*)',
            r'forever\s*#(\d+)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*~([a-zA-Z_][a-zA-Z0-9_]*)',
            r'always\s*begin\s*#(\d+)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*~([a-zA-Z_][a-zA-Z0-9_]*)',
        ]

        for pat in clk_patterns:
            for match in re.finditer(pat, tb_text):
                period = float(match.group(1)) * 2
                clk_name = match.group(2)
                if clk_name not in seen:
                    seen.add(clk_name)
                    # Find line number
                    line_num = tb_text[:match.start()].count('\n') + 1
                    clocks.append(ClockGenerator(
                        signal_name=clk_name,
                        period=period,
                        pattern=match.group(0).strip(),
                        line=line_num
                    ))

        # Also search for clock variables toggled in always blocks via tokens
        i = 0
        n = len(tokens)
        while i < n - 4:
            if tokens[i].value in ("always", "forever") and tokens[i + 1].value == "#":
                try:
                    half_period = float(tokens[i + 2].value)
                    sig = tokens[i + 3].value
                    op = tokens[i + 4].value
                    if op in ("=", "<=") and i + 5 < n and tokens[i + 5].value == "~":
                        if sig not in seen:
                            seen.add(sig)
                            clocks.append(ClockGenerator(
                                signal_name=sig,
                                period=half_period * 2,
                                pattern=f"#{half_period} {sig} = ~{sig}",
                                line=tokens[i].line
                            ))
                except (ValueError, IndexError):
                    pass
            i += 1

        return clocks

    def _detect_resets(self, tokens: List[Token], tb_text: str) -> List[ResetSequence]:
        resets: List[ResetSequence] = []
        seen = set()

        # Find signals with names containing rst, reset
        reset_candidates = set()
        for tok in tokens:
            if tok.type == "IDENTIFIER" and any(k in tok.value.lower() for k in ("rst", "reset")):
                reset_candidates.add(tok.value)

        for rst_name in reset_candidates:
            # Check driving pattern in initial blocks
            # e.g., reset = 1; #20; reset = 0; or rst_n = 0; #20; rst_n = 1;
            pat = rf'{rst_name}\s*(?:<=|=)\s*([01]|1\'b[01])'
            matches = list(re.finditer(pat, tb_text))
            if matches:
                first_val = matches[0].group(1).replace("1'b", "")
                asserted = True
                released = len(matches) > 1

                # If first assigned 1, then released with 0 -> ACTIVE_HIGH
                # If first assigned 0, then released with 1 -> ACTIVE_LOW
                if "n" in rst_name.lower() or "b" in rst_name.lower() or first_val == "0":
                    polarity = "ACTIVE_LOW"
                else:
                    polarity = "ACTIVE_HIGH"

                line_num = tb_text[:matches[0].start()].count('\n') + 1
                resets.append(ResetSequence(
                    signal_name=rst_name,
                    polarity=polarity,
                    asserted=asserted,
                    released=released,
                    line=line_num
                ))
                seen.add(rst_name)

        return resets

    def _detect_stimulus(self, tokens: List[Token]) -> Tuple[List[StimulusAssignment], Dict[str, List[Tuple[str, int]]]]:
        stimulus: List[StimulusAssignment] = []
        signal_values: Dict[str, List[Tuple[str, int]]] = {}

        i = 0
        n = len(tokens)
        current_delay = 0

        while i < n:
            tok = tokens[i]

            # Track delays: #10
            if tok.value == "#" and i + 1 < n and tokens[i + 1].type == "NUMBER":
                try:
                    current_delay += int(tokens[i + 1].value)
                except ValueError:
                    pass

            # Detect assignment: signal [ [idx] ] = value ; or signal <= value ;
            if tok.type == "IDENTIFIER" and i + 1 < n:
                sig_name = tok.value
                sig_line = tok.line
                j = i + 1

                # Handle bit or part select: sig[3] or sig[7:0]
                if tokens[j].value == "[":
                    while j < n and tokens[j].value != "]":
                        j += 1
                    if j < n and tokens[j].value == "]":
                        j += 1

                if j < n and tokens[j].value in ("=", "<="):
                    op = tokens[j].value
                    # Extract rhs value until ';' or ','
                    k = j + 1
                    val_parts = []
                    while k < n and tokens[k].value not in (";", ",", "end", "begin"):
                        val_parts.append(tokens[k].value)
                        k += 1
                    val_str = " ".join(val_parts).strip()

                    # Avoid capturing clock toggle `~clk` as stimulus assignment
                    if not val_str.startswith("~") and not sig_name in ("clk", "clock"):
                        stimulus.append(StimulusAssignment(
                            signal_name=sig_name,
                            value=val_str,
                            time_delay=current_delay,
                            line=sig_line
                        ))
                        if sig_name not in signal_values:
                            signal_values[sig_name] = []
                        signal_values[sig_name].append((val_str, sig_line))

                    i = k
            i += 1

        return stimulus, signal_values

    def _detect_output_checks(self, tokens: List[Token], tb_text: str, dut_outputs: Dict[str, str]) -> List[OutputCheck]:
        output_checks: List[OutputCheck] = []

        # Map each DUT output port to set of names representing it in TB
        port_to_names: Dict[str, Set[str]] = {}
        name_to_port: Dict[str, str] = {}
        for port_name, tb_sig in dut_outputs.items():
            names = {port_name}
            name_to_port[port_name] = port_name
            if tb_sig and tb_sig != port_name:
                names.add(tb_sig)
                name_to_port[tb_sig] = port_name
            port_to_names[port_name] = names

        # Track per-port check evidence
        port_ifs: Dict[str, List[Tuple[str, int]]] = {p: [] for p in dut_outputs}
        port_asserts: Dict[str, List[Tuple[str, int]]] = {p: [] for p in dut_outputs}
        port_displays: Dict[str, List[Tuple[str, int]]] = {p: [] for p in dut_outputs}

        # 1. Parse tokens for if-statements, assertions, and display statements
        i = 0
        n = len(tokens)
        comp_ops = {"==", "!=", "===", "!=="}

        while i < n:
            tok = tokens[i]

            # If-statement check: if (...)
            if tok.type == "KEYWORD" and tok.value == "if" and i + 1 < n and tokens[i + 1].value == "(":
                j = i + 2
                depth = 1
                cond_tokens: List[Token] = []
                while j < n and depth > 0:
                    if tokens[j].value == "(":
                        depth += 1
                    elif tokens[j].value == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    cond_tokens.append(tokens[j])
                    j += 1

                cond_line = tok.line

                # Split condition tokens by || and && at base paren depth
                subclauses: List[List[Token]] = [[]]
                p_depth = 0
                for ct in cond_tokens:
                    if ct.value in ("(", "["):
                        p_depth += 1
                    elif ct.value in (")", "]"):
                        p_depth = max(0, p_depth - 1)

                    if p_depth == 0 and ct.value in ("||", "&&"):
                        subclauses.append([])
                    else:
                        subclauses[-1].append(ct)

                # For each subclause, check if it contains a comparison operator
                for clause in subclauses:
                    has_comp = any(t.value in comp_ops for t in clause)
                    if has_comp:
                        clause_str = " ".join(t.value for t in clause)
                        # Check each matching output signal in this clause
                        seen_ports_in_clause = set()
                        for t in clause:
                            if t.type == "IDENTIFIER" and t.value in name_to_port:
                                port = name_to_port[t.value]
                                if port not in seen_ports_in_clause:
                                    seen_ports_in_clause.add(port)
                                    port_ifs[port].append((clause_str, cond_line))

            # Assertion check: assert(...)
            elif (tok.value == "assert" or tok.value.startswith("assert_")) and i + 1 < n and tokens[i + 1].value == "(":
                j = i + 2
                depth = 1
                assert_tokens: List[Token] = []
                while j < n and depth > 0:
                    if tokens[j].value == "(":
                        depth += 1
                    elif tokens[j].value == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    assert_tokens.append(tokens[j])
                    j += 1

                assert_line = tok.line
                assert_text = "assert(" + " ".join(t.value for t in assert_tokens) + ")"
                seen_ports_in_assert = set()
                for t in assert_tokens:
                    if t.type == "IDENTIFIER" and t.value in name_to_port:
                        port = name_to_port[t.value]
                        if port not in seen_ports_in_assert:
                            seen_ports_in_assert.add(port)
                            port_asserts[port].append((assert_text, assert_line))

            # Display / Monitor check
            elif tok.value in ("$display", "$monitor", "$strobe", "$write") and i + 1 < n and tokens[i + 1].value == "(":
                j = i + 2
                depth = 1
                disp_tokens: List[Token] = []
                while j < n and depth > 0:
                    if tokens[j].value == "(":
                        depth += 1
                    elif tokens[j].value == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    disp_tokens.append(tokens[j])
                    j += 1

                disp_line = tok.line
                disp_text = tok.value + "(" + " ".join(t.value for t in disp_tokens) + ")"
                seen_ports_in_disp = set()
                for t in disp_tokens:
                    if t.type == "IDENTIFIER" and t.value in name_to_port:
                        port = name_to_port[t.value]
                        if port not in seen_ports_in_disp:
                            seen_ports_in_disp.add(port)
                            port_displays[port].append((disp_text, disp_line))

            i += 1

        # Also fallback regex for lines not caught by token stream
        for port_name, names in port_to_names.items():
            if not port_asserts[port_name] and not port_ifs[port_name]:
                for sig in names:
                    m_assert = re.search(rf'assert\s*\([^;]*\b{sig}\b[^;]*\)', tb_text)
                    if m_assert:
                        line_no = tb_text[:m_assert.start()].count('\n') + 1
                        port_asserts[port_name].append((m_assert.group(0).strip(), line_no))
                        break
                    m_if = re.search(rf'if\s*\([^;]*\b{sig}\b\s*(?:!==|!=|==|===)[^;]*\)', tb_text)
                    if m_if:
                        line_no = tb_text[:m_if.start()].count('\n') + 1
                        port_ifs[port_name].append((m_if.group(0).strip(), line_no))
                        break

        # Assemble OutputCheck objects for all DUT output ports
        for port_name in dut_outputs:
            assert_list = port_asserts[port_name]
            if_list = port_ifs[port_name]
            disp_list = port_displays[port_name]

            if assert_list:
                chk_type = "ASSERTION"
                first_detail, first_line = assert_list[0]
                tot = len(assert_list) + len(if_list)
                details = f"Verified by assertion: {first_detail}" if tot == 1 else f"Verified by {tot} check(s), e.g. assertion at L{first_line}"
                output_checks.append(OutputCheck(
                    dut_output=port_name,
                    check_type=chk_type,
                    details=details,
                    line=first_line,
                    is_verified=True,
                    is_compared=True,
                    is_asserted=True,
                    is_displayed=len(disp_list) > 0,
                    check_count=tot,
                    verification_status="VERIFIED_ASSERTION"
                ))
            elif if_list:
                chk_type = "IF_CHECK"
                first_detail, first_line = if_list[0]
                tot = len(if_list)
                details = f"Compared in {tot} check(s), e.g.: if ({first_detail})" if tot > 1 else f"Compared at L{first_line}: if ({first_detail})"
                output_checks.append(OutputCheck(
                    dut_output=port_name,
                    check_type=chk_type,
                    details=details,
                    line=first_line,
                    is_verified=True,
                    is_compared=True,
                    is_asserted=False,
                    is_displayed=len(disp_list) > 0,
                    check_count=tot,
                    verification_status="VERIFIED_COMPARISON"
                ))
            elif disp_list:
                chk_type = "DISPLAY"
                first_detail, first_line = disp_list[0]
                tot = len(disp_list)
                details = f"Observed in {tot} display call(s) without comparison, e.g. at L{first_line}"
                output_checks.append(OutputCheck(
                    dut_output=port_name,
                    check_type=chk_type,
                    details=details,
                    line=first_line,
                    is_verified=False,
                    is_compared=False,
                    is_asserted=False,
                    is_displayed=True,
                    check_count=tot,
                    verification_status="OBSERVED_DISPLAY"
                ))
            else:
                output_checks.append(OutputCheck(
                    dut_output=port_name,
                    check_type="NONE",
                    details=f"Output port '{port_name}' not observed or compared in testbench",
                    line=1,
                    is_verified=False,
                    is_compared=False,
                    is_asserted=False,
                    is_displayed=False,
                    check_count=0,
                    verification_status="UNCHECKED"
                ))

        return output_checks

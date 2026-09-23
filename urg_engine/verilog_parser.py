"""
Verilog RTL Parser and Structural AST Extractor.
Parses Verilog and SystemVerilog files into a comprehensive DesignModel.
"""

import re
from typing import List, Optional, Tuple, Dict, Any, Set
from .ast_nodes import (
    Port, Signal, Parameter, AlwaysBlock, ContinuousAssign,
    Branch, Condition, ConditionTerm, CaseStatement, CaseItem,
    FsmModel, FsmTransition, ModuleModel, DesignModel,
    ModuleInstantiation, HierarchyNode, TBPortConnection
)
from .tokenizer import Token, VerilogLexer, TokenStream


class VerilogParserError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1, file: str = ""):
        super().__init__(f"[{file}:{line}:{col}] {message}")
        self.message = message
        self.line = line
        self.col = col
        self.file = file


class VerilogParser:
    def __init__(self, filename: str = "rtl.v"):
        self.filename = filename
        self.stream: Optional[TokenStream] = None
        self.modules: List[ModuleModel] = []
        self.current_module: Optional[ModuleModel] = None
        self.branch_counter = 0
        self.condition_counter = 0
        self.case_counter = 0

    def parse(self, text: str) -> DesignModel:
        lexer = VerilogLexer(text)
        tokens = lexer.tokenize()
        self.stream = TokenStream(tokens)
        self.modules = []
        self.branch_counter = 0
        self.condition_counter = 0
        self.case_counter = 0

        # Scan for modules
        while self.stream.has_next():
            tok = self.stream.current()
            if tok.value == "module":
                self._parse_module()
            else:
                self.stream.advance()

        top_mod, hierarchy = self._build_design_hierarchy(self.modules)
        return DesignModel(
            modules=self.modules,
            top_module=top_mod,
            filename=self.filename,
            files=[self.filename] if self.filename else [],
            hierarchy=hierarchy,
            total_rtl_lines=text.count('\n') + 1 if text else 0
        )

    @classmethod
    def parse_files(cls, files: List[Tuple[str, str]]) -> DesignModel:
        """
        Parses multiple Verilog / SystemVerilog files.
        files: List of (filename, file_content) tuples.
        """
        all_modules: List[ModuleModel] = []
        all_files: List[str] = []
        total_lines = 0

        for fname, content in files:
            all_files.append(fname)
            total_lines += content.count('\n') + 1
            parser = cls(filename=fname)
            try:
                design = parser.parse(content)
                all_modules.extend(design.modules)
            except Exception as e:
                # Resilient recovery: log partial analysis rather than failing all files
                failed_mod = ModuleModel(
                    name=fname.split('.')[0] if '.' in fname else fname,
                    filename=fname,
                    partial_analysis=True,
                    partial_reason=f"Partial parsing: {e}"
                )
                all_modules.append(failed_mod)

        top_mod, hierarchy = cls._build_design_hierarchy(all_modules)

        return DesignModel(
            modules=all_modules,
            top_module=top_mod,
            filename=all_files[0] if all_files else "",
            files=all_files,
            hierarchy=hierarchy,
            total_rtl_lines=total_lines
        )

    @staticmethod
    def _build_design_hierarchy(modules: List[ModuleModel]) -> Tuple[Optional[str], Optional[HierarchyNode]]:
        if not modules:
            return None, None

        mod_map = {m.name: m for m in modules}
        instantiated_counts = {m.name: 0 for m in modules}

        for m in modules:
            for inst in m.instantiations:
                if inst.module_name in instantiated_counts:
                    instantiated_counts[inst.module_name] += 1

        # The root/top module is never instantiated by any other module
        top_candidates = [m.name for m in modules if instantiated_counts[m.name] == 0]
        top_name = top_candidates[0] if top_candidates else modules[0].name

        for m in modules:
            m.is_top = (m.name == top_name)

        def build_node(mod_name: str, inst_name: str = "", visited: Optional[Set[str]] = None) -> HierarchyNode:
            if visited is None:
                visited = set()
            m = mod_map.get(mod_name)
            node = HierarchyNode(
                module_name=mod_name,
                instance_name=inst_name,
                file=m.filename if m else "",
                is_top=(mod_name == top_name),
                children=[]
            )
            if m and mod_name not in visited:
                new_visited = visited | {mod_name}
                for inst in m.instantiations:
                    child_node = build_node(inst.module_name, inst.instance_name, new_visited)
                    node.children.append(child_node)
            return node

        hierarchy = build_node(top_name)
        return top_name, hierarchy

    def _parse_module(self):
        start_tok = self.stream.consume("module")
        start_line = start_tok.line

        # Module name
        mod_name_tok = self.stream.current()
        mod_name = mod_name_tok.value
        self.stream.advance()

        self.current_module = ModuleModel(
            name=mod_name,
            filename=self.filename,
            start_line=start_line,
            end_line=start_line,
            ports=[],
            signals=[],
            parameters=[],
            always_blocks=[],
            continuous_assigns=[],
            branches=[],
            conditions=[],
            case_statements=[],
            fsm=None,
            executable_lines=[]
        )

        # Parse optional parameter list #( ... )
        if self.stream.current().value == "#":
            self.stream.advance()
            if self.stream.current().value == "(":
                self._parse_parameter_port_list()

        # Parse ports (ANSI or non-ANSI)
        if self.stream.current().value == "(":
            self._parse_port_list()

        if self.stream.current().value == ";":
            self.stream.advance()

        # Parse module body until endmodule
        while self.stream.has_next() and self.stream.current().value != "endmodule":
            tok = self.stream.current()

            if tok.value in ("input", "output", "inout"):
                self._parse_non_ansi_port_decl()
            elif tok.value in ("reg", "wire", "logic", "integer", "bit", "int", "byte", "shortint", "longint"):
                self._parse_signal_decl()
            elif tok.value in ("parameter", "localparam"):
                self._parse_parameter_decl()
            elif tok.value in ("always", "always_ff", "always_comb", "always_latch"):
                self._parse_always_block()
            elif tok.value == "assign":
                self._parse_assign()
            elif tok.value == "initial":
                self._skip_initial_block()
            elif tok.value in ("typedef", "enum", "struct", "union"):
                self._parse_typedef_or_enum()
            elif tok.type == "IDENTIFIER" and self.stream.peek(1) and (
                self.stream.peek(1).type == "IDENTIFIER" or self.stream.peek(1).value == "#"
            ):
                self._parse_module_instantiation()
            else:
                self.stream.advance()

        end_line = self.stream.current().line
        if self.stream.current().value == "endmodule":
            self.stream.advance()
        else:
            self.current_module.partial_analysis = True
            if not self.current_module.partial_reason:
                self.current_module.partial_reason = f"Syntax error: missing 'endmodule' before EOF."

        self.current_module.end_line = end_line
        
        # Deduplicate and refine signals vs ports
        port_names = {p.name for p in self.current_module.ports}
        self.current_module.signals = [s for s in self.current_module.signals if s.name not in port_names]

        # Analyze FSM candidates within this module
        self._detect_fsm(self.current_module)

        # Collect unique executable lines
        self.current_module.executable_lines = sorted(list(set(self.current_module.executable_lines)))

        self.modules.append(self.current_module)
        self.current_module = None

    def _parse_parameter_port_list(self):
        self.stream.advance()  # consume '('
        depth = 1
        curr_tokens: List[Token] = []

        while self.stream.has_next() and depth > 0:
            tok = self.stream.current()
            if tok.value == "(":
                depth += 1
            elif tok.value == ")":
                depth -= 1
                if depth == 0:
                    self.stream.advance()
                    break
            if depth > 0:
                curr_tokens.append(tok)
            self.stream.advance()

        # Extract parameters from parameter port tokens
        s = " ".join(t.value for t in curr_tokens)
        for part in s.split(","):
            part = part.strip()
            if "parameter" in part:
                part = part.replace("parameter", "").strip()
            if "=" in part:
                name, val = part.split("=", 1)
                self.current_module.parameters.append(Parameter(name=name.strip(), default_value=val.strip(), line=curr_tokens[0].line if curr_tokens else 1))

    def _parse_port_list(self):
        """Parses ports enclosed in ( ... ); handles both ANSI declarations and simple identifier lists."""
        self.stream.advance()  # consume '('
        depth = 1
        port_tokens: List[Token] = []

        while self.stream.has_next() and depth > 0:
            tok = self.stream.current()
            if tok.value == "(":
                depth += 1
            elif tok.value == ")":
                depth -= 1
                if depth == 0:
                    self.stream.advance()
                    break
            if depth > 0:
                port_tokens.append(tok)
            self.stream.advance()

        if depth > 0 and self.current_module:
            self.current_module.partial_analysis = True
            self.current_module.partial_reason = "Syntax error: unclosed port list parenthesis '(' before EOF."

        # Split port_tokens by comma ','
        entries: List[List[Token]] = []
        cur: List[Token] = []
        for t in port_tokens:
            if t.value == ",":
                if cur:
                    entries.append(cur)
                    cur = []
            else:
                cur.append(t)
        if cur:
            entries.append(cur)

        last_direction = "input"
        last_type = "wire"
        last_width = "[0:0]"

        for entry in entries:
            if not entry:
                continue
            words = [t.value for t in entry]
            line = entry[0].line
            
            # Check for direction in entry
            dir_found = None
            for d in ("input", "output", "inout"):
                if d in words:
                    dir_found = d
                    last_width = "[0:0]"
                    break
            if dir_found:
                last_direction = dir_found
            direction = last_direction

            # Check for data type
            dtype = "wire"
            for dt in ("reg", "logic", "wire", "integer"):
                if dt in words:
                    dtype = dt
                    break
            last_type = dtype

            # Check for width: [ ... : ... ]
            width = last_width
            w_str = ""
            in_w = False
            for t in entry:
                if t.value == "[":
                    in_w = True
                    w_str = "["
                elif t.value == "]":
                    w_str += "]"
                    in_w = False
                    width = w_str
                    last_width = w_str
                    break
                elif in_w:
                    w_str += t.value

            # Identifier is the last token that is an IDENTIFIER
            port_name = None
            for t in reversed(entry):
                if t.type == "IDENTIFIER" and t.value not in ("input", "output", "inout", "reg", "wire", "logic"):
                    port_name = t.value
                    line = t.line
                    break

            if port_name:
                self.current_module.ports.append(
                    Port(name=port_name, direction=direction, width=width, data_type=dtype, line=line)
                )

    def _parse_non_ansi_port_decl(self):
        """Parses standalone declarations like: input [7:0] a, b;"""
        dir_tok = self.stream.advance()
        direction = dir_tok.value
        line = dir_tok.line

        # Optional data type
        dtype = "wire"
        if self.stream.current().value in ("reg", "wire", "logic", "integer"):
            dtype = self.stream.advance().value

        # Optional width
        width = "[0:0]"
        if self.stream.current().value == "[":
            width_tokens = []
            while self.stream.has_next() and self.stream.current().value != "]":
                width_tokens.append(self.stream.advance().value)
            if self.stream.current().value == "]":
                width_tokens.append(self.stream.advance().value)
            width = "".join(width_tokens)

        # Port identifiers until ';'
        while self.stream.has_next() and self.stream.current().value != ";":
            tok = self.stream.current()
            if tok.type == "IDENTIFIER":
                # Check if port already exists in ports list (from non-ANSI port list), update it
                found = False
                for p in self.current_module.ports:
                    if p.name == tok.value:
                        p.direction = direction
                        p.data_type = dtype
                        p.width = width
                        p.line = tok.line
                        found = True
                        break
                if not found:
                    self.current_module.ports.append(
                        Port(name=tok.value, direction=direction, width=width, data_type=dtype, line=tok.line)
                    )
            self.stream.advance()
        if self.stream.current().value == ";":
            self.stream.advance()

    def _parse_signal_decl(self):
        type_tok = self.stream.advance()
        dtype = type_tok.value

        # Optional width
        width = "[0:0]"
        if self.stream.current().value == "[":
            width_tokens = []
            while self.stream.has_next() and self.stream.current().value != "]":
                width_tokens.append(self.stream.advance().value)
            if self.stream.current().value == "]":
                width_tokens.append(self.stream.advance().value)
            width = "".join(width_tokens)

        while self.stream.has_next() and self.stream.current().value != ";":
            tok = self.stream.current()
            if tok.type == "IDENTIFIER":
                # Check if it's already an output port declared with reg
                for p in self.current_module.ports:
                    if p.name == tok.value and p.direction == "output":
                        p.data_type = dtype
                        if width != "[0:0]":
                            p.width = width
                        break
                else:
                    self.current_module.signals.append(
                        Signal(name=tok.value, data_type=dtype, width=width, line=tok.line)
                    )
            self.stream.advance()
        if self.stream.current().value == ";":
            self.stream.advance()

    def _parse_parameter_decl(self):
        self.stream.advance()  # consume 'parameter' or 'localparam'
        while self.stream.has_next() and self.stream.current().value != ";":
            tok = self.stream.current()
            if tok.type == "IDENTIFIER":
                name = tok.value
                line = tok.line
                self.stream.advance()
                val = ""
                if self.stream.current().value == "=":
                    self.stream.advance()
                    val_parts = []
                    while self.stream.has_next() and self.stream.current().value not in (",", ";"):
                        val_parts.append(self.stream.advance().value)
                    val = " ".join(val_parts)
                self.current_module.parameters.append(Parameter(name=name, default_value=val, line=line))
            else:
                self.stream.advance()
        if self.stream.current().value == ";":
            self.stream.advance()

    def _parse_assign(self):
        assign_tok = self.stream.advance()
        line = assign_tok.line
        self.current_module.executable_lines.append(line)

        target_parts = []
        while self.stream.has_next() and self.stream.current().value != "=":
            target_parts.append(self.stream.advance().value)
        target = " ".join(target_parts).strip()

        if self.stream.current().value == "=":
            self.stream.advance()

        expr_parts = []
        while self.stream.has_next() and self.stream.current().value != ";":
            expr_parts.append(self.stream.advance().value)
        expr = " ".join(expr_parts).strip()

        if self.stream.current().value == ";":
            self.stream.advance()

        self.current_module.continuous_assigns.append(
            ContinuousAssign(target=target, expr=expr, line=line)
        )

    def _parse_typedef_or_enum(self):
        while self.stream.has_next() and self.stream.current().value != ";":
            self.stream.advance()
        if self.stream.current().value == ";":
            self.stream.advance()

    def _parse_module_instantiation(self):
        mod_type_tok = self.stream.advance()
        mod_type = mod_type_tok.value
        line = mod_type_tok.line

        # Optional parameter override: #( ... )
        if self.stream.current().value == "#":
            self.stream.advance()
            if self.stream.current().value == "(":
                self.stream.advance()
                depth = 1
                while self.stream.has_next() and depth > 0:
                    t = self.stream.advance()
                    if t.value == "(":
                        depth += 1
                    elif t.value == ")":
                        depth -= 1

        # Instance name
        inst_name = ""
        if self.stream.current().type == "IDENTIFIER":
            inst_name = self.stream.advance().value

        # Port connections: ( ... )
        conns: List[TBPortConnection] = []
        if self.stream.current().value == "(":
            self.stream.advance()
            depth = 1
            conn_tokens = []
            while self.stream.has_next() and depth > 0:
                t = self.stream.advance()
                if t.value == "(":
                    depth += 1
                elif t.value == ")":
                    depth -= 1
                    if depth == 0:
                        break
                if depth > 0:
                    conn_tokens.append(t)

            i = 0
            n = len(conn_tokens)
            while i < n:
                if conn_tokens[i].value == "." and i + 1 < n:
                    pname = conn_tokens[i + 1].value
                    i += 2
                    if i < n and conn_tokens[i].value == "(":
                        i += 1
                        expr_parts = []
                        cdepth = 1
                        while i < n and cdepth > 0:
                            if conn_tokens[i].value == "(":
                                cdepth += 1
                            elif conn_tokens[i].value == ")":
                                cdepth -= 1
                                if cdepth == 0:
                                    break
                            if cdepth > 0:
                                expr_parts.append(conn_tokens[i].value)
                            i += 1
                        conns.append(TBPortConnection(port_name=pname, tb_expr=" ".join(expr_parts).strip(), line=line))
                i += 1

        if self.stream.current().value == ";":
            self.stream.advance()

        if inst_name and self.current_module:
            self.current_module.instantiations.append(
                ModuleInstantiation(
                    module_name=mod_type,
                    instance_name=inst_name,
                    connections=conns,
                    line=line,
                    file=self.filename
                )
            )

    def _parse_always_block(self):
        always_tok = self.stream.advance()
        block_type = always_tok.value
        start_line = always_tok.line

        # Parse sensitivity list: @( ... ) or @*
        sensitivity = "*"
        is_clocked = False
        clk_sig = None
        rst_sig = None

        if self.stream.current().value == "@":
            self.stream.advance()
            if self.stream.current().value == "*":
                self.stream.advance()
                sensitivity = "*"
            elif self.stream.current().value == "(":
                self.stream.advance()
                depth = 1
                sens_tokens = []
                while self.stream.has_next() and depth > 0:
                    tok = self.stream.current()
                    if tok.value == "(":
                        depth += 1
                    elif tok.value == ")":
                        depth -= 1
                        if depth == 0:
                            self.stream.advance()
                            break
                    if depth > 0:
                        sens_tokens.append(tok)
                    self.stream.advance()

                sens_text = " ".join(t.value for t in sens_tokens)
                sensitivity = sens_text
                # Check for clock and reset in sensitivity list
                for i, t in enumerate(sens_tokens):
                    if t.value in ("posedge", "negedge"):
                        is_clocked = True
                        if i + 1 < len(sens_tokens):
                            sig_name = sens_tokens[i + 1].value
                            sig_lower = sig_name.lower()
                            if any(k in sig_lower for k in ("clk", "clock")):
                                clk_sig = sig_name
                            elif any(k in sig_lower for k in ("rst", "reset")):
                                rst_sig = sig_name
                            elif not clk_sig:
                                clk_sig = sig_name

        if block_type == "always_ff":
            is_clocked = True

        # Now parse the procedural statement / block inside always
        end_line = self._parse_statement()

        self.current_module.always_blocks.append(
            AlwaysBlock(
                block_type=block_type,
                sensitivity=sensitivity,
                start_line=start_line,
                end_line=end_line,
                is_clocked=is_clocked,
                clock_signal=clk_sig,
                reset_signal=rst_sig
            )
        )

    def _parse_statement(self) -> int:
        """Parses a procedural statement (begin...end, if...else, case...endcase, or simple assignment)."""
        if not self.stream.has_next():
            return 1

        tok = self.stream.current()
        line = tok.line

        # Begin ... end block
        if tok.value == "begin":
            self.stream.advance()
            last_line = line
            while self.stream.has_next() and self.stream.current().value != "end":
                last_line = self._parse_statement()
            if self.stream.current().value == "end":
                last_line = self.stream.current().line
                self.stream.advance()
            return last_line

        # If ... else statement
        elif tok.value == "if":
            return self._parse_if_statement()

        # Case ... endcase statement
        elif tok.value in ("case", "casex", "casez"):
            return self._parse_case_statement()

        # Simple assignment or other procedural line
        else:
            self.current_module.executable_lines.append(line)
            # Advance until semicolon ';' or block boundary
            while self.stream.has_next() and self.stream.current().value not in (";", "end", "endcase", "else"):
                tok = self.stream.advance()
                line = tok.line
            if self.stream.current().value == ";":
                line = self.stream.advance().line
            return line

    def _parse_if_statement(self) -> int:
        if_tok = self.stream.advance()  # 'if'
        line = if_tok.line
        self.current_module.executable_lines.append(line)

        # Parse condition ( ... )
        cond_expr = ""
        if self.stream.current().value == "(":
            self.stream.advance()
            depth = 1
            cond_tokens = []
            while self.stream.has_next() and depth > 0:
                t = self.stream.current()
                if t.value == "(":
                    depth += 1
                elif t.value == ")":
                    depth -= 1
                    if depth == 0:
                        self.stream.advance()
                        break
                if depth > 0:
                    cond_tokens.append(t)
                self.stream.advance()
            cond_expr = " ".join(t.value for t in cond_tokens)

        # Analyze condition into terms
        self.condition_counter += 1
        condition_obj = self._analyze_condition_expr(f"COND#{self.condition_counter:02d}", line, cond_expr)
        self.current_module.conditions.append(condition_obj)

        # Register TRUE branch
        self.branch_counter += 1
        true_branch_id = f"BR#{self.branch_counter:02d}"
        start_true = self.stream.current().line
        end_true = self._parse_statement()

        self.current_module.branches.append(
            Branch(
                id=true_branch_id,
                branch_type="if_then",
                condition_expr=f"({cond_expr}) == TRUE",
                line=line,
                start_line=start_true,
                end_line=end_true,
                status="POTENTIALLY_UNTESTED"
            )
        )

        last_line = end_true

        # Check for else / else if
        if self.stream.current().value == "else":
            else_tok = self.stream.advance()  # consume 'else'
            else_line = else_tok.line
            self.current_module.executable_lines.append(else_line)

            if self.stream.current().value == "if":
                # else if
                last_line = self._parse_if_statement()
            else:
                # else branch
                self.branch_counter += 1
                false_branch_id = f"BR#{self.branch_counter:02d}"
                start_false = self.stream.current().line
                end_false = self._parse_statement()
                self.current_module.branches.append(
                    Branch(
                        id=false_branch_id,
                        branch_type="if_else",
                        condition_expr=f"({cond_expr}) == FALSE",
                        line=else_line,
                        start_line=start_false,
                        end_line=end_false,
                        status="POTENTIALLY_UNTESTED"
                    )
                )
                last_line = end_false

        return last_line

    def _parse_case_statement(self) -> int:
        case_tok = self.stream.advance()
        case_type = case_tok.value
        line = case_tok.line
        self.current_module.executable_lines.append(line)

        # Parse case expression ( ... )
        expr = ""
        if self.stream.current().value == "(":
            self.stream.advance()
            depth = 1
            expr_tokens = []
            while self.stream.has_next() and depth > 0:
                t = self.stream.current()
                if t.value == "(":
                    depth += 1
                elif t.value == ")":
                    depth -= 1
                    if depth == 0:
                        self.stream.advance()
                        break
                if depth > 0:
                    expr_tokens.append(t)
                self.stream.advance()
            expr = " ".join(t.value for t in expr_tokens)

        items: List[CaseItem] = []
        has_default = False
        default_line = None

        # Parse case items until endcase
        while self.stream.has_next() and self.stream.current().value != "endcase":
            tok = self.stream.current()
            item_line = tok.line

            if tok.value == "default":
                has_default = True
                default_line = item_line
                self.stream.advance()
                if self.stream.current().value == ":":
                    self.stream.advance()
                stmt_start = self.stream.current().line
                stmt_end = self._parse_statement()
                items.append(
                    CaseItem(
                        label="default",
                        values=["default"],
                        start_line=stmt_start,
                        end_line=stmt_end,
                        is_default=True
                    )
                )
                self.branch_counter += 1
                self.current_module.branches.append(
                    Branch(
                        id=f"BR#{self.branch_counter:02d}",
                        branch_type="case_default",
                        condition_expr=f"{expr} == default",
                        line=item_line,
                        start_line=stmt_start,
                        end_line=stmt_end,
                        status="POTENTIALLY_UNTESTED"
                    )
                )
            else:
                # Value(s) : statement
                val_tokens = []
                while self.stream.has_next() and self.stream.current().value != ":" and self.stream.current().value != "endcase":
                    val_tokens.append(self.stream.advance().value)
                if self.stream.current().value == ":":
                    self.stream.advance()

                val_str = " ".join(val_tokens)
                vals = [v.strip() for v in val_str.split(",") if v.strip()]
                stmt_start = self.stream.current().line
                stmt_end = self._parse_statement()

                items.append(
                    CaseItem(
                        label=val_str,
                        values=vals,
                        start_line=stmt_start,
                        end_line=stmt_end,
                        is_default=False
                    )
                )
                self.branch_counter += 1
                self.current_module.branches.append(
                    Branch(
                        id=f"BR#{self.branch_counter:02d}",
                        branch_type="case_item",
                        condition_expr=f"{expr} in [{val_str}]",
                        line=item_line,
                        start_line=stmt_start,
                        end_line=stmt_end,
                        status="POTENTIALLY_UNTESTED"
                    )
                )

        endcase_line = line
        if self.stream.current().value == "endcase":
            endcase_line = self.stream.advance().line

        self.case_counter += 1
        case_id = f"CASE#{self.case_counter:02d}"
        case_stmt = CaseStatement(
            id=case_id,
            line=line,
            expr=expr,
            case_type=case_type,
            items=items,
            has_default=has_default,
            default_line=default_line,
            total_branches=len(items),
            stimulated_branches=0
        )
        self.current_module.case_statements.append(case_stmt)
        return endcase_line

    def _skip_initial_block(self):
        self.stream.advance()  # 'initial'
        self._parse_statement()

    def _analyze_condition_expr(self, cond_id: str, line: int, expr: str) -> Condition:
        terms: List[ConditionTerm] = []
        # Split on logical operators && and ||
        # Regex to split on && or || while keeping pieces
        sub_exprs = re.split(r'\s*(&&|\|\|)\s*', expr)

        for sub in sub_exprs:
            sub = sub.strip()
            if not sub or sub in ("&&", "||"):
                continue

            # Strip leading/trailing parens
            clean_sub = sub
            while clean_sub.startswith("(") and clean_sub.endswith(")"):
                clean_sub = clean_sub[1:-1].strip()

            # Check for comparison: ==, !=, <=, >=, <, >
            comp_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*(\[[^\]]+\])?)\s*(==|!=|<=|>=|<|>)\s*(.*)', clean_sub)
            if comp_match:
                var = comp_match.group(1).strip()
                op = comp_match.group(3).strip()
                target_val = comp_match.group(4).strip()
                terms.append(
                    ConditionTerm(
                        variable=var,
                        comparison_op=op,
                        target_value=target_val,
                        details=f"Evaluates {var} {op} {target_val}"
                    )
                )
            elif clean_sub.startswith("!"):
                var = clean_sub[1:].strip()
                terms.append(
                    ConditionTerm(
                        variable=var,
                        comparison_op="==",
                        target_value="0",
                        details=f"Evaluates !{var} (active-low or 0)"
                    )
                )
            else:
                var = clean_sub.strip()
                terms.append(
                    ConditionTerm(
                        variable=var,
                        comparison_op="!=",
                        target_value="0",
                        details=f"Evaluates {var} as boolean TRUE"
                    )
                )

        return Condition(
            id=cond_id,
            line=line,
            raw_expression=expr,
            terms=terms,
            missing_scenarios=[]
        )

    def _detect_fsm(self, mod: ModuleModel):
        """Identifies genuine FSM-like structures. Avoids classifying ALU opcodes or muxes as FSMs."""
        clocked_blocks = [b for b in mod.always_blocks if b.is_clocked]
        if not clocked_blocks or not mod.case_statements:
            mod.fsm = None
            return

        input_names = {p.name for p in mod.ports if p.direction == "input"}

        for case_stmt in mod.case_statements:
            expr_name = case_stmt.expr.strip()

            # An input port (like opcode, select) is NOT an internal FSM state register
            if expr_name in input_names:
                continue

            # Must be a reg or logic signal
            is_reg = any(s.name == expr_name and s.data_type in ("reg", "logic") for s in mod.signals) or \
                     any(p.name == expr_name and p.direction == "output" for p in mod.ports)
            
            if not is_reg:
                continue

            expr_lower = expr_name.lower()
            is_state_name = any(k in expr_lower for k in ("state", "fsm", "curr", "present", "st_reg", "phase"))

            # Look for states defined in parameters or case items
            detected_states = []
            for item in case_stmt.items:
                if not item.is_default:
                    detected_states.extend(item.values)

            # Must have at least 2 distinct states
            if len(detected_states) < 2:
                continue

            # Check if any parameter matches detected state names
            param_names = {p.name for p in mod.parameters}
            has_param_states = any(s in param_names for s in detected_states)

            # If it has state-like naming or state parameters, classify as FSM
            if is_state_name or has_param_states:
                confidence = "High" if (is_state_name and has_param_states) else "Medium"
                transitions: List[FsmTransition] = []

                # Find transitions inside each case item
                for item in case_stmt.items:
                    if item.is_default:
                        continue
                    src = item.values[0] if item.values else item.label
                    
                    # Look for if branches within this item's lines
                    item_branches = [b for b in mod.branches if b.branch_type in ("if_then", "if_else") and item.start_line <= b.line <= item.end_line]
                    if item_branches:
                        for br in item_branches:
                            # Try to match destination state from tokens in branch line range
                            dst = None
                            for t in self.stream.tokens:
                                if br.start_line <= t.line <= br.end_line and t.value in detected_states and t.value != src:
                                    dst = t.value
                                    break
                            if not dst:
                                for st in detected_states:
                                    if st != src:
                                        dst = st
                                        break
                            clean_cond = br.condition_expr.replace("== TRUE", "").replace("== FALSE", "").strip(" ()")
                            transitions.append(
                                FsmTransition(
                                    from_state=src,
                                    to_state=dst or src,
                                    condition_expr=clean_cond,
                                    trigger_condition=clean_cond,
                                    status="NO_EVIDENCE",
                                    line=br.line
                                )
                            )
                    else:
                        # Direct transition - look for assigned state in item lines
                        dst = None
                        for t in self.stream.tokens:
                            if item.start_line <= t.line <= item.end_line and t.value in detected_states and t.value != src:
                                dst = t.value
                                break
                        if not dst:
                            dst = detected_states[(detected_states.index(src) + 1) % len(detected_states)] if src in detected_states else src
                        transitions.append(
                            FsmTransition(
                                from_state=src,
                                to_state=dst,
                                condition_expr="Unconditional advance",
                                trigger_condition="Unconditional",
                                status="NO_EVIDENCE",
                                line=item.start_line
                            )
                        )

                mod.fsm = FsmModel(
                    state_reg=expr_name,
                    detected_states=detected_states,
                    transitions=transitions,
                    confidence=confidence,
                    stimulus_evidence=f"Clocked state register '{expr_name}' with {len(detected_states)} states"
                )
                return

        mod.fsm = None

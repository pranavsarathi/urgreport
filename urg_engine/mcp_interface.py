"""
Structured Model Context Protocol (MCP) and Tool Interface for URG Engine.
Exposes 13 clean, deterministic tools for AI assistants, IDE sidecars, and automated verification workflows.
"""

from typing import Dict, Any, Optional, List, Union
from .ast_nodes import CoverageReport, Finding, BeforeAfterComparison, ModuleModel
from .verilog_parser import VerilogParser
from .testbench_analyzer import TestbenchAnalyzer
from .coverage_analyzer import CoverageAnalyzer
from .diff_analyzer import DiffAnalyzer


class URGToolInterface:
    """Provides structured tool functions conforming to MCP tool conventions."""

    @staticmethod
    def get_tool_catalog() -> List[Dict[str, Any]]:
        """Returns metadata for all 13 standard MCP verification tools."""
        return [
            {
                "name": "analyze_design",
                "description": "Runs complete pre-simulation static coverage analysis on arbitrary single- or multi-file Verilog/SystemVerilog RTL and testbench.",
                "parameters": {
                    "rtl_content": "optional string (single-file RTL content)",
                    "tb_content": "string (Verilog testbench content)",
                    "files": "optional array of {filename: string, content: string} for multi-file designs",
                    "rtl_filename": "optional string (default: 'rtl.v')",
                    "tb_filename": "optional string (default: 'testbench.v')"
                }
            },
            {
                "name": "get_design_summary",
                "description": "Returns high-level design metrics: top module, hierarchy tree, port counts, coverage scores, and gap statistics.",
                "parameters": {}
            },
            {
                "name": "get_modules",
                "description": "Lists all parsed RTL modules in the design with port lists, signal counts, branch statistics, and FSM flags.",
                "parameters": {}
            },
            {
                "name": "get_module",
                "description": "Returns detailed structural AST and coverage data for a specific module name.",
                "parameters": {"module_name": "string"}
            },
            {
                "name": "get_finding",
                "description": "Retrieves structured WHY evidence (Formal Evidence Model), dataflow trace, confidence, and suggested Verilog stimulus snippet for a finding ID.",
                "parameters": {"finding_id": "string"}
            },
            {
                "name": "get_findings",
                "description": "Retrieves all findings with optional filtering by category (LINE, BRANCH, CONDITION, FSM_TRANSITION, TOGGLE, OUTPUT_CHECK, RESET), severity (HIGH, MEDIUM, LOW), or module.",
                "parameters": {
                    "category": "optional string",
                    "severity": "optional string",
                    "module": "optional string"
                }
            },
            {
                "name": "get_source_context",
                "description": "Returns lines of source code around a target line with line numbers and focus highlighting.",
                "parameters": {
                    "file_type": "string ('rtl' or 'tb')",
                    "line": "integer",
                    "window": "optional integer (default: 5)"
                }
            },
            {
                "name": "get_fsm",
                "description": "Returns FSM states, transition reachability matrix, trigger conditions, and SVG graph nodes/edges for state machine visualization.",
                "parameters": {"module_name": "optional string"}
            },
            {
                "name": "get_dataflow",
                "description": "Traces upstream drivers and downstream consumers for an arbitrary signal or condition expression.",
                "parameters": {"signal_name": "string"}
            },
            {
                "name": "get_signal_evidence",
                "description": "Retrieves toggle counts, TB driven values, reset polarity behavior, and output check verification status for a specific signal.",
                "parameters": {"signal_name": "string"}
            },
            {
                "name": "get_verification_gaps",
                "description": "Returns prioritized list of verification gaps filtered by severity or category, with linked findings.",
                "parameters": {
                    "severity_filter": "optional string ('HIGH', 'MEDIUM', 'LOW')",
                    "category_filter": "optional string"
                }
            },
            {
                "name": "suggest_test",
                "description": "Generates copyable Verilog stimulus snippet and expected check to close a verification gap.",
                "parameters": {"finding_id": "string"}
            },
            {
                "name": "suggest_test_scenario",
                "description": "Generates copyable Verilog stimulus snippet and expected check to close a verification gap.",
                "parameters": {"finding_id": "string"}
            },
            {
                "name": "compare_analysis",
                "description": "Compares current analysis run against previous run, returning score deltas, newly resolved gaps, and regression warnings.",
                "parameters": {}
            },
            {
                "name": "analyze_rtl",
                "description": "Statically inspects Verilog RTL, returning top module, port count, branches, and FSM detection.",
                "parameters": {"rtl_content": "string", "rtl_filename": "optional string"}
            },
            {
                "name": "analyze_testbench",
                "description": "Analyzes testbench stimulus, clock generation, reset polarity, and output checkers.",
                "parameters": {"tb_content": "string", "tb_filename": "optional string"}
            }
        ]

    @staticmethod
    def analyze_design(
        rtl_content: Optional[str] = None,
        tb_content: str = "",
        files: Optional[List[Dict[str, str]]] = None,
        rtl_filename: str = "rtl.v",
        tb_filename: str = "testbench.v"
    ) -> CoverageReport:
        """Runs full static coverage analysis on single or multi-file design."""
        if files and len(files) > 0:
            file_tuples = [(f["filename"], f["content"]) for f in files]
            design = VerilogParser.parse_files(file_tuples)
            raw_rtl = "\n\n".join(f"// File: {f['filename']}\n{f['content']}" for f in files)
        else:
            parser = VerilogParser(filename=rtl_filename)
            design = parser.parse(rtl_content or "")
            raw_rtl = rtl_content or ""

        tb_analyzer = TestbenchAnalyzer(filename=tb_filename)
        tb_model = tb_analyzer.analyze(tb_content, design=design)

        cov_analyzer = CoverageAnalyzer()
        return cov_analyzer.analyze(
            design=design,
            tb=tb_model,
            raw_rtl=raw_rtl,
            raw_tb=tb_content
        )

    @staticmethod
    def get_design_summary(report: CoverageReport) -> Dict[str, Any]:
        """Returns high-level design metrics and hierarchy."""
        return {
            "status": "success",
            "design_name": report.design_name,
            "top_module": report.top_module,
            "modules_count": len(report.modules),
            "files": report.design_files,
            "total_rtl_lines": report.total_rtl_lines,
            "total_tb_lines": report.total_tb_lines,
            "hierarchy": report.hierarchy.model_dump() if report.hierarchy else None,
            "overall_score": report.scores.overall_score,
            "category_scores": report.scores.model_dump(),
            "total_findings": len(report.findings),
            "total_gaps": len(report.gaps)
        }

    @staticmethod
    def get_modules(report: CoverageReport) -> List[Dict[str, Any]]:
        """Lists all modules in report."""
        return [
            {
                "name": m.name,
                "filename": m.filename,
                "is_top": m.is_top,
                "ports_count": len(m.ports),
                "ports": [p.model_dump() for p in m.ports],
                "signals_count": len(m.signals),
                "branches_count": len(m.branches),
                "conditions_count": len(m.conditions),
                "has_fsm": m.fsm is not None,
                "fsm_states": m.fsm.detected_states if m.fsm else []
            }
            for m in report.modules
        ]

    @staticmethod
    def get_module(report: CoverageReport, module_name: str) -> Optional[Dict[str, Any]]:
        """Returns details for a specific module."""
        m = next((mod for mod in report.modules if mod.name == module_name), None)
        if not m:
            return None
        return m.model_dump()

    @staticmethod
    def get_finding(report: CoverageReport, finding_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete structured evidence and reasoning for a finding ID."""
        for f in report.findings:
            if f.id == finding_id:
                return f.model_dump()
        return None

    @staticmethod
    def get_findings(
        report: CoverageReport,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filters findings by category, severity, or module."""
        results = []
        for f in report.findings:
            if category and f.category.upper() != category.upper():
                continue
            if severity and f.severity.upper() != severity.upper():
                continue
            if module and f.module != module:
                continue
            results.append(f.model_dump())
        return results

    @staticmethod
    def get_source_context(report: CoverageReport, file_type: str, line: int, window: int = 5) -> Dict[str, Any]:
        """Returns source code lines around a target line with line numbers."""
        raw_code = report.raw_rtl if file_type.lower() == "rtl" else report.raw_tb
        filename = report.rtl_filename if file_type.lower() == "rtl" else report.tb_filename
        lines = raw_code.split("\n")
        start = max(1, line - window)
        end = min(len(lines), line + window)

        context_lines = [
            {"line": i, "content": lines[i - 1], "is_target": (i == line)}
            for i in range(start, end + 1)
        ]
        return {
            "file": filename,
            "target_line": line,
            "window": window,
            "lines": context_lines
        }

    @staticmethod
    def get_fsm(report: CoverageReport, module_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns FSM state reachability, transitions, and visual graph representation."""
        mod = next((m for m in report.modules if (module_name is None or m.name == module_name) and m.fsm), None)
        if not mod or not mod.fsm:
            return None
        return mod.fsm.model_dump()

    # Alias for get_fsm
    analyze_fsm = get_fsm

    @staticmethod
    def get_dataflow(report: CoverageReport, signal_name: str) -> Dict[str, Any]:
        """Returns dataflow dependencies and fanout for a signal."""
        deps = report.dataflow_graph.get("dependencies", {})
        return {
            "signal": signal_name,
            "drives": [k for k, v in deps.items() if signal_name in v],
            "driven_by": deps.get(signal_name, [])
        }

    @staticmethod
    def get_signal_evidence(report: CoverageReport, signal_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves toggle counts, TB driven values, and check status for a signal."""
        for sig in report.signals:
            if sig.dut_port == signal_name or sig.tb_signal == signal_name:
                return sig.model_dump()
        return None

    @staticmethod
    def get_verification_gaps(
        report: CoverageReport,
        severity_filter: Optional[str] = None,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filters and returns verification gaps with their linked finding details."""
        results = []
        for g in report.gaps:
            if severity_filter and g.severity.upper() != severity_filter.upper():
                continue
            if category_filter and g.category.upper() != category_filter.upper():
                continue
            item = g.model_dump()
            if g.finding_id:
                finding = next((f for f in report.findings if f.id == g.finding_id), None)
                if finding:
                    item["finding"] = finding.model_dump()
            results.append(item)
        return results

    # Alias for get_verification_gaps
    find_verification_gaps = get_verification_gaps

    @staticmethod
    def suggest_test(report: CoverageReport, finding_id: str) -> Optional[Dict[str, Any]]:
        """Returns tailored verification guidance and copyable Verilog stimulus snippet."""
        finding = next((f for f in report.findings if f.id == finding_id), None)
        if not finding:
            return None
        return {
            "finding_id": finding.id,
            "title": finding.title,
            "suggested_scenario": finding.suggested_next_scenario,
            "suggested_next_scenario": finding.suggested_next_scenario,
            "stimulus_snippet": finding.suggested_stimulus_snippet,
            "suggested_stimulus_snippet": finding.suggested_stimulus_snippet,
            "target_location": f"{finding.rtl_file}:{finding.rtl_line}"
        }

    # Alias for suggest_test
    suggest_test_scenario = suggest_test

    @staticmethod
    def compare_analysis(previous: Optional[CoverageReport], current: CoverageReport) -> Dict[str, Any]:
        """Compares previous and current analysis runs, returning metric deltas and resolved gaps."""
        diff = DiffAnalyzer.compare(previous, current)
        return diff.model_dump()

    # Legacy compatibility methods
    @staticmethod
    def analyze_rtl(rtl_content: str, rtl_filename: str = "rtl.v") -> Dict[str, Any]:
        parser = VerilogParser(filename=rtl_filename)
        design = parser.parse(rtl_content)
        return {
            "status": "success",
            "top_module": design.top_module,
            "modules_count": len(design.modules),
            "modules": [
                {
                    "name": m.name,
                    "ports_count": len(m.ports),
                    "branches_count": len(m.branches),
                    "conditions_count": len(m.conditions),
                    "case_statements_count": len(m.case_statements),
                    "fsm_detected": m.fsm is not None
                }
                for m in design.modules
            ]
        }

    @staticmethod
    def analyze_testbench(tb_content: str, tb_filename: str = "testbench.v") -> Dict[str, Any]:
        tb_analyzer = TestbenchAnalyzer(filename=tb_filename)
        tb_model = tb_analyzer.analyze(tb_content)
        return {
            "status": "success",
            "dut_instances": [i.instance_name for i in tb_model.dut_instances],
            "clocks_detected": [c.signal_name for c in tb_model.clocks],
            "resets_detected": [r.signal_name for r in tb_model.resets],
            "stimulus_events_count": len(tb_model.stimulus),
            "active_nets": list(tb_model.toggles.keys()),
            "output_checks_count": len(tb_model.output_checks)
        }

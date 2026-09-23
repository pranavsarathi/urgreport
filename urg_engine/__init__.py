"""
URG Engine: Pre-Simulation RTL Coverage and Testbench Stimulus Analysis.
"""

from .ast_nodes import (
    DesignModel, ModuleModel, TestbenchModel, CoverageReport,
    CoverageScore, ModuleCoverage, CoverageGap, SignalMappingItem,
    Branch, Condition, CaseStatement, FsmModel, Finding,
    BeforeAfterComparison, TruthTableRow, FsmTransition, FsmGraphNode, FsmGraphEdge
)
from .tokenizer import Token, VerilogLexer, TokenStream
from .verilog_parser import VerilogParser, VerilogParserError
from .testbench_analyzer import TestbenchAnalyzer
from .coverage_analyzer import CoverageAnalyzer
from .dataflow_analyzer import DataflowAnalyzer
from .diff_analyzer import DiffAnalyzer
from .mcp_interface import URGToolInterface
from .exporter import ReportExporter

__all__ = [
    "DesignModel", "ModuleModel", "TestbenchModel", "CoverageReport",
    "CoverageScore", "ModuleCoverage", "CoverageGap", "SignalMappingItem",
    "Branch", "Condition", "CaseStatement", "FsmModel", "Finding",
    "BeforeAfterComparison", "TruthTableRow", "FsmTransition", "FsmGraphNode", "FsmGraphEdge",
    "Token", "VerilogLexer", "TokenStream",
    "VerilogParser", "VerilogParserError",
    "TestbenchAnalyzer", "CoverageAnalyzer", "DataflowAnalyzer",
    "DiffAnalyzer", "URGToolInterface", "ReportExporter"
]

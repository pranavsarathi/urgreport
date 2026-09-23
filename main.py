"""
URG Report for RTL Code - FastAPI Backend Application.
Serves REST API for Pre-Simulation RTL Coverage Analysis and SPA Frontend.
Includes Multi-File RTL Support, Hierarchy Navigation, and 13 MCP Tool Endpoints.
"""

import os
import re
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from urg_engine import (
    VerilogParser, TestbenchAnalyzer, CoverageAnalyzer,
    ReportExporter, CoverageReport, VerilogParserError,
    DiffAnalyzer, URGToolInterface
)

app = FastAPI(
    title="URG Report for RTL Code",
    description="General Pre-Simulation RTL Coverage Analysis Engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = BASE_DIR / "examples"
WEB_DIR = BASE_DIR / "web"

# In-memory store for session runs (session_id_design -> CoverageReport)
SESSION_REPORTS: Dict[str, CoverageReport] = {}


class FileInput(BaseModel):
    filename: str
    content: str


class AnalyzeRequest(BaseModel):
    rtl_content: Optional[str] = None
    tb_content: str = ""
    rtl_filename: str = "rtl.v"
    tb_filename: str = "testbench.v"
    files: Optional[List[FileInput]] = None
    session_id: Optional[str] = "default"


class McpExecuteRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}
    session_id: Optional[str] = "default"


EXAMPLES_CATALOG = [
    {
        "id": "low_power_earbud",
        "name": "Low-Power Earbud Controller (Initial TB)",
        "description": "Smart earbud power controller with sleep/wake detection and wake_irq interrupt. Testbench omits wake_irq checking and activity threshold testing.",
        "rtl_file": "low_power_earbud.v",
        "tb_file": "low_power_earbud_tb.v",
        "path": "low_power_earbud",
        "multi_file": False
    },
    {
        "id": "low_power_earbud_enhanced",
        "name": "Low-Power Earbud Controller (Enhanced TB - Fixed)",
        "description": "Enhanced testbench that asserts sound activity threshold, reaches WAKE state, and verifies wake_irq interrupt with assertions.",
        "rtl_file": "low_power_earbud.v",
        "tb_file": "low_power_earbud_tb_enhanced.v",
        "path": "low_power_earbud",
        "multi_file": False
    },
    {
        "id": "alu_8bit",
        "name": "8-bit ALU with Flags",
        "description": "8-bit Arithmetic Logic Unit with carry/zero/overflow flags. Testbench intentionally omits opcode 3'b111 (SHR) and never checks overflow.",
        "rtl_file": "alu_8bit.v",
        "tb_file": "alu_8bit_tb.v",
        "path": "alu_8bit",
        "multi_file": False
    },
    {
        "id": "counter_4bit",
        "name": "4-bit Up/Down Counter",
        "description": "4-bit synchronous counter with enable and active-low reset. Testbench tests count-up only; count-down and rollover checking are omitted.",
        "rtl_file": "counter_4bit.v",
        "tb_file": "counter_4bit_tb.v",
        "path": "counter_4bit",
        "multi_file": False
    },
    {
        "id": "fsm_traffic",
        "name": "Traffic Light FSM Controller",
        "description": "5-state Traffic Light Controller with emergency override. Testbench tests standard cycle but never asserts emergency override.",
        "rtl_file": "fsm_traffic.v",
        "tb_file": "fsm_traffic_tb.v",
        "path": "fsm_traffic",
        "multi_file": False
    },
    {
        "id": "fifo_sync",
        "name": "Synchronous FIFO Buffer",
        "description": "Depth-8 synchronous FIFO with full/empty flags and pointer management. Testbench tests partial writes/reads but leaves full flag and overflow untested.",
        "rtl_file": "fifo_sync.v",
        "tb_file": "fifo_sync_tb.v",
        "path": "fifo_sync",
        "multi_file": False
    },
    {
        "id": "uart_tx",
        "name": "UART Transmitter with Baud Generator",
        "description": "4-state UART transmitter (IDLE, START, DATA, STOP) with baud clock divider. Verifies serialized output transmission and done handshake.",
        "rtl_file": "uart_tx.v",
        "tb_file": "uart_tx_tb.v",
        "path": "uart_tx",
        "multi_file": False
    },
    {
        "id": "spi_master",
        "name": "SPI Master Controller",
        "description": "SPI Mode 0 Master controller with shift register and chip-select gating. Testbench drives transaction byte and observes bus completion.",
        "rtl_file": "spi_master.v",
        "tb_file": "spi_master_tb.v",
        "path": "spi_master",
        "multi_file": False
    },
    {
        "id": "riscv_decoder",
        "name": "RISC-V 32I Instruction Decoder",
        "description": "Pure combinational RISC-V 32I opcode decoder. Testbench tests R-type, I-type, and Load instructions, leaving Store and Branch paths untested.",
        "rtl_file": "riscv_decoder.v",
        "tb_file": "riscv_decoder_tb.v",
        "path": "riscv_decoder",
        "multi_file": False
    },
    {
        "id": "reg_file",
        "name": "32x32 Register File (Dual Read, Single Write)",
        "description": "32-entry 32-bit register file with x0 hardwired to zero. Testbench verifies register writes, asynchronous reads, and zero-register immutability.",
        "rtl_file": "reg_file.v",
        "tb_file": "reg_file_tb.v",
        "path": "reg_file",
        "multi_file": False
    },
    {
        "id": "pwm_controller",
        "name": "Pulse Width Modulation (PWM) Controller",
        "description": "PWM controller with configurable period and duty threshold registers. Testbench verifies active modulation pulses and cycle completion.",
        "rtl_file": "pwm_controller.v",
        "tb_file": "pwm_controller_tb.v",
        "path": "pwm_controller",
        "multi_file": False
    },
    {
        "id": "pipeline_datapath",
        "name": "Hierarchical 3-Stage Datapath (Multi-File RTL)",
        "description": "Multi-file pipelined datapath: top-level pipeline_top.v instantiating fetch.v, decode.v, and execute.v submodules.",
        "rtl_file": "pipeline_top.v",
        "rtl_files": ["fetch.v", "decode.v", "execute.v", "pipeline_top.v"],
        "tb_file": "pipeline_tb.v",
        "path": "pipeline_datapath",
        "multi_file": True
    }
]


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "tool": "URG REPORT FOR RTL CODE",
        "tagline": "Pre-Simulation RTL Coverage Analysis",
        "version": "2.0.0"
    }


@app.get("/api/examples")
def get_examples():
    return EXAMPLES_CATALOG


@app.get("/api/examples/{example_id}")
def get_example_code(example_id: str):
    ex = next((e for e in EXAMPLES_CATALOG if e["id"] == example_id), None)
    if not ex:
        raise HTTPException(status_code=404, detail="Example not found")

    folder = EXAMPLES_DIR / ex["path"]
    rtl_path = folder / ex["rtl_file"]
    tb_path = folder / ex["tb_file"]

    if not rtl_path.exists() or not tb_path.exists():
        raise HTTPException(status_code=404, detail="Example files missing on disk")

    result = {
        "id": ex["id"],
        "name": ex["name"],
        "description": ex["description"],
        "rtl_filename": ex["rtl_file"],
        "tb_filename": ex["tb_file"],
        "rtl_content": rtl_path.read_text(encoding="utf-8", errors="replace"),
        "tb_content": tb_path.read_text(encoding="utf-8", errors="replace"),
        "multi_file": ex.get("multi_file", False)
    }

    if ex.get("multi_file") and "rtl_files" in ex:
        files_data = []
        for fn in ex["rtl_files"]:
            p = folder / fn
            if p.exists():
                files_data.append({
                    "filename": fn,
                    "content": p.read_text(encoding="utf-8", errors="replace")
                })
        result["files"] = files_data

    return result


def perform_analysis(
    rtl_content: Optional[str] = None,
    tb_content: str = "",
    rtl_filename: str = "rtl.v",
    tb_filename: str = "testbench.v",
    files: Optional[List[Tuple[str, str]]] = None,
    session_id: str = "default"
) -> CoverageReport:
    try:
        if files and len(files) > 0:
            design = VerilogParser.parse_files(files)
            raw_rtl = "\n\n".join(f"// File: {fn}\n{cnt}" for fn, cnt in files)
            rtl_filename = design.top_module or files[0][0]
        else:
            parser = VerilogParser(filename=rtl_filename)
            design = parser.parse(rtl_content or "")
            raw_rtl = rtl_content or ""
            # Ensure fresh metadata: derive filename from parsed module if mismatched or default
            if design.top_module:
                known_mod_names = {m.name for m in design.modules}
                if not any(k in rtl_filename for k in known_mod_names) or rtl_filename in ("rtl.v", "design.v"):
                    rtl_filename = f"{design.top_module}.v"
                    design.filename = rtl_filename
                    design.files = [rtl_filename]

        # Ensure fresh testbench filename from tb module or top module
        tb_mod_match = re.search(r'\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)', tb_content)
        if tb_mod_match:
            tb_mod_name = tb_mod_match.group(1)
            if tb_filename in ("testbench.v", "tb.v") or (design.top_module and design.top_module not in tb_filename and tb_mod_name not in tb_filename):
                tb_filename = f"{tb_mod_name}.v"
        elif design.top_module and (tb_filename in ("testbench.v", "tb.v") or (design.top_module not in tb_filename and "tb" in tb_filename)):
            tb_filename = f"{design.top_module}_tb.v"

        tb_analyzer = TestbenchAnalyzer(filename=tb_filename)
        tb_model = tb_analyzer.analyze(tb_content, design=design)

        cov_analyzer = CoverageAnalyzer()
        report = cov_analyzer.analyze(
            design=design,
            tb=tb_model,
            raw_rtl=raw_rtl,
            raw_tb=tb_content
        )

        # Before / After Diff Correlation with previous session report
        session_key = f"{session_id}_{report.design_name}"
        prev_report = SESSION_REPORTS.get(session_key)
        if prev_report:
            report.before_after = DiffAnalyzer.compare(prev_report, report)
        else:
            report.before_after = DiffAnalyzer.compare(None, report)

        # Update in-memory session report
        SESSION_REPORTS[session_key] = report
        return report

    except VerilogParserError as pe:
        raise HTTPException(
            status_code=422,
            detail={
                "error_type": "PARSER_ERROR",
                "file": pe.file or rtl_filename,
                "line": pe.line,
                "message": pe.message,
                "possible_cause": "Syntax error, missing semicolon, unmatched begin/end or malformed declaration."
            }
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "ANALYSIS_ERROR",
                "message": str(e),
                "possible_cause": "Internal error during Verilog parsing or coverage correlation."
            }
        )


@app.post("/api/session/reset")
def reset_session(session_id: str = "default"):
    """Resets previous comparison baseline for the given session."""
    keys_to_del = [k for k in SESSION_REPORTS if k.startswith(f"{session_id}_")]
    for k in keys_to_del:
        del SESSION_REPORTS[k]
    return {"status": "success", "message": f"Baseline cleared for session '{session_id}'"}


@app.get("/api/finding/{finding_id}")
def get_finding_by_id(finding_id: str, session_id: str = "default"):
    """Retrieves full reasoning evidence, dataflow chain, and stimulus snippet for a finding ID."""
    for key, report in SESSION_REPORTS.items():
        if key.startswith(f"{session_id}_"):
            for f in report.findings:
                if f.id == finding_id:
                    return f.model_dump()
    for report in SESSION_REPORTS.values():
        for f in report.findings:
            if f.id == finding_id:
                return f.model_dump()
    raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found in active session.")


@app.get("/api/mcp/tools")
def get_mcp_tools():
    """Returns catalog of structured Model Context Protocol (MCP) tools for AI agents and EDA automation."""
    return {
        "status": "success",
        "tools": URGToolInterface.get_tool_catalog()
    }


@app.post("/api/mcp/execute")
async def execute_mcp_tool(req: McpExecuteRequest):
    """Executes an MCP tool against current session report or provided inputs."""
    tool = req.tool
    args = req.arguments
    session_id = req.session_id or "default"

    # Find active report for session
    active_report: Optional[CoverageReport] = None
    for k, rep in SESSION_REPORTS.items():
        if k.startswith(f"{session_id}_"):
            active_report = rep
            break
    if not active_report and SESSION_REPORTS:
        active_report = next(iter(SESSION_REPORTS.values()))

    # 1. analyze_design
    if tool == "analyze_design":
        rtl = args.get("rtl_content")
        tb = args.get("tb_content", "")
        files_arg = args.get("files")
        fn_rtl = args.get("rtl_filename", "rtl.v")
        fn_tb = args.get("tb_filename", "testbench.v")
        files_tuples = [(f["filename"], f["content"]) for f in files_arg] if files_arg else None
        rep = perform_analysis(rtl_content=rtl, tb_content=tb, rtl_filename=fn_rtl, tb_filename=fn_tb, files=files_tuples, session_id=session_id)
        return URGToolInterface.get_design_summary(rep)

    # 2. get_design_summary
    elif tool == "get_design_summary":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report. Run analyze_design first.")
        return URGToolInterface.get_design_summary(active_report)

    # 3. get_modules
    elif tool == "get_modules":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        return {"status": "success", "modules": URGToolInterface.get_modules(active_report)}

    # 4. get_module
    elif tool == "get_module":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        m = URGToolInterface.get_module(active_report, args.get("module_name", ""))
        if not m:
            raise HTTPException(status_code=404, detail="Module not found.")
        return m

    # 5. get_finding
    elif tool == "get_finding":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        finding = URGToolInterface.get_finding(active_report, args.get("finding_id", ""))
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found.")
        return finding

    # 6. get_findings
    elif tool == "get_findings":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        return {
            "status": "success",
            "findings": URGToolInterface.get_findings(
                active_report,
                category=args.get("category"),
                severity=args.get("severity"),
                module=args.get("module")
            )
        }

    # 7. get_source_context
    elif tool == "get_source_context":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        return URGToolInterface.get_source_context(
            active_report,
            args.get("file_type", "rtl"),
            args.get("line", 1),
            args.get("window", 5)
        )

    # 8. get_fsm / analyze_fsm
    elif tool in ("get_fsm", "analyze_fsm"):
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        fsm_data = URGToolInterface.get_fsm(active_report, args.get("module_name"))
        if not fsm_data:
            return {"status": "none", "message": "No FSM detected in target module."}
        return fsm_data

    # 9. get_dataflow
    elif tool == "get_dataflow":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        return URGToolInterface.get_dataflow(active_report, args.get("signal_name", ""))

    # 10. get_signal_evidence
    elif tool == "get_signal_evidence":
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        sig_ev = URGToolInterface.get_signal_evidence(active_report, args.get("signal_name", ""))
        if not sig_ev:
            raise HTTPException(status_code=404, detail=f"Signal '{args.get('signal_name')}' not found.")
        return sig_ev

    # 11. get_verification_gaps / find_verification_gaps
    elif tool in ("get_verification_gaps", "find_verification_gaps"):
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        return {
            "status": "success",
            "gaps": URGToolInterface.get_verification_gaps(
                active_report,
                severity_filter=args.get("severity_filter"),
                category_filter=args.get("category_filter")
            )
        }

    # 12. suggest_test / suggest_test_scenario
    elif tool in ("suggest_test", "suggest_test_scenario"):
        if not active_report:
            raise HTTPException(status_code=400, detail="No active analysis report.")
        sug = URGToolInterface.suggest_test(active_report, args.get("finding_id", ""))
        if not sug:
            raise HTTPException(status_code=404, detail="Finding not found.")
        return sug

    # 13. compare_analysis
    elif tool == "compare_analysis":
        if not active_report or not active_report.before_after:
            return {"status": "no_previous_comparison"}
        return active_report.before_after.model_dump()

    # Legacy compatibility
    elif tool == "analyze_rtl":
        rtl = args.get("rtl_content", "")
        fn = args.get("rtl_filename", "rtl.v")
        return URGToolInterface.analyze_rtl(rtl, fn)
    elif tool == "analyze_testbench":
        tb = args.get("tb_content", "")
        fn = args.get("tb_filename", "testbench.v")
        return URGToolInterface.analyze_testbench(tb, fn)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool '{tool}'")


@app.post("/api/analyze")
async def analyze_design_endpoint(request: Request):
    content_type = request.headers.get("content-type", "")
    rtl_content = None
    tb_content = ""
    rtl_filename = "rtl.v"
    tb_filename = "testbench.v"
    files: Optional[List[Tuple[str, str]]] = None
    session_id = request.headers.get("x-session-id", "default")

    if "application/json" in content_type:
        data = await request.json()
        rtl_content = data.get("rtl_content")
        tb_content = data.get("tb_content", "")
        rtl_filename = data.get("rtl_filename", "rtl.v")
        tb_filename = data.get("tb_filename", "testbench.v")
        session_id = data.get("session_id", session_id)
        if "files" in data and data["files"]:
            files = [(f["filename"], f["content"]) for f in data["files"]]
    else:
        form = await request.form()
        session_id = form.get("session_id", session_id)
        tb_file = form.get("tb_file")
        if tb_file and hasattr(tb_file, "read"):
            tb_bytes = await tb_file.read()
            tb_content = tb_bytes.decode("utf-8", errors="replace")
            tb_filename = getattr(tb_file, "filename", "testbench.v") or "testbench.v"

        # Check for multiple RTL files uploaded
        form_files = form.getlist("rtl_files")
        if form_files:
            files = []
            for rf in form_files:
                if hasattr(rf, "read"):
                    rf_bytes = await rf.read()
                    rf_fn = getattr(rf, "filename", "file.v") or "file.v"
                    files.append((rf_fn, rf_bytes.decode("utf-8", errors="replace")))
        else:
            rtl_file = form.get("rtl_file")
            if rtl_file and hasattr(rtl_file, "read"):
                rtl_bytes = await rtl_file.read()
                rtl_content = rtl_bytes.decode("utf-8", errors="replace")
                rtl_filename = getattr(rtl_file, "filename", "rtl.v") or "rtl.v"

    if not files and (not rtl_content or not rtl_content.strip()):
        raise HTTPException(status_code=400, detail="RTL content or files must be provided")
    if not tb_content.strip():
        raise HTTPException(status_code=400, detail="Testbench file content is empty")

    report = perform_analysis(
        rtl_content=rtl_content,
        tb_content=tb_content,
        rtl_filename=rtl_filename,
        tb_filename=tb_filename,
        files=files,
        session_id=session_id
    )
    return report


@app.post("/api/export/html")
async def export_html(payload: AnalyzeRequest):
    files_tuples = [(f.filename, f.content) for f in payload.files] if payload.files else None
    report = perform_analysis(
        rtl_content=payload.rtl_content,
        tb_content=payload.tb_content,
        rtl_filename=payload.rtl_filename,
        tb_filename=payload.tb_filename,
        files=files_tuples,
        session_id=payload.session_id or "default"
    )
    html_content = ReportExporter.to_standalone_html(report)
    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Disposition": f"attachment; filename=URG_Report_{report.design_name}.html"
        }
    )


@app.post("/api/export/json")
async def export_json(payload: AnalyzeRequest):
    files_tuples = [(f.filename, f.content) for f in payload.files] if payload.files else None
    report = perform_analysis(
        rtl_content=payload.rtl_content,
        tb_content=payload.tb_content,
        rtl_filename=payload.rtl_filename,
        tb_filename=payload.tb_filename,
        files=files_tuples,
        session_id=payload.session_id or "default"
    )
    return JSONResponse(
        content=report.model_dump(),
        headers={
            "Content-Disposition": f"attachment; filename=URG_Report_{report.design_name}.json"
        }
    )


# Serve Static Frontend Files
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(str(WEB_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("ENVIRONMENT", "production").lower() == "development"
    uvicorn.run("main:app", host=host, port=port, reload=reload)

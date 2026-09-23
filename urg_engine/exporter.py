"""
Export engine for URG Coverage Analysis reports.
Generates Standalone Interactive HTML, Formatted Print/PDF HTML, and JSON representations.
"""

import json
from .ast_nodes import CoverageReport


class ReportExporter:
    @staticmethod
    def to_json(report: CoverageReport) -> str:
        return report.model_dump_json(indent=2)

    @staticmethod
    def to_standalone_html(report: CoverageReport) -> str:
        rep_dict = report.model_dump()
        json_data = json.dumps(rep_dict)

        fsm_val = f"{report.total_summary.fsm_cov}%" if report.total_summary.fsm_cov is not None else "N/A"
        fsm_badge = "bg-slate-100 text-slate-600" if report.total_summary.fsm_cov is None else (
            "bg-emerald-100 text-emerald-800" if report.total_summary.fsm_cov >= 80 else "bg-amber-100 text-amber-800"
        )

        def badge(val):
            if val is None:
                return "bg-slate-100 text-slate-500 border border-slate-300"
            if val >= 80:
                return "bg-emerald-50 text-emerald-700 border border-emerald-300"
            elif val >= 50:
                return "bg-amber-50 text-amber-700 border border-amber-300"
            return "bg-rose-50 text-rose-700 border border-rose-300"

        fsm_val = f"{report.total_summary.fsm_cov}%" if report.total_summary.fsm_cov is not None else "N/A"
        fsm_badge = badge(report.total_summary.fsm_cov) if report.total_summary.fsm_cov is not None else "bg-slate-100 text-slate-500 border border-slate-300"
        cond_val = f"{report.total_summary.cond_cov}%" if report.total_summary.cond_cov is not None else "N/A"
        cond_badge = badge(report.total_summary.cond_cov)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>URG Report - {report.design_name} (Pre-Simulation Static Analysis)</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  @media print {{
    .no-print {{ display: none !important; }}
    body {{ background: white !important; font-size: 11pt; }}
    .page-break {{ page-break-before: always; }}
  }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  .eda-table th {{ background-color: #f1f5f9; color: #334155; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .eda-table td, .eda-table th {{ border: 1px solid #e2e8f0; padding: 6px 10px; }}
</style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased p-6">
<div class="max-w-7xl mx-auto space-y-6">

  <!-- Header Banner -->
  <div class="bg-white border border-slate-300 rounded shadow-sm p-5 flex flex-wrap justify-between items-center">
    <div>
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-bold tracking-tight text-slate-900">URG REPORT FOR RTL CODE</h1>
        <span class="px-2.5 py-0.5 text-xs font-semibold rounded bg-sky-100 text-sky-800 border border-sky-300 uppercase">
          Pre-Simulation Static Analysis
        </span>
      </div>
      <p class="text-xs text-slate-500 mt-1">Pre-Simulation RTL & Testbench Structural Coverage Analysis Engine v{report.version}</p>
      <div class="flex flex-wrap gap-6 text-xs text-slate-600 mt-3">
        <div><span class="font-semibold text-slate-700">Design:</span> <span class="font-mono bg-slate-100 px-1.5 py-0.5 rounded">{report.design_name}</span></div>
        <div><span class="font-semibold text-slate-700">RTL File:</span> <span class="font-mono">{report.rtl_filename}</span></div>
        <div><span class="font-semibold text-slate-700">Testbench:</span> <span class="font-mono">{report.tb_filename}</span></div>
        <div><span class="font-semibold text-slate-700">Generated:</span> {report.timestamp}</div>
      </div>
    </div>
    <div class="flex gap-2 no-print mt-3 sm:mt-0">
      <button onclick="window.print()" class="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-white rounded shadow-sm">
        Print / Save PDF
      </button>
    </div>
  </div>

  <!-- Total Coverage Summary (Synopsys URG Style) -->
  <div class="bg-white border border-slate-300 rounded shadow-sm overflow-hidden">
    <div class="bg-slate-100 px-4 py-2 border-b border-slate-300 flex justify-between items-center">
      <h2 class="text-xs font-bold text-slate-700 uppercase tracking-wider">TOTAL COVERAGE SUMMARY</h2>
      <span class="text-xs text-slate-500 italic">Static Estimation (Pre-Simulation)</span>
    </div>
    <table class="w-full text-center border-collapse eda-table text-sm">
      <thead>
        <tr>
          <th class="py-2.5 font-bold">SCORE</th>
          <th>LINE</th>
          <th>COND</th>
          <th>TOGGLE</th>
          <th>FSM</th>
          <th>BRANCH</th>
        </tr>
      </thead>
      <tbody>
        <tr class="font-mono text-base font-semibold">
          <td class="py-3 text-slate-900 bg-slate-50">{report.total_summary.score}%</td>
          <td><span class="px-2 py-0.5 rounded text-xs {badge(report.total_summary.line_cov)}">{report.total_summary.line_cov}%</span></td>
          <td><span class="px-2 py-0.5 rounded text-xs {cond_badge}">{cond_val}</span></td>
          <td><span class="px-2 py-0.5 rounded text-xs {badge(report.total_summary.toggle_cov)}">{report.total_summary.toggle_cov}%</span></td>
          <td><span class="px-2 py-0.5 rounded text-xs {fsm_badge}">{fsm_val}</span></td>
          <td><span class="px-2 py-0.5 rounded text-xs {badge(report.total_summary.branch_cov)}">{report.total_summary.branch_cov}%</span></td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Hierarchical Coverage Data -->
  <div class="bg-white border border-slate-300 rounded shadow-sm overflow-hidden">
    <div class="bg-slate-100 px-4 py-2 border-b border-slate-300">
      <h2 class="text-xs font-bold text-slate-700 uppercase tracking-wider">HIERARCHICAL COVERAGE DATA</h2>
    </div>
    <table class="w-full text-left border-collapse eda-table text-xs">
      <thead>
        <tr>
          <th>SCORE</th>
          <th>LINE</th>
          <th>COND</th>
          <th>TOGGLE</th>
          <th>FSM</th>
          <th>BRANCH</th>
          <th>MODULE NAME</th>
        </tr>
      </thead>
      <tbody class="font-mono">
        {''.join([f'''<tr>
          <td class="font-bold">{m.score}%</td>
          <td>{m.line_cov}%</td>
          <td>{m.cond_cov}%</td>
          <td>{m.toggle_cov}%</td>
          <td>{f"{m.fsm_cov}%" if m.fsm_cov is not None else "N/A"}</td>
          <td>{m.branch_cov}%</td>
          <td class="font-sans font-medium text-slate-800">{m.module_name}</td>
        </tr>''' for m in report.hierarchical_coverage])}
      </tbody>
    </table>
  </div>

  <!-- DUT Port ↔ TB Signal Mapping -->
  <div class="bg-white border border-slate-300 rounded shadow-sm overflow-hidden">
    <div class="bg-slate-100 px-4 py-2 border-b border-slate-300 flex justify-between items-center">
      <h2 class="text-xs font-bold text-slate-700 uppercase tracking-wider">DUT PORT ↔ TB SIGNAL MAPPING & STIMULUS</h2>
      <span class="text-xs text-slate-500 font-mono">{len(report.signal_mapping)} Ports Analyzed</span>
    </div>
    <table class="w-full text-left border-collapse eda-table text-xs">
      <thead>
        <tr>
          <th>DUT Port</th>
          <th>Direction</th>
          <th>Width</th>
          <th>TB Connection</th>
          <th>Stimulus Status</th>
          <th>Observation Status</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody class="font-mono">
        {''.join([f'''<tr>
          <td class="font-bold text-slate-900">{s.dut_port}</td>
          <td><span class="px-1.5 py-0.5 rounded text-[10px] {'bg-blue-50 text-blue-700' if s.direction == 'input' else 'bg-purple-50 text-purple-700'}">{s.direction}</span></td>
          <td>{s.width}</td>
          <td>{s.tb_connection}</td>
          <td>{s.stimulus_status}</td>
          <td>{s.observation_status}</td>
          <td><span class="px-1.5 py-0.5 rounded text-[10px] font-sans font-bold {'bg-emerald-100 text-emerald-800' if s.status == 'OK' else ('bg-amber-100 text-amber-800' if s.status == 'WARNING' else 'bg-rose-100 text-rose-800')}">{s.status}</span></td>
        </tr>''' for s in report.signal_mapping])}
      </tbody>
    </table>
  </div>

  <!-- Potential Coverage Gaps -->
  <div class="bg-white border border-slate-300 rounded shadow-sm overflow-hidden">
    <div class="bg-slate-100 px-4 py-2 border-b border-slate-300 flex justify-between items-center">
      <h2 class="text-xs font-bold text-slate-700 uppercase tracking-wider">POTENTIAL COVERAGE GAPS & VERIFICATION ACTION ITEMS</h2>
      <span class="text-xs text-slate-500">{len(report.gaps)} Finding(s)</span>
    </div>
    <div class="p-4 space-y-3">
      {''.join([f'''<div class="border rounded p-3.5 {'border-rose-300 bg-rose-50/40' if g.severity == 'HIGH' else ('border-amber-300 bg-amber-50/40' if g.severity == 'MEDIUM' else 'border-slate-300 bg-slate-50/50')}">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold {'bg-rose-600 text-white' if g.severity == 'HIGH' else ('bg-amber-500 text-white' if g.severity == 'MEDIUM' else 'bg-slate-600 text-white')}">{g.severity}</span>
            <span class="font-bold text-xs text-slate-900">{g.title}</span>
          </div>
          <span class="text-[11px] font-mono text-slate-500">{g.rtl_file}:{g.rtl_line}</span>
        </div>
        <p class="text-xs text-slate-700 mt-2">{g.description}</p>
        <div class="mt-2 text-xs bg-white/70 p-2 rounded border border-slate-200 text-slate-600 font-mono">
          <span class="font-bold font-sans text-slate-700">Evidence:</span> {g.evidence}
        </div>
        <div class="mt-2 text-xs text-indigo-900 font-sans font-medium">
          💡 <span class="font-semibold">Recommended Action:</span> {g.suggested_action}
        </div>
      </div>''' for g in report.gaps]) if report.gaps else '<div class="text-xs text-slate-500 italic p-4">No critical verification gaps detected.</div>'}
    </div>
  </div>

  <div class="text-center text-xs text-slate-400 py-4 border-t border-slate-200">
    Generated by URG Report for RTL Code &bull; Pre-Simulation Static Coverage Analysis &bull; Not affiliated with Synopsys Inc.
  </div>

</div>
</body>
</html>"""
        return html

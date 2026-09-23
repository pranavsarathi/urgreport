/**
 * URG Report for RTL Code — Frontend Application Logic
 */

// Application State
const state = {
  rtlFiles: [{ filename: "rtl.v", content: "" }],
  activeRtlIndex: 0,
  rtlContent: "",
  tbContent: "",
  rtlFilename: "rtl.v",
  tbFilename: "testbench.v",
  report: null,
  activeFinding: null,
  sessionId: "session_" + Math.random().toString(36).substring(2, 9),
  currentTab: "dashboard",
  monacoRtl: null,
  monacoTb: null,
  useMonaco: false
};

const STAGES = [
  "Reading RTL",
  "Detecting modules",
  "Detecting DUT ports",
  "Parsing procedural blocks",
  "Detecting branches",
  "Detecting conditions",
  "Detecting case statements",
  "Detecting FSM structures",
  "Reading testbench",
  "Detecting stimulus",
  "Mapping DUT connections",
  "Checking output observation",
  "Generating report"
];

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  setupNotepadHandlers();
  setupNavigation();
  setupExportHandlers();
  setupWhyModal();
  setupMethodologyModal();
  setupBeforeAfterHandlers();
  loadExamplesCatalog();
  initMonaco();
});

// Setup Monaco Editor if available
function initMonaco() {
  if (window.require) {
    window.require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
    window.require(['vs/editor/editor.main'], function () {
      state.useMonaco = true;
    });
  }
}

// -------------------------------------------------------------
// Dual Notepad Handlers & Live Sync
// -------------------------------------------------------------
function setupNotepadHandlers() {
  const rtlTextarea = document.getElementById("rtlTextarea");
  const tbTextarea = document.getElementById("tbTextarea");
  const rtlGutter = document.getElementById("rtlGutter");
  const tbGutter = document.getElementById("tbGutter");
  const rtlFilenameInput = document.getElementById("rtlFilenameInput");
  const tbFilenameInput = document.getElementById("tbFilenameInput");
  const rtlFileInput = document.getElementById("rtlFileInput");
  const tbFileInput = document.getElementById("tbFileInput");
  const btnClearRtl = document.getElementById("btnClearRtlText");
  const btnClearTb = document.getElementById("btnClearTbText");
  const btnClearBoth = document.getElementById("btnClearBoth");
  const btnAnalyze = document.getElementById("btnAnalyze");
  const rtlBox = document.getElementById("rtlNotepadBox");
  const tbBox = document.getElementById("tbNotepadBox");

  const btnAddRtlFile = document.getElementById("btnAddRtlFile");

  // Render RTL File Tabs
  function renderRtlFileTabs() {
    const container = document.getElementById("rtlFileTabs");
    const countBadge = document.getElementById("rtlFileCountBadge");
    if (!container) return;
    container.innerHTML = "";

    if (countBadge) {
      countBadge.textContent = `${state.rtlFiles.length} File${state.rtlFiles.length > 1 ? "s" : ""}`;
    }

    state.rtlFiles.forEach((file, idx) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = `rtl-file-tab ${idx === state.activeRtlIndex ? "active" : ""}`;
      tab.title = `Switch to ${file.filename}`;

      const nameSpan = document.createElement("span");
      nameSpan.textContent = file.filename;
      tab.appendChild(nameSpan);

      if (state.rtlFiles.length > 1) {
        const closeBtn = document.createElement("span");
        closeBtn.className = "rtl-file-tab-close";
        closeBtn.innerHTML = "&times;";
        closeBtn.title = "Remove this file";
        closeBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          removeRtlFile(idx);
        });
        tab.appendChild(closeBtn);
      }

      tab.addEventListener("click", () => {
        switchRtlFile(idx);
      });

      container.appendChild(tab);
    });
  }

  function switchRtlFile(newIdx) {
    if (newIdx < 0 || newIdx >= state.rtlFiles.length) return;
    // Save current textarea content to active file
    state.rtlFiles[state.activeRtlIndex].content = rtlTextarea.value;
    state.rtlFiles[state.activeRtlIndex].filename = rtlFilenameInput.value.trim() || state.rtlFiles[state.activeRtlIndex].filename;

    state.activeRtlIndex = newIdx;
    rtlFilenameInput.value = state.rtlFiles[newIdx].filename;
    rtlTextarea.value = state.rtlFiles[newIdx].content || "";
    renderRtlFileTabs();
    updateRtlGutterAndStats();
  }

  function addRtlFile(filename = "", content = "") {
    state.rtlFiles[state.activeRtlIndex].content = rtlTextarea.value;
    state.rtlFiles[state.activeRtlIndex].filename = rtlFilenameInput.value.trim() || state.rtlFiles[state.activeRtlIndex].filename;

    const fn = filename || `submodule_${state.rtlFiles.length}.v`;
    state.rtlFiles.push({ filename: fn, content: content });
    switchRtlFile(state.rtlFiles.length - 1);
  }

  function removeRtlFile(idx) {
    if (state.rtlFiles.length <= 1) return;
    state.rtlFiles.splice(idx, 1);
    if (state.activeRtlIndex >= state.rtlFiles.length) {
      state.activeRtlIndex = state.rtlFiles.length - 1;
    }
    const cur = state.rtlFiles[state.activeRtlIndex];
    rtlFilenameInput.value = cur.filename;
    rtlTextarea.value = cur.content || "";
    renderRtlFileTabs();
    updateRtlGutterAndStats();
  }

  if (btnAddRtlFile) {
    btnAddRtlFile.addEventListener("click", () => addRtlFile());
  }

  rtlFilenameInput.addEventListener("input", () => {
    state.rtlFiles[state.activeRtlIndex].filename = rtlFilenameInput.value.trim() || "file.v";
    renderRtlFileTabs();
  });

  // Sync RTL Textarea
  function updateRtlGutterAndStats() {
    const text = rtlTextarea.value;
    state.rtlFiles[state.activeRtlIndex].content = text;

    // Auto-detect module name if single file or default filename
    const m = text.match(/\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)/);
    if (m && m[1]) {
      const modName = m[1];
      const curFn = rtlFilenameInput.value.trim();
      if (curFn === "rtl.v" || (!curFn.includes(modName) && state.rtlFiles.length === 1)) {
        rtlFilenameInput.value = `${modName}.v`;
        state.rtlFiles[state.activeRtlIndex].filename = `${modName}.v`;
        renderRtlFileTabs();
      }
    }

    state.rtlFiles[state.activeRtlIndex].filename = rtlFilenameInput.value.trim() || "rtl.v";
    state.rtlContent = state.rtlFiles.map(f => f.content).join("\n\n");
    state.rtlFilename = state.rtlFiles[0].filename;

    const lineCount = text ? text.split("\n").length : 1;
    rtlGutter.innerHTML = Array.from({ length: lineCount }, (_, i) => i + 1).join("<br>");
    const bytes = new Blob([text]).size;
    const sizeStr = bytes > 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} bytes`;
    document.getElementById("rtlStats").textContent = `${lineCount} lines • ${sizeStr} (${state.rtlFiles.length} file${state.rtlFiles.length > 1 ? "s" : ""})`;
    updateAnalyzeBtn();
  }

  // Sync TB Textarea
  function updateTbGutterAndStats() {
    const text = tbTextarea.value;
    state.tbContent = text;

    // Auto-detect testbench module name
    const m = text.match(/\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)/);
    if (m && m[1]) {
      const tbModName = m[1];
      const curFn = tbFilenameInput.value.trim();
      if (curFn === "testbench.v" || (!curFn.includes(tbModName) && !curFn.includes(tbModName.replace("_tb", "")))) {
        tbFilenameInput.value = `${tbModName}.v`;
        state.tbFilename = `${tbModName}.v`;
      }
    }

    state.tbFilename = tbFilenameInput.value.trim() || "testbench.v";
    const lineCount = text ? text.split("\n").length : 1;
    tbGutter.innerHTML = Array.from({ length: lineCount }, (_, i) => i + 1).join("<br>");
    const bytes = new Blob([text]).size;
    const sizeStr = bytes > 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} bytes`;
    document.getElementById("tbStats").textContent = `${lineCount} lines • ${sizeStr}`;
    updateAnalyzeBtn();
  }

  // Bind input & scroll events
  rtlTextarea.addEventListener("input", updateRtlGutterAndStats);
  rtlTextarea.addEventListener("scroll", () => {
    rtlGutter.scrollTop = rtlTextarea.scrollTop;
  });

  tbTextarea.addEventListener("input", updateTbGutterAndStats);
  tbTextarea.addEventListener("scroll", () => {
    tbGutter.scrollTop = tbTextarea.scrollTop;
  });

  // Tab key & Ctrl+Enter handling in both textareas
  [rtlTextarea, tbTextarea].forEach(ta => {
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        ta.value = ta.value.substring(0, start) + "    " + ta.value.substring(end);
        ta.selectionStart = ta.selectionEnd = start + 4;
        if (ta === rtlTextarea) updateRtlGutterAndStats();
        else updateTbGutterAndStats();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        if (state.rtlContent && state.tbContent) {
          startAnalysis();
        }
      }
    });
  });

  // Clear buttons
  btnClearRtl.addEventListener("click", () => {
    rtlTextarea.value = "";
    state.rtlFiles[state.activeRtlIndex].content = "";
    updateRtlGutterAndStats();
  });

  btnClearTb.addEventListener("click", () => {
    tbTextarea.value = "";
    updateTbGutterAndStats();
  });

  btnClearBoth.addEventListener("click", () => {
    state.rtlFiles = [{ filename: "rtl.v", content: "" }];
    state.activeRtlIndex = 0;
    rtlFilenameInput.value = "rtl.v";
    rtlTextarea.value = "";
    tbTextarea.value = "";
    renderRtlFileTabs();
    updateRtlGutterAndStats();
    updateTbGutterAndStats();
  });

  // File Upload buttons
  rtlFileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      if (e.target.files.length === 1) {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = (evt) => {
          rtlTextarea.value = evt.target.result;
          rtlFilenameInput.value = file.name;
          state.rtlFiles[state.activeRtlIndex] = { filename: file.name, content: evt.target.result };
          renderRtlFileTabs();
          updateRtlGutterAndStats();
          hideLandingError();
        };
        reader.readAsText(file);
      } else {
        const filesArray = Array.from(e.target.files);
        let loaded = 0;
        const newFiles = [];
        filesArray.forEach((file, fIdx) => {
          const reader = new FileReader();
          reader.onload = (evt) => {
            newFiles[fIdx] = { filename: file.name, content: evt.target.result };
            loaded++;
            if (loaded === filesArray.length) {
              state.rtlFiles = newFiles;
              state.activeRtlIndex = 0;
              rtlFilenameInput.value = state.rtlFiles[0].filename;
              rtlTextarea.value = state.rtlFiles[0].content;
              renderRtlFileTabs();
              updateRtlGutterAndStats();
              hideLandingError();
            }
          };
          reader.readAsText(file);
        });
      }
    }
  });

  tbFileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (evt) => {
        tbTextarea.value = evt.target.result;
        tbFilenameInput.value = file.name;
        updateTbGutterAndStats();
        hideLandingError();
      };
      reader.readAsText(file);
    }
  });

  // Drag & drop directly onto either notepad
  ['dragenter', 'dragover'].forEach(evt => {
    rtlBox.addEventListener(evt, (e) => {
      e.preventDefault();
      rtlBox.classList.add("border-sky-500", "ring-2", "ring-sky-200");
    });
    tbBox.addEventListener(evt, (e) => {
      e.preventDefault();
      tbBox.classList.add("border-emerald-500", "ring-2", "ring-emerald-200");
    });
  });
  ['dragleave', 'drop'].forEach(evt => {
    rtlBox.addEventListener(evt, (e) => {
      e.preventDefault();
      rtlBox.classList.remove("border-sky-500", "ring-2", "ring-sky-200");
    });
    tbBox.addEventListener(evt, (e) => {
      e.preventDefault();
      tbBox.classList.remove("border-emerald-500", "ring-2", "ring-emerald-200");
    });
  });

  rtlBox.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length > 0) {
      if (e.dataTransfer.files.length === 1) {
        const file = e.dataTransfer.files[0];
        const reader = new FileReader();
        reader.onload = (evt) => {
          rtlTextarea.value = evt.target.result;
          rtlFilenameInput.value = file.name;
          state.rtlFiles[state.activeRtlIndex] = { filename: file.name, content: evt.target.result };
          renderRtlFileTabs();
          updateRtlGutterAndStats();
          hideLandingError();
        };
        reader.readAsText(file);
      } else {
        const filesArray = Array.from(e.dataTransfer.files);
        let loaded = 0;
        const newFiles = [];
        filesArray.forEach((file, fIdx) => {
          const reader = new FileReader();
          reader.onload = (evt) => {
            newFiles[fIdx] = { filename: file.name, content: evt.target.result };
            loaded++;
            if (loaded === filesArray.length) {
              state.rtlFiles = newFiles;
              state.activeRtlIndex = 0;
              rtlFilenameInput.value = state.rtlFiles[0].filename;
              rtlTextarea.value = state.rtlFiles[0].content;
              renderRtlFileTabs();
              updateRtlGutterAndStats();
              hideLandingError();
            }
          };
          reader.readAsText(file);
        });
      }
    }
  });

  tbBox.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const reader = new FileReader();
      reader.onload = (evt) => {
        tbTextarea.value = evt.target.result;
        tbFilenameInput.value = file.name;
        updateTbGutterAndStats();
        hideLandingError();
      };
      reader.readAsText(file);
    }
  });

  // Analyze button
  btnAnalyze.addEventListener("click", () => {
    state.rtlFiles[state.activeRtlIndex].content = rtlTextarea.value;
    state.rtlFiles[state.activeRtlIndex].filename = rtlFilenameInput.value.trim() || "rtl.v";
    state.rtlFilename = state.rtlFiles[0].filename;
    state.tbFilename = tbFilenameInput.value.trim() || "testbench.v";
    startAnalysis();
  });

  document.getElementById("btnNewAnalysis").addEventListener("click", () => {
    resetToLanding();
  });

  renderRtlFileTabs();
}

function updateAnalyzeBtn() {
  const btn = document.getElementById("btnAnalyze");
  btn.disabled = !(state.rtlContent && state.rtlContent.trim() && state.tbContent && state.tbContent.trim());
}

// -------------------------------------------------------------
// Reference Examples Loader
// -------------------------------------------------------------
async function loadExamplesCatalog() {
  try {
    const res = await fetch("/api/examples");
    const examples = await res.json();
    const container = document.getElementById("examplesContainer");
    container.innerHTML = "";

    examples.forEach(ex => {
      const card = document.createElement("div");
      card.className = "bg-white border border-slate-200 hover:border-sky-400 rounded p-3 text-left transition shadow-xs cursor-pointer";
      card.innerHTML = `
        <div class="font-semibold text-xs text-slate-800 flex items-center justify-between">
          <span>${ex.name}</span>
          <span class="text-[10px] text-sky-600 bg-sky-50 border border-sky-200 px-1.5 py-0.5 rounded font-mono font-medium">Load &amp; Edit</span>
        </div>
        <p class="text-[11px] text-slate-500 mt-1 line-clamp-2">${ex.description}</p>
        <div class="text-[10px] text-slate-400 font-mono mt-2">${ex.rtl_file} + ${ex.tb_file}</div>
      `;
      card.addEventListener("click", () => loadSpecificExample(ex.id));
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to load examples", err);
  }
}

async function loadSpecificExample(exampleId) {
  try {
    const res = await fetch(`/api/examples/${exampleId}`);
    if (!res.ok) throw new Error("Could not fetch example");
    const data = await res.json();

    const rtlTextarea = document.getElementById("rtlTextarea");
    const tbTextarea = document.getElementById("tbTextarea");
    const rtlFilenameInput = document.getElementById("rtlFilenameInput");
    const tbFilenameInput = document.getElementById("tbFilenameInput");

    if (data.files && data.files.length > 0) {
      state.rtlFiles = data.files;
      state.activeRtlIndex = 0;
      rtlFilenameInput.value = state.rtlFiles[0].filename;
      rtlTextarea.value = state.rtlFiles[0].content;
    } else {
      state.rtlFiles = [{ filename: data.rtl_filename, content: data.rtl_content }];
      state.activeRtlIndex = 0;
      rtlFilenameInput.value = data.rtl_filename;
      rtlTextarea.value = data.rtl_content;
    }

    tbTextarea.value = data.tb_content;
    tbFilenameInput.value = data.tb_filename;

    state.rtlContent = state.rtlFiles.map(f => f.content).join("\n\n");
    state.rtlFilename = state.rtlFiles[0].filename;
    state.tbContent = data.tb_content;
    state.tbFilename = data.tb_filename;

    const countBadge = document.getElementById("rtlFileCountBadge");
    if (countBadge) countBadge.textContent = `${state.rtlFiles.length} File${state.rtlFiles.length > 1 ? "s" : ""}`;

    const tabsContainer = document.getElementById("rtlFileTabs");
    if (tabsContainer) {
      tabsContainer.innerHTML = "";
      state.rtlFiles.forEach((file, idx) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = `rtl-file-tab ${idx === state.activeRtlIndex ? "active" : ""}`;
        tab.textContent = file.filename;
        tab.addEventListener("click", () => {
          state.rtlFiles[state.activeRtlIndex].content = rtlTextarea.value;
          state.activeRtlIndex = idx;
          rtlFilenameInput.value = state.rtlFiles[idx].filename;
          rtlTextarea.value = state.rtlFiles[idx].content;
          tabsContainer.querySelectorAll(".rtl-file-tab").forEach((t, i) => {
            t.className = `rtl-file-tab ${i === idx ? "active" : ""}`;
          });
          rtlTextarea.dispatchEvent(new Event("input"));
        });
        tabsContainer.appendChild(tab);
      });
    }

    // Trigger input events to update gutters and stats
    rtlTextarea.dispatchEvent(new Event("input"));
    tbTextarea.dispatchEvent(new Event("input"));

    hideLandingError();

    // Auto trigger analysis for immediate results
    startAnalysis();
  } catch (err) {
    showLandingError("Failed to load example design", err.message);
  }
}

// -------------------------------------------------------------
// Live Analysis Pipeline with Real Stages
// -------------------------------------------------------------
async function startAnalysis() {
  const modal = document.getElementById("progressModal");
  const stagesList = document.getElementById("progressStagesList");
  const progressBar = document.getElementById("progressBar");
  const progressPct = document.getElementById("progressPct");

  modal.classList.remove("hidden");
  stagesList.innerHTML = "";

  // Render initial pending stages
  STAGES.forEach((stage, idx) => {
    const row = document.createElement("div");
    row.id = `stage-row-${idx}`;
    row.className = "flex items-center gap-2 text-xs text-slate-400 py-0.5";
    row.innerHTML = `
      <span class="w-4 h-4 rounded-full border border-slate-300 flex items-center justify-center text-[10px]">&bull;</span>
      <span>${stage}...</span>
    `;
    stagesList.appendChild(row);
  });

  let currentStage = 0;
  const stageInterval = setInterval(() => {
    if (currentStage < STAGES.length - 1) {
      markStageDone(currentStage);
      currentStage++;
      const pct = Math.round((currentStage / STAGES.length) * 100);
      progressBar.style.width = `${pct}%`;
      progressPct.textContent = `${pct}%`;
    }
  }, 120);

  const payload = {
    tb_content: state.tbContent,
    tb_filename: state.tbFilename,
    session_id: state.sessionId
  };
  if (state.rtlFiles.length > 1) {
    payload.files = state.rtlFiles;
    payload.rtl_filename = state.rtlFiles[0].filename;
  } else {
    payload.rtl_content = state.rtlFiles[0].content;
    payload.rtl_filename = state.rtlFiles[0].filename;
  }

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    clearInterval(stageInterval);

    if (!response.ok) {
      const err = await response.json();
      throw err;
    }

    const report = await response.json();
    state.report = report;

    // Complete all stages to 100%
    for (let i = 0; i < STAGES.length; i++) {
      markStageDone(i);
    }
    progressBar.style.width = "100%";
    progressPct.textContent = "100%";

    setTimeout(() => {
      modal.classList.add("hidden");
      renderReport(report);
    }, 400);

  } catch (err) {
    clearInterval(stageInterval);
    modal.classList.add("hidden");
    const detail = err.detail || {};
    showLandingError(
      detail.error_type === "PARSER_ERROR" ? "Verilog Parser Error" : "Analysis Failed",
      detail.message || err.message || "An error occurred while parsing Verilog files.",
      detail.file ? `File: ${detail.file}, Line: ${detail.line}\nCause: ${detail.possible_cause || ''}` : null
    );
  }
}

function markStageDone(idx) {
  const row = document.getElementById(`stage-row-${idx}`);
  if (row) {
    row.className = "flex items-center gap-2 text-xs text-emerald-700 font-medium py-0.5";
    row.innerHTML = `
      <span class="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-[10px] font-bold">✓</span>
      <span>${STAGES[idx]}</span>
    `;
  }
}

function showLandingError(title, msg, details) {
  const errBox = document.getElementById("landingError");
  document.getElementById("landingErrorTitle").textContent = title;
  document.getElementById("landingErrorMessage").textContent = msg;
  const dBox = document.getElementById("landingErrorDetails");
  if (details) {
    dBox.textContent = details;
    dBox.classList.remove("hidden");
  } else {
    dBox.classList.add("hidden");
  }
  errBox.classList.remove("hidden");
}

function hideLandingError() {
  document.getElementById("landingError").classList.add("hidden");
}

function resetToLanding() {
  document.getElementById("reportContainer").classList.add("hidden");
  document.getElementById("reportNavBar").classList.add("hidden");
  document.getElementById("landingView").classList.remove("hidden");
  ["btnNewAnalysis", "btnExportHtml", "btnExportPdf", "btnExportJson"].forEach(id => {
    document.getElementById(id).classList.add("hidden");
  });
  updateAnalyzeBtn();
}

// -------------------------------------------------------------
// Report Dashboard Rendering
// -------------------------------------------------------------
function renderReport(report) {
  document.getElementById("landingView").classList.add("hidden");
  document.getElementById("reportContainer").classList.remove("hidden");
  document.getElementById("reportNavBar").classList.remove("hidden");

  // Show top right actions
  ["btnNewAnalysis", "btnExportHtml", "btnExportPdf", "btnExportJson"].forEach(id => {
    document.getElementById(id).classList.remove("hidden");
  });

  // Header data
  document.getElementById("repDesignName").textContent = report.design_name;
  if (document.getElementById("repTopModule")) {
    document.getElementById("repTopModule").textContent = report.top_module || report.design_name || "-";
  }
  if (document.getElementById("repRtlFilesPills")) {
    const files = report.design_files && report.design_files.length > 0 ? report.design_files : [report.rtl_filename];
    document.getElementById("repRtlFilesPills").innerHTML = files.map(f => `<span class="bg-slate-100 border border-slate-300 px-1.5 py-0.5 rounded text-[11px] font-mono text-slate-800">${escapeHtml(f)}</span>`).join("");
  }
  if (document.getElementById("repLinesStats")) {
    document.getElementById("repLinesStats").textContent = `${report.total_rtl_lines || 0} RTL • ${report.total_tb_lines || 0} TB`;
  }
  const partialBadge = document.getElementById("repAnalysisStatusBadge");
  if (partialBadge) {
    if (report.partial_analysis) {
      partialBadge.classList.remove("hidden");
      partialBadge.title = (report.partial_reasons || []).join("; ");
    } else {
      partialBadge.classList.add("hidden");
    }
  }
  if (document.getElementById("repRtlFile")) document.getElementById("repRtlFile").textContent = report.rtl_filename;
  document.getElementById("repTbFile").textContent = report.tb_filename;
  document.getElementById("repTimestamp").textContent = report.timestamp;

  document.getElementById("navDutName").textContent = report.top_module || report.design_name;
  document.getElementById("navScore").textContent = `${report.total_summary.score !== null ? report.total_summary.score : 0}%`;
  document.getElementById("navGapsBadge").textContent = report.gaps.length;

  // 0. Before / After Comparison Banner
  renderBeforeAfterBanner(report.before_after);

  // 1. Total Coverage Summary
  renderTotalSummary(report.total_summary);

  // 2. Hierarchical Coverage Table
  renderHierarchicalTable(report.hierarchical_coverage);

  // 3. Module Definition Summary
  renderModuleDefinition(report.modules[0], report.gaps);

  // 4. Testbench Structure Summary
  renderTestbenchStructure(report.tb_model);

  // 5. Gaps Preview
  renderGapsPreview(report.gaps);

  // 6. Detailed Tables
  renderBranchesTable(report.branches);
  renderConditionsList(report.conditions);
  renderSignalsTable(report.signal_mapping);
  renderFsmView(report.modules[0]);
  renderGapsList(report.gaps);
  renderCoverageBreakdown(report.total_summary);
  renderLogs(report.logs);
  renderHierarchyTree(report.modules, report.hierarchy);

  // 7. Initialize Code Viewers
  setupCodeViewers(report.raw_rtl, report.raw_tb, report.rtl_filename, report.tb_filename);

  // Default to Dashboard tab
  switchTab("dashboard");
}

function badgeClass(val) {
  if (val === null || val === undefined) return "badge-na";
  if (val >= 80) return "badge-covered";
  if (val >= 50) return "badge-warning";
  return "badge-untested";
}

function renderTotalSummary(sum) {
  document.getElementById("covScore").textContent = `${sum.score}%`;
  document.getElementById("covLine").innerHTML = `<span class="${badgeClass(sum.line_cov)}">${sum.line_cov}%</span>`;
  document.getElementById("covCond").innerHTML = sum.cond_cov !== null && sum.cond_cov !== undefined ? `<span class="${badgeClass(sum.cond_cov)}">${sum.cond_cov}%</span>` : `<span class="badge-na">N/A</span>`;
  document.getElementById("covToggle").innerHTML = `<span class="${badgeClass(sum.toggle_cov)}">${sum.toggle_cov}%</span>`;
  document.getElementById("covFsm").innerHTML = sum.fsm_cov !== null ? `<span class="${badgeClass(sum.fsm_cov)}">${sum.fsm_cov}%</span>` : `<span class="badge-na">N/A</span>`;
  document.getElementById("covBranch").innerHTML = `<span class="${badgeClass(sum.branch_cov)}">${sum.branch_cov}%</span>`;
}

function renderHierarchicalTable(hier) {
  const tbody = document.getElementById("hierarchicalTableBody");
  tbody.innerHTML = "";
  hier.forEach(m => {
    const tr = document.createElement("tr");
    tr.className = "cursor-pointer hover:bg-slate-50";
    tr.innerHTML = `
      <td class="font-bold text-slate-900">${m.score}%</td>
      <td><span class="${badgeClass(m.line_cov)}">${m.line_cov}%</span></td>
      <td>${m.cond_cov !== null && m.cond_cov !== undefined ? `<span class="${badgeClass(m.cond_cov)}">${m.cond_cov}%</span>` : `<span class="badge-na">N/A</span>`}</td>
      <td><span class="${badgeClass(m.toggle_cov)}">${m.toggle_cov}%</span></td>
      <td>${m.fsm_cov !== null ? `<span class="${badgeClass(m.fsm_cov)}">${m.fsm_cov}%</span>` : `<span class="badge-na">N/A</span>`}</td>
      <td><span class="${badgeClass(m.branch_cov)}">${m.branch_cov}%</span></td>
      <td class="font-sans font-semibold text-slate-800 hover:text-sky-600">${m.module_name}</td>
    `;
    tr.addEventListener("click", () => switchTab("hierarchy"));
    tbody.appendChild(tr);
  });
}

function renderModuleDefinition(mod, gaps) {
  if (!mod) return;
  document.getElementById("modSummaryName").textContent = mod.name;
  const list = document.getElementById("modDefinitionMetrics");
  const inPorts = mod.ports.filter(p => p.direction === "input").map(p => p.name).join(", ") || "None";
  const outPorts = mod.ports.filter(p => p.direction === "output").map(p => p.name).join(", ") || "None";

  list.innerHTML = `
    <li class="flex justify-between"><span>Inputs:</span> <span class="font-mono text-slate-800 text-[11px] truncate max-w-[180px]" title="${inPorts}">${inPorts}</span></li>
    <li class="flex justify-between"><span>Outputs:</span> <span class="font-mono text-slate-800 text-[11px] truncate max-w-[180px]" title="${outPorts}">${outPorts}</span></li>
    <li class="flex justify-between"><span>Always Blocks:</span> <span class="font-mono font-semibold">${mod.always_blocks.length}</span></li>
    <li class="flex justify-between"><span>Branches:</span> <span class="font-mono font-semibold">${mod.branches.length}</span></li>
    <li class="flex justify-between"><span>Conditions:</span> <span class="font-mono font-semibold">${mod.conditions.length}</span></li>
    <li class="flex justify-between"><span>Case Items:</span> <span class="font-mono font-semibold">${mod.case_statements.reduce((acc, c) => acc + c.items.length, 0)}</span></li>
    <li class="flex justify-between"><span>FSM Detected:</span> <span class="font-semibold ${mod.fsm ? 'text-emerald-700' : 'text-slate-500'}">${mod.fsm ? 'Yes (' + mod.fsm.detected_states.length + ' states)' : 'No'}</span></li>
    <li class="flex justify-between"><span>Verification Gaps:</span> <span class="font-mono font-bold text-rose-600">${gaps.length}</span></li>
  `;
}

function renderTestbenchStructure(tb) {
  if (!tb) return;
  document.getElementById("tbSummaryTotalEvents").textContent = `${tb.stimulus.length} stimulus events`;
  const list = document.getElementById("tbStructureMetrics");

  const hasRtlClock = state.report && state.report.modules && state.report.modules.some(m => (m.always_blocks && m.always_blocks.some(b => b.is_clocked)) || (m.ports && m.ports.some(p => /clk|clock/i.test(p.name))));
  const hasRtlReset = state.report && state.report.modules && state.report.modules.some(m => (m.always_blocks && m.always_blocks.some(b => b.reset_signal)) || (m.ports && m.ports.some(p => /rst|reset/i.test(p.name))));

  const clkStatus = tb.clocks.length > 0 
    ? `<span class="text-emerald-700 font-bold">✓ Detected (${tb.clocks[0].signal_name})</span>` 
    : (hasRtlClock ? `<span class="text-rose-600 font-bold">✗ Not Found</span>` : `<span class="text-slate-500 font-medium">N/A (Combinational)</span>`);

  const rstStatus = tb.resets.length > 0 
    ? `<span class="text-emerald-700 font-bold">✓ ${tb.resets[0].signal_name} (${tb.resets[0].polarity})</span>` 
    : (hasRtlReset ? `<span class="text-rose-600 font-bold">✗ Not Found</span>` : `<span class="text-slate-500 font-medium">N/A (Combinational)</span>`);

  const dutStatus = tb.dut_instances.length > 0 ? `<span class="text-emerald-700 font-bold">✓ Instantiated (${tb.dut_instances[0].instance_name})</span>` : `<span class="text-amber-600 font-bold">⚠ Positional/Direct</span>`;

  const checkedOutCount = tb.output_checks.filter(c => c.is_verified).length;
  const totalOutCount = tb.output_checks.length;

  list.innerHTML = `
    <li class="flex justify-between"><span>Clock Generator:</span> <span>${clkStatus}</span></li>
    <li class="flex justify-between"><span>Reset Sequence:</span> <span>${rstStatus}</span></li>
    <li class="flex justify-between"><span>DUT Instance:</span> <span>${dutStatus}</span></li>
    <li class="flex justify-between"><span>Active Stimulus Nets:</span> <span class="font-mono font-semibold">${Object.keys(tb.toggles).length}</span></li>
    <li class="flex justify-between"><span>Outputs Checked:</span> <span class="font-mono font-semibold ${checkedOutCount < totalOutCount ? 'text-rose-600' : 'text-emerald-700'}">${checkedOutCount} / ${totalOutCount}</span></li>
    <li class="flex justify-between"><span>Assertions Detected:</span> <span class="font-mono font-semibold">${tb.total_assertions}</span></li>
    <li class="flex justify-between"><span>Initial Blocks:</span> <span class="font-mono font-semibold">${tb.initial_blocks_count}</span></li>
  `;
}

function renderGapsPreview(gaps) {
  const container = document.getElementById("dashGapsPreview");
  container.innerHTML = "";
  if (!gaps || gaps.length === 0) {
    container.innerHTML = `<div class="text-slate-500 italic py-4 text-center">No critical verification gaps found!</div>`;
    return;
  }

  gaps.slice(0, 4).forEach(gap => {
    const div = document.createElement("div");
    const sevClass = gap.severity === "HIGH" ? "text-rose-700 bg-rose-50 border-rose-200" : (
      gap.severity === "MEDIUM" ? "text-amber-800 bg-amber-50 border-amber-200" : "text-slate-700 bg-slate-50 border-slate-200"
    );
    div.className = `p-2 rounded border ${sevClass} text-[11px] cursor-pointer hover:opacity-90`;
    div.innerHTML = `
      <div class="flex items-center justify-between font-bold">
        <span>[${gap.severity}] ${gap.title}</span>
        <span class="text-[10px] font-mono opacity-70">L${gap.rtl_line}</span>
      </div>
    `;
    div.addEventListener("click", () => {
      switchTab("gaps");
    });
    container.appendChild(div);
  });
}

// -------------------------------------------------------------
// Detailed Section Renderers
// -------------------------------------------------------------
function renderBranchesTable(branches) {
  const tbody = document.getElementById("branchesTableBody");
  document.getElementById("branchesCountBadge").textContent = `${branches.length} Branches`;
  tbody.innerHTML = "";

  const filter = document.getElementById("branchFilter").value;

  branches.forEach(br => {
    if (filter !== "ALL" && br.status !== filter) return;

    const tr = document.createElement("tr");
    const isCovered = br.status === "COVERED";
    tr.className = `hover:bg-slate-50 ${!isCovered ? 'bg-rose-50/20' : ''}`;
    tr.innerHTML = `
      <td class="font-bold text-slate-800">${br.id}</td>
      <td class="text-slate-500">L${br.line}</td>
      <td><span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-100">${br.branch_type}</span></td>
      <td class="font-mono text-slate-900">${escapeHtml(br.condition_expr)}</td>
      <td>${br.stimulated_true ? '<span class="text-emerald-600 font-bold">✓ Stimulated</span>' : '<span class="text-slate-400">✗ None</span>'}</td>
      <td>${br.stimulated_false ? '<span class="text-emerald-600 font-bold">✓ Stimulated</span>' : '<span class="text-slate-400">✗ None</span>'}</td>
      <td><span class="${isCovered ? 'badge-covered' : 'badge-untested'}">${br.status}</span></td>
      <td class="whitespace-nowrap space-x-1">
        <button class="px-1.5 py-0.5 text-[10px] bg-slate-100 hover:bg-sky-100 text-sky-700 rounded border border-slate-300" onclick="jumpToCode('rtl', ${br.line})">
          View
        </button>
        ${br.finding_id ? `<button class="btn-why" onclick="openWhyModal('${br.finding_id}')"><span>?</span> WHY?</button>` : ''}
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById("branchFilter").onchange = () => renderBranchesTable(state.report.branches);
}

function renderConditionsList(conditions) {
  const container = document.getElementById("conditionsList");
  document.getElementById("conditionsCountBadge").textContent = `${conditions.length} Conditions`;
  container.innerHTML = "";

  conditions.forEach(cond => {
    const card = document.createElement("div");
    card.className = "border border-slate-200 rounded p-3 bg-white space-y-2.5";
    const statusBadge = cond.status === "COVERED" ? "badge-covered" : (cond.status === "PARTIALLY_TESTED" ? "badge-warning" : "badge-untested");

    // Truth Table HTML if available
    let truthTableHtml = "";
    if (cond.truth_table && cond.truth_table.length > 0) {
      truthTableHtml = `
        <div class="mt-2 pt-2 border-t border-slate-100">
          <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">Compound Condition Truth-Table Matrix</div>
          <table class="truth-table">
            <thead>
              <tr>
                ${cond.terms.map(t => `<th>${escapeHtml(t.variable)}</th>`).join('')}
                <th>Expected Outcome</th>
                <th>Pre-Sim TB Evidence</th>
              </tr>
            </thead>
            <tbody>
              ${cond.truth_table.map(row => {
                const isTested = row.status === "COVERED" || row.status === "EVALUATED_TRUE" || row.status === "EVALUATED_FALSE";
                return `
                  <tr>
                    <td>${escapeHtml(row.input_a)}</td>
                    <td>${escapeHtml(row.input_b)}</td>
                    <td class="font-bold">${escapeHtml(row.outcome)}</td>
                    <td class="${isTested ? 'truth-cell-tested' : 'truth-cell-untested'}">
                      ${isTested ? '✓ EVALUATED' : '⚠ UNTESTED COMBINATION'}
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    // Boundary conditions if available
    let boundaryHtml = "";
    if (cond.boundary_conditions && cond.boundary_conditions.length > 0) {
      boundaryHtml = `
        <div class="mt-2 pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-[11px]">
          <span class="font-semibold text-slate-700">Boundary Targets:</span>
          ${cond.boundary_conditions.map(b => `<span class="px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-mono text-[10px]">${escapeHtml(b)}</span>`).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex items-center justify-between pb-2 border-b border-slate-100">
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-800">${cond.id}</span>
          <span class="text-slate-400 font-mono">Line ${cond.line}</span>
          <span class="${statusBadge} text-[10px]">${cond.status}</span>
        </div>
        <div class="flex items-center gap-2">
          ${cond.finding_id ? `<button class="btn-why" onclick="openWhyModal('${cond.finding_id}')"><span>?</span> WHY?</button>` : ''}
          <button class="px-2 py-0.5 text-[10px] text-sky-700 bg-sky-50 hover:bg-sky-100 border border-sky-200 rounded" onclick="jumpToCode('rtl', ${cond.line})">
            Jump to Line ${cond.line}
          </button>
        </div>
      </div>

      <div class="font-mono text-xs bg-slate-50 p-2 rounded border border-slate-200 text-slate-800">
        ${escapeHtml(cond.raw_expression)}
      </div>

      <!-- Condition Terms Breakdown -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
        ${cond.terms.map(t => `
          <div class="p-2 rounded border border-slate-100 bg-slate-50/50 text-[11px]">
            <div class="font-semibold text-slate-700">${escapeHtml(t.variable)} (${escapeHtml(t.details)})</div>
            <div class="flex gap-4 mt-1">
              <span>HIGH (Match): ${t.stimulated_high ? '<span class="text-emerald-600 font-bold">✓</span>' : '<span class="text-rose-500 font-bold">✗</span>'}</span>
              <span>LOW (Inactive): ${t.stimulated_low ? '<span class="text-emerald-600 font-bold">✓</span>' : '<span class="text-rose-500 font-bold">✗</span>'}</span>
            </div>
          </div>
        `).join('')}
      </div>

      ${truthTableHtml}
      ${boundaryHtml}

      ${cond.missing_scenarios && cond.missing_scenarios.length > 0 ? `
        <div class="text-[11px] text-amber-800 bg-amber-50 p-2 rounded border border-amber-200">
          ⚠️ <strong>Potential Missing Scenario:</strong> ${cond.missing_scenarios.join("; ")}
        </div>
      ` : ''}
    `;
    container.appendChild(card);
  });
}

function renderSignalsTable(mapping) {
  const tbody = document.getElementById("signalsTableBody");
  document.getElementById("signalsCountBadge").textContent = `${mapping.length} Ports`;
  tbody.innerHTML = "";

  mapping.forEach(sig => {
    const tr = document.createElement("tr");
    const stBadge = sig.status === "OK" ? "badge-covered" : (sig.status === "WARNING" ? "badge-warning" : "badge-untested");
    tr.className = "hover:bg-slate-50";
    tr.innerHTML = `
      <td class="font-bold text-slate-900">${sig.dut_port}</td>
      <td><span class="px-1.5 py-0.5 rounded text-[10px] ${sig.direction === 'input' ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'}">${sig.direction}</span></td>
      <td>${sig.width}</td>
      <td class="text-slate-800 font-semibold">${sig.tb_connection}</td>
      <td>${sig.stimulus_status}</td>
      <td>${sig.observation_status}</td>
      <td><span class="${stBadge}">${sig.status}</span></td>
      <td class="whitespace-nowrap space-x-1">
        <button class="px-1.5 py-0.5 text-[10px] bg-slate-100 hover:bg-sky-100 text-sky-700 rounded border border-slate-300" onclick="jumpToCode('rtl', ${sig.rtl_line})">
          RTL:L${sig.rtl_line}
        </button>
        ${sig.finding_id ? `<button class="btn-why" onclick="openWhyModal('${sig.finding_id}')"><span>?</span> WHY?</button>` : ''}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderFsmView(mod) {
  const container = document.getElementById("fsmContainer");
  if (!mod || !mod.fsm) {
    container.innerHTML = `
      <div class="text-center py-10 space-y-2">
        <div class="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto text-base">ℹ</div>
        <h4 class="font-bold text-slate-700 text-sm">No Clocked FSM State Register Identified</h4>
        <p class="text-slate-500 text-xs max-w-md mx-auto">
          The structural parser analyzes clocked state registers with case transitions. If your design is pure combinational logic or uses an opcode multiplexer, FSM coverage correctly reports <strong>N/A</strong>.
        </p>
      </div>
    `;
    return;
  }

  const fsm = mod.fsm;
  const states = fsm.detected_states || [];
  const transitions = fsm.transitions || [];

  // Build SVG State Diagram
  let svgContent = "";
  if (states.length > 0) {
    const width = 640;
    const height = 300;
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(180, Math.max(90, states.length * 35));

    // Calculate node positions in circle
    const positions = {};
    states.forEach((st, idx) => {
      const angle = (2 * Math.PI * idx) / states.length - Math.PI / 2;
      positions[st] = {
        x: Math.round(cx + radius * Math.cos(angle)),
        y: Math.round(cy + radius * Math.sin(angle))
      };
    });

    let edgesSvg = "";
    transitions.forEach((tr, i) => {
      const p1 = positions[tr.from_state];
      const p2 = positions[tr.to_state];
      if (!p1 || !p2) return;

      if (tr.from_state === tr.to_state) {
        // Self-loop
        const loopR = 20;
        edgesSvg += `
          <path d="M ${p1.x - 15} ${p1.y - 20} A ${loopR} ${loopR} 0 1 1 ${p1.x + 15} ${p1.y - 20}" class="fsm-edge" />
          <text x="${p1.x}" y="${p1.y - 42}" class="fsm-edge-label">${escapeHtml(tr.condition_expr || 'hold')}</text>
        `;
      } else {
        // Curve between states
        const mx = (p1.x + p2.x) / 2 + (cy - (p1.y + p2.y) / 2) * 0.2;
        const my = (p1.y + p2.y) / 2 + ((p1.x + p2.x) / 2 - cx) * 0.2;
        edgesSvg += `
          <path d="M ${p1.x} ${p1.y} Q ${mx} ${my} ${p2.x} ${p2.y}" class="fsm-edge" />
          <text x="${mx}" y="${my - 4}" class="fsm-edge-label">${escapeHtml(tr.condition_expr || '')}</text>
        `;
      }
    });

    let nodesSvg = "";
    states.forEach((st, idx) => {
      const pos = positions[st];
      const isReset = idx === 0 || st.toLowerCase().includes("reset") || st.toLowerCase().includes("idle");
      const reachability = (fsm.reachability && fsm.reachability.find(r => r.state_name === st)) || null;
      const isReachable = reachability ? reachability.is_reachable : isReset;
      const nodeClass = isReset ? "fsm-node fsm-node-reset" : (isReachable ? "fsm-node fsm-node-reachable" : "fsm-node fsm-node-unreached");

      nodesSvg += `
        <g class="${nodeClass}" onclick="jumpToCode('rtl', ${fsm.line || 1})" title="${st}: ${isReachable ? 'Reachable' : 'Potentially Unreached'}">
          <circle cx="${pos.x}" cy="${pos.y}" r="28" />
          <text x="${pos.x}" y="${pos.y + 4}" text-anchor="middle" font-size="11" font-weight="bold" font-family="ui-monospace, monospace" fill="#0f172a">${st}</text>
          ${isReset ? `<text x="${pos.x}" y="${pos.y + 20}" text-anchor="middle" font-size="8" fill="#2563eb" font-weight="bold">RESET</text>` : ''}
        </g>
      `;
    });

    svgContent = `
      <div class="fsm-svg-container p-2 mb-4">
        <div class="flex items-center justify-between text-xs px-2 py-1 text-slate-500 border-b border-slate-200 mb-2">
          <span>Interactive State Transition Graph</span>
          <span class="flex items-center gap-3 text-[10px]">
            <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-blue-100 border border-blue-500 inline-block"></span> Reset State</span>
            <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-emerald-100 border border-emerald-500 inline-block"></span> Reachable</span>
            <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-full bg-amber-100 border border-amber-500 inline-block"></span> Untested Transition</span>
          </span>
        </div>
        <svg class="fsm-svg" viewBox="0 0 ${width} ${height}">
          <defs>
            <marker id="fsm-arrow" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b"/>
            </marker>
          </defs>
          ${edgesSvg}
          ${nodesSvg}
        </svg>
      </div>
    `;
  }

  // Reachability Table
  let reachabilityTable = "";
  if (fsm.reachability && fsm.reachability.length > 0) {
    reachabilityTable = `
      <div class="border border-slate-200 rounded overflow-hidden mt-4">
        <div class="bg-slate-50 px-3 py-2 border-b border-slate-200 font-bold text-xs text-slate-700">
          State Reachability &amp; Reset Assertion Evidence
        </div>
        <table class="w-full text-left border-collapse eda-table text-xs">
          <thead>
            <tr>
              <th>State</th>
              <th>Encoding / Value</th>
              <th>Reachable Status</th>
              <th>Static Evidence</th>
            </tr>
          </thead>
          <tbody class="font-mono">
            ${fsm.reachability.map(r => `
              <tr>
                <td class="font-bold text-slate-900">${escapeHtml(r.state_name)}</td>
                <td class="text-slate-500">${escapeHtml(r.state_value)}</td>
                <td>
                  <span class="${r.is_reachable ? 'badge-covered' : 'badge-untested'}">
                    ${r.is_reachable ? '✓ STATICALLY REACHABLE' : '⚠ POTENTIALLY UNREACHED'}
                  </span>
                </td>
                <td class="text-slate-700">${escapeHtml(r.evidence)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  // Container HTML
  container.innerHTML = `
    <div class="space-y-4">
      <div class="flex items-center justify-between pb-3 border-b border-slate-200">
        <div>
          <h4 class="text-sm font-bold text-slate-900">Finite State Machine Analysis</h4>
          <p class="text-xs text-slate-500">State Register: <code class="bg-slate-100 px-1 py-0.5 rounded font-mono text-slate-800">${escapeHtml(fsm.state_reg)}</code> &bull; Confidence: <span class="font-semibold text-emerald-700">${escapeHtml(fsm.confidence)}</span></p>
        </div>
        <span class="badge-covered text-xs">${states.length} States Identified</span>
      </div>

      <!-- State Pills -->
      <div class="flex flex-wrap gap-2">
        ${states.map(st => `
          <div class="px-3 py-1.5 rounded bg-slate-50 border border-slate-300 flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-sky-500"></span>
            <span class="font-mono font-bold text-xs text-slate-800">${escapeHtml(st)}</span>
          </div>
        `).join('')}
      </div>

      <!-- Interactive SVG Diagram -->
      ${svgContent}

      <!-- Reachability Table -->
      ${reachabilityTable}

      <!-- Transitions Table -->
      <div class="border border-slate-200 rounded overflow-hidden mt-4">
        <div class="bg-slate-50 px-3 py-2 border-b border-slate-200 font-bold text-xs text-slate-700 flex justify-between items-center">
          <span>Detected State Transitions</span>
          <span class="text-[10px] text-slate-400 font-normal">Pre-Simulation Correlation</span>
        </div>
        <table class="w-full text-left border-collapse eda-table text-xs">
          <thead>
            <tr>
              <th>From State</th>
              <th>To State</th>
              <th>Transition Condition</th>
              <th>Stimulus Evidence</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody class="font-mono">
            ${transitions.map(tr => `
              <tr>
                <td class="font-bold text-slate-900">${escapeHtml(tr.from_state)}</td>
                <td class="text-slate-800">&rarr; ${escapeHtml(tr.to_state)}</td>
                <td>${escapeHtml(tr.condition_expr)}</td>
                <td><span class="${tr.finding_id ? 'badge-warning' : 'badge-covered'}">${tr.finding_id ? '⚠ Untested' : '✓ Stimulated'}</span></td>
                <td>
                  ${tr.finding_id ? `<button class="btn-why" onclick="openWhyModal('${tr.finding_id}')"><span>?</span> WHY?</button>` : `<button class="px-1.5 py-0.5 text-[10px] bg-slate-100 hover:bg-sky-100 text-sky-700 rounded border border-slate-300" onclick="jumpToCode('rtl', ${tr.line || 1})">View</button>`}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderGapsList(gaps) {
  const container = document.getElementById("gapsList");
  document.getElementById("gapsCountBadge").textContent = `${gaps.length} Gaps`;
  container.innerHTML = "";

  const filter = document.getElementById("gapSeverityFilter").value;

  if (gaps.length === 0) {
    container.innerHTML = `<div class="p-6 text-center text-slate-500 italic">No verification gaps identified! Design and stimulus match properly.</div>`;
    return;
  }

  gaps.forEach(gap => {
    if (filter !== "ALL" && gap.severity !== filter) return;

    const card = document.createElement("div");
    const sevBadge = gap.severity === "HIGH" ? "bg-rose-600 text-white" : (gap.severity === "MEDIUM" ? "bg-amber-500 text-white" : "bg-slate-600 text-white");
    const cardBorder = gap.severity === "HIGH" ? "border-rose-300 bg-rose-50/20" : (gap.severity === "MEDIUM" ? "border-amber-300 bg-amber-50/20" : "border-slate-300 bg-slate-50/30");

    card.className = `border rounded p-4 ${cardBorder} space-y-2.5`;
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${sevBadge}">${gap.severity}</span>
          <h4 class="font-bold text-xs text-slate-900">${escapeHtml(gap.title)}</h4>
        </div>
        <div class="flex items-center gap-2">
          ${gap.finding_id ? `<button class="btn-why" onclick="openWhyModal('${gap.finding_id}')"><span>?</span> WHY?</button>` : ''}
          ${gap.rtl_line ? `
            <button class="px-2 py-0.5 text-[10px] bg-white border border-slate-300 hover:bg-sky-50 text-sky-700 rounded font-mono" onclick="jumpToCode('rtl', ${gap.rtl_line})">
              RTL L${gap.rtl_line}
            </button>
          ` : ''}
          ${gap.tb_line ? `
            <button class="px-2 py-0.5 text-[10px] bg-white border border-slate-300 hover:bg-emerald-50 text-emerald-700 rounded font-mono" onclick="jumpToCode('tb', ${gap.tb_line})">
              TB L${gap.tb_line}
            </button>
          ` : ''}
        </div>
      </div>

      <p class="text-xs text-slate-700">${escapeHtml(gap.description)}</p>

      <div class="text-[11px] bg-white p-2 rounded border border-slate-200 text-slate-600 font-mono">
        <span class="font-bold font-sans text-slate-700">Evidence:</span> ${escapeHtml(gap.evidence)}
      </div>

      <div class="text-xs text-indigo-950 font-medium">
        💡 <span class="font-semibold">Suggested Action:</span> ${escapeHtml(gap.suggested_action)}
      </div>
    `;
    container.appendChild(card);
  });

  document.getElementById("gapSeverityFilter").onchange = () => renderGapsList(state.report.gaps);
}

function renderCoverageBreakdown(sum) {
  const container = document.getElementById("coverageBarsList");
  container.innerHTML = "";

  const items = [
    { name: "Executable Line Coverage", val: sum.line_cov },
    { name: "Branch Coverage", val: sum.branch_cov },
  ];
  if (sum.cond_cov !== null && sum.cond_cov !== undefined) {
    items.push({ name: "Condition Coverage", val: sum.cond_cov });
  } else {
    items.push({ name: "Condition Coverage", val: null, naLabel: "N/A (No condition terms — excluded from score)" });
  }
  items.push({ name: "Toggle Stimulus Coverage", val: sum.toggle_cov });
  if (sum.fsm_cov !== null && sum.fsm_cov !== undefined) {
    items.push({ name: "FSM State & Transition Coverage", val: sum.fsm_cov });
  }

  items.forEach(it => {
    const bar = document.createElement("div");
    bar.className = "space-y-1";
    if (it.val !== null) {
      bar.innerHTML = `
        <div class="flex justify-between text-xs font-semibold text-slate-700">
          <span>${it.name}</span>
          <span class="font-mono">${it.val}%</span>
        </div>
        <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
          <div class="h-2 rounded-full ${it.val >= 80 ? 'bg-emerald-500' : (it.val >= 50 ? 'bg-amber-500' : 'bg-rose-500')}" style="width: ${it.val}%"></div>
        </div>
      `;
    } else {
      bar.innerHTML = `
        <div class="flex justify-between text-xs font-semibold text-slate-500">
          <span>${it.name}</span>
          <span class="font-mono text-[10px] text-slate-400 font-medium">${it.naLabel || 'N/A'}</span>
        </div>
        <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
          <div class="h-2 rounded-full bg-slate-200" style="width: 0%"></div>
        </div>
      `;
    }
    container.appendChild(bar);
  });
}

function renderLogs(logs) {
  const container = document.getElementById("logsContainer");
  document.getElementById("logsCountBadge").textContent = `${logs.length} entries`;
  container.innerHTML = "";

  logs.forEach(l => {
    const lvlColor = l.level === "SUCCESS" ? "text-emerald-400" : (l.level === "WARN" ? "text-amber-400" : (l.level === "ERROR" ? "text-rose-400" : "text-sky-400"));
    const row = document.createElement("div");
    row.innerHTML = `
      <span class="text-slate-500">[${l.timestamp}]</span>
      <span class="font-bold ${lvlColor}">[${l.stage}]</span>
      <span>${l.message}</span>
    `;
    container.appendChild(row);
  });
}

function renderHierarchyTree(modules, hierarchy) {
  const tree = document.getElementById("moduleHierarchyTree");
  tree.innerHTML = "";

  // 1. If hierarchical design tree is available, render visual instance hierarchy
  if (hierarchy) {
    const treeCard = document.createElement("div");
    treeCard.className = "border border-slate-200 rounded p-4 bg-slate-50 space-y-3 mb-6";
    treeCard.innerHTML = `
      <div class="flex items-center justify-between border-b border-slate-200 pb-2">
        <h4 class="font-bold text-xs text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <span>Hierarchy Tree Visualization</span>
          <span class="badge-covered text-[10px]">Top: ${escapeHtml(hierarchy.module_name)}</span>
        </h4>
        <span class="text-[11px] text-slate-500 font-mono">${modules.length} Module(s) in Design</span>
      </div>
      <div id="hierarchyTreeNodes" class="space-y-2 font-mono text-xs pt-1"></div>
    `;
    tree.appendChild(treeCard);

    const nodesContainer = treeCard.querySelector("#hierarchyTreeNodes");
    function renderNode(node, depth = 0) {
      const nodeEl = document.createElement("div");
      nodeEl.className = "flex items-center gap-2 py-1 px-2 rounded hover:bg-white transition border border-transparent hover:border-slate-200";
      nodeEl.style.marginLeft = `${depth * 24}px`;
      nodeEl.innerHTML = `
        <span class="text-slate-400">${depth > 0 ? "├── " : "• "}</span>
        <span class="font-bold text-sky-700">${escapeHtml(node.module_name)}</span>
        ${node.instance_name ? `<span class="text-slate-500 text-[11px]">(${escapeHtml(node.instance_name)})</span>` : ""}
        ${node.is_top ? `<span class="px-1.5 py-0.2 bg-blue-100 text-blue-700 text-[9px] font-bold rounded">TOP</span>` : ""}
        ${node.file ? `<span class="text-slate-400 text-[10px] ml-auto font-sans">${escapeHtml(node.file)}</span>` : ""}
      `;
      nodesContainer.appendChild(nodeEl);
      if (node.children && node.children.length > 0) {
        node.children.forEach(child => renderNode(child, depth + 1));
      }
    }
    renderNode(hierarchy);
  }

  // 2. Module Definition Cards
  const header = document.createElement("h4");
  header.className = "text-xs font-bold text-slate-700 uppercase tracking-wider mb-2";
  header.textContent = "Parsed Module Definitions";
  tree.appendChild(header);

  modules.forEach(m => {
    const div = document.createElement("div");
    div.className = `border ${m.partial_analysis ? 'border-amber-300 bg-amber-50/30' : 'border-slate-200 bg-white'} rounded p-4 space-y-2 mb-3`;
    div.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="font-mono font-bold text-sm text-sky-700">module ${escapeHtml(m.name)}</span>
          ${m.is_top ? '<span class="px-1.5 py-0.2 bg-blue-100 text-blue-700 text-[9px] font-bold rounded">TOP</span>' : ''}
          ${m.partial_analysis ? `<span class="px-1.5 py-0.2 bg-amber-100 text-amber-800 text-[9px] font-bold rounded" title="${escapeHtml(m.partial_reason)}">PARTIAL</span>` : ''}
          <span class="text-slate-400 text-xs font-mono">Lines ${m.start_line}-${m.end_line}</span>
          ${m.filename ? `<span class="text-slate-400 text-xs font-sans">&bull; ${escapeHtml(m.filename)}</span>` : ''}
        </div>
        <span class="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono">${m.ports.length} Ports</span>
      </div>
      <div class="text-xs text-slate-600 grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100">
        <div>Procedural Blocks: <strong>${m.always_blocks.length}</strong></div>
        <div>Continuous Assigns: <strong>${m.continuous_assigns.length}</strong></div>
        <div>Branches: <strong>${m.branches.length}</strong></div>
        <div>Conditions: <strong>${m.conditions.length}</strong></div>
      </div>
      ${m.partial_analysis ? `<div class="text-[11px] text-amber-700 bg-amber-100/60 p-2 rounded font-mono mt-2">${escapeHtml(m.partial_reason)}</div>` : ''}
    `;
    tree.appendChild(div);
  });
}

// -------------------------------------------------------------
// Code Viewer with Monaco & Resilient Fallback
// -------------------------------------------------------------
function setupCodeViewers(rtlCode, tbCode, rtlFile, tbFile) {
  document.getElementById("rtlViewerFilename").textContent = rtlFile;
  document.getElementById("tbViewerFilename").textContent = tbFile;

  const rtlContainer = document.getElementById("rtlEditorContainer");
  const tbContainer = document.getElementById("tbEditorContainer");

  if (state.useMonaco && window.monaco) {
    rtlContainer.innerHTML = "";
    tbContainer.innerHTML = "";

    state.monacoRtl = monaco.editor.create(rtlContainer, {
      value: rtlCode,
      language: 'verilog',
      theme: 'vs-light',
      readOnly: true,
      lineNumbers: 'on',
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: 12
    });

    state.monacoTb = monaco.editor.create(tbContainer, {
      value: tbCode,
      language: 'verilog',
      theme: 'vs-light',
      readOnly: true,
      lineNumbers: 'on',
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: 12
    });
  } else {
    // Fallback Line-numbered Viewer
    renderFallbackViewer(rtlContainer, rtlCode, "rtl");
    renderFallbackViewer(tbContainer, tbCode, "tb");
  }
}

function renderFallbackViewer(container, code, prefix) {
  container.innerHTML = "";
  const lines = code.split("\n");
  const wrapper = document.createElement("div");
  wrapper.className = "code-viewer-container";

  const gutter = document.createElement("div");
  gutter.className = "code-gutter";

  const content = document.createElement("div");
  content.className = "code-content";

  lines.forEach((line, i) => {
    const lineNum = i + 1;
    const gLine = document.createElement("div");
    gLine.textContent = lineNum;
    gutter.appendChild(gLine);

    const cLine = document.createElement("div");
    cLine.id = `${prefix}-line-${lineNum}`;
    cLine.className = "code-line";
    cLine.textContent = line || " ";
    content.appendChild(cLine);
  });

  wrapper.appendChild(gutter);
  wrapper.appendChild(content);
  container.appendChild(wrapper);
}

function jumpToCode(fileType, line) {
  switchTab(fileType === "rtl" ? "rtl" : "testbench");

  setTimeout(() => {
    if (fileType === "rtl") {
      if (state.monacoRtl) {
        state.monacoRtl.revealLineInCenter(line);
        state.monacoRtl.setPosition({ lineNumber: line, column: 1 });
      } else {
        const el = document.getElementById(`rtl-line-${line}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add("highlight-target");
          setTimeout(() => el.classList.remove("highlight-target"), 2500);
        }
      }
    } else {
      if (state.monacoTb) {
        state.monacoTb.revealLineInCenter(line);
        state.monacoTb.setPosition({ lineNumber: line, column: 1 });
      } else {
        const el = document.getElementById(`tb-line-${line}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add("highlight-target");
          setTimeout(() => el.classList.remove("highlight-target"), 2500);
        }
      }
    }
  }, 100);
}

// -------------------------------------------------------------
// Navigation & Tab Switching
// -------------------------------------------------------------
function setupNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  state.currentTab = tabId;

  // Update tabs active state
  document.querySelectorAll(".nav-tab").forEach(tab => {
    if (tab.getAttribute("data-tab") === tabId) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  // Toggle content sections
  document.querySelectorAll(".tab-content").forEach(c => {
    c.classList.add("hidden");
  });

  const activeContent = document.getElementById(`tab-${tabId}`);
  if (activeContent) {
    activeContent.classList.remove("hidden");
  }

  // Monaco layout refresh on tab switch
  if (tabId === "rtl" && state.monacoRtl) {
    setTimeout(() => state.monacoRtl.layout(), 50);
  } else if (tabId === "testbench" && state.monacoTb) {
    setTimeout(() => state.monacoTb.layout(), 50);
  }
}

// -------------------------------------------------------------
// Export Handlers
// -------------------------------------------------------------
function setupExportHandlers() {
  document.getElementById("btnExportHtml").addEventListener("click", async () => {
    if (!state.report) return;
    try {
      const res = await fetch("/api/export/html", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rtl_content: state.rtlContent,
          tb_content: state.tbContent,
          rtl_filename: state.rtlFilename,
          tb_filename: state.tbFilename
        })
      });
      const blob = await res.blob();
      downloadBlob(blob, `URG_Report_${state.report.design_name}.html`);
    } catch (e) {
      alert("Export HTML failed: " + e.message);
    }
  });

  document.getElementById("btnExportJson").addEventListener("click", async () => {
    if (!state.report) return;
    try {
      const res = await fetch("/api/export/json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rtl_content: state.rtlContent,
          tb_content: state.tbContent,
          rtl_filename: state.rtlFilename,
          tb_filename: state.tbFilename
        })
      });
      const blob = await res.blob();
      downloadBlob(blob, `URG_Report_${state.report.design_name}.json`);
    } catch (e) {
      alert("Export JSON failed: " + e.message);
    }
  });

  document.getElementById("btnExportPdf").addEventListener("click", () => {
    window.print();
  });
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
}

// -------------------------------------------------------------
// Before / After Comparison Banner Logic
// -------------------------------------------------------------
function renderBeforeAfterBanner(ba) {
  const banner = document.getElementById("beforeAfterBanner");
  if (!banner) return;
  if (!ba || !ba.has_previous) {
    banner.classList.add("hidden");
    return;
  }

  banner.classList.remove("hidden");
  const deltaScore = ba.score_delta;
  const sign = deltaScore >= 0 ? "+" : "";
  const scoreBadge = document.getElementById("diffScoreBadge");
  scoreBadge.textContent = `${sign}${deltaScore}%`;
  scoreBadge.className = deltaScore >= 0 
    ? "px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30"
    : "px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-400/30";

  document.getElementById("diffDetailsText").textContent = 
    `Score: ${ba.score_before}% → ${ba.score_after}% (${sign}${deltaScore}%) • Baseline: ${ba.previous_timestamp || 'Run 1'}`;

  const formatDelta = (val) => {
    if (val === null || val === undefined) return "N/A";
    const s = val >= 0 ? `+${val}%` : `${val}%`;
    const c = val > 0 ? "text-emerald-400" : (val < 0 ? "text-rose-400" : "text-slate-300");
    return `<span class="${c}">${s}</span>`;
  };

  document.getElementById("diffDeltaScore").innerHTML = formatDelta(ba.score_delta);
  document.getElementById("diffDeltaLine").innerHTML = formatDelta(ba.line_delta);
  document.getElementById("diffDeltaCond").innerHTML = formatDelta(ba.cond_delta);
  document.getElementById("diffDeltaToggle").innerHTML = formatDelta(ba.toggle_delta);
  document.getElementById("diffDeltaFsm").innerHTML = formatDelta(ba.fsm_delta);
  document.getElementById("diffDeltaBranch").innerHTML = formatDelta(ba.branch_delta);

  const gapsContainer = document.getElementById("diffGapsContainer");
  gapsContainer.innerHTML = "";

  if (ba.resolved_gaps && ba.resolved_gaps.length > 0) {
    ba.resolved_gaps.forEach(g => {
      const chip = document.createElement("span");
      chip.className = "px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-[11px] font-medium flex items-center gap-1";
      chip.innerHTML = `✓ <strong>RESOLVED:</strong> ${escapeHtml(g)}`;
      gapsContainer.appendChild(chip);
    });
  }

  if (ba.remaining_gaps && ba.remaining_gaps.length > 0) {
    ba.remaining_gaps.forEach(g => {
      const chip = document.createElement("span");
      chip.className = "px-2 py-0.5 rounded bg-amber-950/70 border border-amber-500/40 text-amber-300 text-[11px] font-medium flex items-center gap-1";
      chip.innerHTML = `⚠ <strong>REMAINING:</strong> ${escapeHtml(g)}`;
      gapsContainer.appendChild(chip);
    });
  }

  if (ba.new_gaps && ba.new_gaps.length > 0) {
    ba.new_gaps.forEach(g => {
      const chip = document.createElement("span");
      chip.className = "px-2 py-0.5 rounded bg-rose-950/80 border border-rose-500/50 text-rose-300 text-[11px] font-medium flex items-center gap-1";
      chip.innerHTML = `+ <strong>NEW:</strong> ${escapeHtml(g)}`;
      gapsContainer.appendChild(chip);
    });
  }
}

function setupBeforeAfterHandlers() {
  const btnReset = document.getElementById("btnResetBaseline");
  if (btnReset) {
    btnReset.addEventListener("click", async () => {
      try {
        await fetch(`/api/session/reset?session_id=${encodeURIComponent(state.sessionId)}`, { method: "POST" });
        const banner = document.getElementById("beforeAfterBanner");
        if (banner) banner.classList.add("hidden");
        showToast("Comparison baseline reset! Next analysis will establish a fresh baseline.");
      } catch (e) {
        console.error("Failed to reset baseline", e);
      }
    });
  }
}

// -------------------------------------------------------------
// [ WHY? ] Signature Modal Drawer Handlers
// -------------------------------------------------------------
function setupWhyModal() {
  const modal = document.getElementById("whyModal");
  const btnClose = document.getElementById("btnCloseWhyModal");
  const btnCloseBottom = document.getElementById("btnWhyCloseBottom");
  const btnCopy = document.getElementById("btnCopyStimulus");
  const btnInsert = document.getElementById("btnInsertStimulus");
  const btnJump = document.getElementById("btnWhyJumpCode");

  [btnClose, btnCloseBottom].forEach(b => {
    if (b) b.addEventListener("click", closeWhyModal);
  });

  // Close on clicking backdrop outside drawer
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeWhyModal();
  });

  // Copy stimulus snippet
  if (btnCopy) {
    btnCopy.addEventListener("click", () => {
      const snippet = document.getElementById("whySnippet").textContent;
      if (snippet) {
        navigator.clipboard.writeText(snippet).then(() => {
          const txt = document.getElementById("copyStimulusText");
          const orig = txt.textContent;
          txt.textContent = "✓ Copied!";
          setTimeout(() => { txt.textContent = orig; }, 2000);
          showToast("Stimulus snippet copied to clipboard!");
        });
      }
    });
  }

  // Insert stimulus snippet into TB editor
  if (btnInsert) {
    btnInsert.addEventListener("click", () => {
      const snippet = document.getElementById("whySnippet").textContent;
      if (snippet && snippet !== "// No stimulus snippet required") {
        insertStimulusIntoTb(snippet);
      }
    });
  }

  // Jump to RTL
  if (btnJump) {
    btnJump.addEventListener("click", () => {
      if (state.activeFinding && state.activeFinding.rtl_line) {
        jumpToCode("rtl", state.activeFinding.rtl_line);
        closeWhyModal();
      }
    });
  }

  // Escape key closes modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeWhyModal();
    }
  });
}

function openWhyModal(findingId) {
  if (!findingId) return;
  let finding = null;
  if (state.report && state.report.findings) {
    finding = state.report.findings.find(f => f.id === findingId);
  }
  if (!finding) return;

  state.activeFinding = finding;

  document.getElementById("whyFindingId").textContent = finding.id;
  document.getElementById("whyTitle").textContent = finding.title;
  document.getElementById("whyDescription").textContent = finding.description;

  // Badges
  const sevBadge = document.getElementById("whySeverityBadge");
  sevBadge.textContent = `${finding.severity} SEVERITY`;
  sevBadge.className = finding.severity === "HIGH" 
    ? "px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300"
    : (finding.severity === "MEDIUM" 
        ? "px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300"
        : "px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-800 border border-slate-300");

  const confBadge = document.getElementById("whyConfidenceBadge");
  confBadge.textContent = `${finding.confidence} CONFIDENCE`;
  confBadge.className = finding.confidence === "HIGH"
    ? "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300"
    : (finding.confidence === "MEDIUM"
        ? "px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300"
        : "px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300");

  document.getElementById("whyCategoryBadge").textContent = finding.category;
  document.getElementById("whyCodeLocBadge").textContent = `${finding.rtl_file}:L${finding.rtl_line}`;

  // Evidence
  document.getElementById("whyTbEvidenceStatus").textContent = finding.tb_evidence_status;
  document.getElementById("whyTbEvidenceDetails").textContent = finding.tb_evidence_details;

  // Dataflow chain breadcrumbs
  const dfContainer = document.getElementById("whyDataflowBreadcrumbs");
  dfContainer.innerHTML = "";
  if (finding.dataflow_chain && finding.dataflow_chain.length > 0) {
    document.getElementById("whyDataflowSection").classList.remove("hidden");
    finding.dataflow_chain.forEach((crumb, idx) => {
      if (idx > 0) {
        const arr = document.createElement("span");
        arr.className = "dataflow-arrow";
        arr.textContent = "→";
        dfContainer.appendChild(arr);
      }
      const cSpan = document.createElement("span");
      let typeClass = "dataflow-crumb";
      if (idx === 0) typeClass += " input";
      else if (idx === finding.dataflow_chain.length - 1) typeClass += " output";
      else if (crumb.includes(">=") || crumb.includes("==") || crumb.includes("<=")) typeClass += " compare";
      else typeClass += " counter";
      cSpan.className = typeClass;
      cSpan.textContent = crumb;
      dfContainer.appendChild(cSpan);
    });
  } else {
    document.getElementById("whyDataflowSection").classList.add("hidden");
  }

  // Reasoning & Next Scenario
  document.getElementById("whyReasoning").textContent = finding.reasoning;
  document.getElementById("whyNextScenario").textContent = finding.suggested_next_scenario;

  // Snippet
  document.getElementById("whySnippet").textContent = finding.suggested_stimulus_snippet || "// No stimulus snippet required";

  // Display modal
  document.getElementById("whyModal").classList.remove("hidden");
}

function closeWhyModal() {
  const modal = document.getElementById("whyModal");
  if (modal) modal.classList.add("hidden");
}

function insertStimulusIntoTb(snippet) {
  if (!snippet) return;
  const tbTextarea = document.getElementById("tbTextarea");
  let currentVal = tbTextarea.value;

  // If there's an endmodule, insert right before endmodule
  const endmoduleIdx = currentVal.lastIndexOf("endmodule");
  if (endmoduleIdx !== -1) {
    const before = currentVal.substring(0, endmoduleIdx).trimEnd();
    const after = currentVal.substring(endmoduleIdx);
    tbTextarea.value = before + "\n\n    // --- Inserted by URG Stimulus Assistant ---\n" + snippet + "\n\n" + after;
  } else {
    tbTextarea.value = currentVal + "\n\n    // --- Inserted by URG Stimulus Assistant ---\n" + snippet + "\n";
  }

  tbTextarea.dispatchEvent(new Event("input"));
  closeWhyModal();

  showToast("Stimulus snippet inserted into Testbench Notepad!");
}

// -------------------------------------------------------------
// Methodology Modal Handlers
// -------------------------------------------------------------
function setupMethodologyModal() {
  const modal = document.getElementById("methodologyModal");
  const btnOpen = document.getElementById("btnMethodology");
  const btnClose = document.getElementById("btnCloseMethodology");
  const btnCloseBottom = document.getElementById("btnCloseMethodologyBottom");

  if (btnOpen) {
    btnOpen.addEventListener("click", () => {
      modal.classList.remove("hidden");
    });
  }

  [btnClose, btnCloseBottom].forEach(b => {
    if (b) {
      b.addEventListener("click", () => {
        modal.classList.add("hidden");
      });
    }
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
}

// -------------------------------------------------------------
// Toast Notification
// -------------------------------------------------------------
function showToast(msg) {
  let toast = document.getElementById("urgToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "urgToast";
    toast.className = "fixed bottom-5 right-5 z-50 bg-slate-900 text-white border border-slate-700 px-4 py-2.5 rounded-lg shadow-2xl text-xs flex items-center gap-2.5 transition-all duration-300";
    document.body.appendChild(toast);
  }
  toast.innerHTML = `
    <span class="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">✓</span>
    <span>${escapeHtml(msg)}</span>
  `;
  toast.style.opacity = "1";
  toast.style.transform = "translateY(0)";

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
  }, 2800);
}

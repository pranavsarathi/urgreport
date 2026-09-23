"""
End-to-End API Integration Tests for URG Report FastAPI service.
"""

import pytest
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["tool"] == "URG REPORT FOR RTL CODE"


def test_get_examples():
    res = client.get("/api/examples")
    assert res.status_code == 200
    examples = res.json()
    assert len(examples) >= 3
    ids = [e["id"] for e in examples]
    assert "alu_8bit" in ids
    assert "counter_4bit" in ids
    assert "fsm_traffic" in ids


def test_get_example_code():
    res = client.get("/api/examples/alu_8bit")
    assert res.status_code == 200
    data = res.json()
    assert "module alu_8bit" in data["rtl_content"]
    assert "alu_8bit_tb" in data["tb_content"]


def test_analyze_payload():
    ex = client.get("/api/examples/alu_8bit").json()
    payload = {
        "rtl_content": ex["rtl_content"],
        "tb_content": ex["tb_content"],
        "rtl_filename": ex["rtl_filename"],
        "tb_filename": ex["tb_filename"]
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    report = res.json()
    assert report["design_name"] == "alu_8bit"
    assert report["total_summary"]["score"] is not None
    assert report["total_summary"]["fsm_cov"] is None  # FSM should be N/A for ALU
    assert len(report["gaps"]) > 0
    assert any("overflow" in g["title"] for g in report["gaps"])


def test_export_html_and_json_api():
    ex = client.get("/api/examples/alu_8bit").json()
    payload = {
        "rtl_content": ex["rtl_content"],
        "tb_content": ex["tb_content"],
        "rtl_filename": ex["rtl_filename"],
        "tb_filename": ex["tb_filename"]
    }
    # HTML Export
    res_html = client.post("/api/export/html", json=payload)
    assert res_html.status_code == 200
    assert "URG REPORT FOR RTL CODE" in res_html.text

    # JSON Export
    res_json = client.post("/api/export/json", json=payload)
    assert res_json.status_code == 200
    assert res_json.json()["design_name"] == "alu_8bit"


def test_serve_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "URG REPORT FOR RTL CODE" in res.text


def test_get_example_multi_file():
    res = client.get("/api/examples/pipeline_datapath")
    assert res.status_code == 200
    data = res.json()
    assert data["multi_file"] is True
    assert "files" in data
    assert len(data["files"]) == 4


def test_analyze_multi_file_api():
    ex = client.get("/api/examples/pipeline_datapath").json()
    payload = {
        "files": ex["files"],
        "tb_content": ex["tb_content"],
        "tb_filename": ex["tb_filename"]
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    report = res.json()
    assert report["design_name"] == "pipeline_top"
    assert report["top_module"] == "pipeline_top"
    assert len(report["modules"]) == 4
    assert report["hierarchy"] is not None


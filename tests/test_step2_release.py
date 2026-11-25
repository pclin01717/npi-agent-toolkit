import hashlib
import json
import re

import cadquery as cq
import pdfplumber
import pytest

from npi import pipeline
from npi.errors import NpiError
from npi.readers.ours import read_bom, read_spec_doc
from npi.stations import release

from conftest import (A0_SPEC, B0_ECR, INPUT_ROOT, FakeStation, fixture_of,
                      run_real, write_judgement)

NPI = "NPI-26-097"


def a0_until_release(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")


def render_a0(out_root, judgement=None):
    a0_until_release(out_root)
    write_judgement(out_root, NPI, "A0", "release", judgement or fixture_of("A0", "release"))
    return pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)


def check_a0(out_root, judgement):
    a0_until_release(out_root)
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), "A0", "release", INPUT_ROOT, out_root, "2026-11-02")
    facts = json.loads((ctx.station_dir / "facts.json").read_text(encoding="utf-8"))
    return release.check(ctx, facts, judgement)


EXPECTED_A0 = ["LPC-PS-26097_RevA0_Product_Specification.docx", "LPC-BOM-26097_RevA0_BOM.xlsx",
               "LPC-DWG-26097_RevA0_Fiber_Array_Drawing.pdf", "LPC-FA24-110_RevA0.step",
               "LPC-FA24-127-8A_RevA0.step"]


# STEP2-1
def test_STEP2_1_release_writes_five_files(out_root):
    files = render_a0(out_root)
    assert len(files) == 5 and all(f.exists() for f in files)


def test_STEP2_1_file_names_follow_input_pattern(out_root):
    files = render_a0(out_root)
    assert sorted(f.name for f in files) == sorted(EXPECTED_A0)


# STEP2-2
def test_STEP2_2_prepare_refused_without_decisions(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    with pytest.raises(NpiError, match="客戶決定"):
        pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root)


def test_STEP2_2_decide_records_each_item(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "R-03 接受; R-15 不接受，維持原交期", out_root)
    facts = json.loads(pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root).read_text(encoding="utf-8"))
    assert "R-03 接受" in facts["decisions"] and "R-15 不接受" in facts["decisions"]


# STEP2-3
def _pdf_text(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def test_STEP2_3_key_params_same_in_spec_bom_drawing(out_root):
    files = {f.suffix: f for f in render_a0(out_root) if f.suffix != ".step"}
    spec = read_spec_doc(files[".docx"])["params"]
    bom_desc = read_bom(files[".xlsx"])[0]["description"]
    drawing = _pdf_text(files[".pdf"])
    assert (spec["channels"], spec["pitch_um"], spec["end_face_angle_deg"]) == (24, 127, 8)
    assert (spec["pigtail_mm"], spec["pigtail_tol_mm"]) == (800, 20)
    for text in (bom_desc, drawing):
        assert "24 ch" in text and "127 µm" in text and "8°" in text and "800 ± 20 mm" in text


def test_STEP2_3_inconsistent_key_param_rejected(out_root):
    j = fixture_of("A0", "release")
    j["spec_sections"].append({"title": "Note", "text": "The array has 32 channels.", "sources": []})
    assert any("關鍵參數" in e and "32" in e for e in check_a0(out_root, j))


# STEP2-4
def test_STEP2_4_bom_top_level_part_number(out_root):
    bom = next(f for f in render_a0(out_root) if f.suffix == ".xlsx")
    assert read_bom(bom)[0]["part_no"] == "LPC-FA24-127-8A"


def test_STEP2_4_material_not_in_mm002_flagged(out_root):
    j = fixture_of("A0", "release")
    j["bom"].append({"item": "70", "part_no": "RM-XX-NOTEXIST", "description": "Unknown part",
                     "make_buy": "Buy", "qty_per": 1, "uom": "pcs", "sources": ["R-01"],
                     "op": "110", "category": "待工程師填寫"})      # 第 3 批：補工序和類別（使用者 2026-11-01 同意）
    bom = next(f for f in render_a0(out_root, j) if f.suffix == ".xlsx")
    row = next(r for r in read_bom(bom) if r["part_no"] == "RM-XX-NOTEXIST")
    assert "LPC-MM-002" in row["remark"]


# STEP2-5
def test_STEP2_5_drawing_pdf_has_views_title_block_channel_table(out_root):
    pdf = next(f for f in render_a0(out_root) if f.suffix == ".pdf")
    text = _pdf_text(pdf)
    assert "FRONT VIEW" in text and "SIDE VIEW" in text
    assert "LPC-DWG-26097" in text and "REV A0" in text
    assert {int(n) for n in re.findall(r"\bCH (\d+)\b", text)} == set(range(1, 25))


# STEP2-6
def test_STEP2_6_block_step_bounding_box_matches_spec(out_root):
    files = render_a0(out_root)
    step = next(f for f in files if f.name == "LPC-FA24-110_RevA0.step")
    spec = read_spec_doc(next(f for f in files if f.suffix == ".docx"))["params"]
    bb = cq.importers.importStep(str(step)).val().BoundingBox()
    assert bb.xlen == pytest.approx(spec["substrate_w_mm"], abs=0.01)
    assert bb.ylen == pytest.approx(spec["substrate_l_mm"], abs=0.01)
    assert bb.zlen == pytest.approx(spec["substrate_t_mm"] + spec["lid_t_mm"], abs=0.01)


# STEP2-7
@pytest.fixture
def b0_ready(out_root, monkeypatch):
    from npi import stations
    monkeypatch.setitem(stations.REGISTRY, "cost", FakeStation)
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release"):
        run_real(out_root, "A0", st)
    pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root)
    write_judgement(out_root, NPI, "A0", "cost", {})
    pipeline.render(NPI, "A0", "cost", INPUT_ROOT, out_root)
    pipeline.approve(NPI, "A0", "cost", INPUT_ROOT, out_root)
    pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    run_real(out_root, "B0", "dfm")
    pipeline.decide(NPI, "B0", "CH1～CH4 全部接受", out_root)
    pipeline.prepare(NPI, "B0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    return out_root


def _reviewed(out_root, rev):
    return json.loads((out_root / NPI / rev / "release" / "reviewed.json").read_text(encoding="utf-8"))


def test_STEP2_7_b0_rev_channels_connector(b0_ready):
    write_judgement(b0_ready, NPI, "B0", "release", fixture_of("B0", "release"))
    files = pipeline.render(NPI, "B0", "release", INPUT_ROOT, b0_ready)
    assert "LPC-PS-26097_RevB0_Product_Specification.docx" in [f.name for f in files]
    spec = read_spec_doc(next(f for f in files if f.suffix == ".docx"))
    assert spec["rev"] == "B0"
    assert spec["params"]["channels"] == 32
    assert "MPO-16" in spec["params"]["connector"]


def test_STEP2_7_fields_not_in_ecr_unchanged(b0_ready):
    j = fixture_of("B0", "release")
    write_judgement(b0_ready, NPI, "B0", "release", j)
    pipeline.render(NPI, "B0", "release", INPUT_ROOT, b0_ready)
    pipeline.approve(NPI, "B0", "release", INPUT_ROOT, b0_ready)
    a0, b0 = _reviewed(b0_ready, "A0")["params"], _reviewed(b0_ready, "B0")["params"]
    for key in a0:
        if key not in j["changes"]:
            assert a0[key] == b0[key], key


def test_STEP2_7_unrelated_field_change_rejected(b0_ready):
    j = fixture_of("B0", "release")
    j["params"]["pigtail_mm"] = {"value": 500, "sources": ["CH1"]}
    ctx = pipeline._ctx(pipeline.load_state(NPI, b0_ready), "B0", "release", INPUT_ROOT, b0_ready, "2026-11-02")
    facts = json.loads((ctx.station_dir / "facts.json").read_text(encoding="utf-8"))
    assert any("pigtail_mm" in e and "CH" in e for e in release.check(ctx, facts, j))


# STEP2-8
def test_STEP2_8_previous_rev_files_unchanged(b0_ready):
    a0_dir = b0_ready / NPI / "A0" / "release"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in a0_dir.iterdir()}
    write_judgement(b0_ready, NPI, "B0", "release", fixture_of("B0", "release"))
    pipeline.render(NPI, "B0", "release", INPUT_ROOT, b0_ready)
    pipeline.approve(NPI, "B0", "release", INPUT_ROOT, b0_ready)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in a0_dir.iterdir()}
    assert before == after

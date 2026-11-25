import json
import re

import cadquery as cq
import docx
import openpyxl
import pdfplumber
import pytest

from npi import params as P
from npi import pipeline
from npi.compare import diff_release
from npi.errors import NpiError
from npi.readers.ours import read_bom, read_spec_doc
from npi.stations import release

from conftest import (CVN_A0_SPEC, CVN_B0_ECR, INPUT_ROOT, KALVARA_FIXTURES, fixture_of, run_real,
                      write_judgement)
from test_step6_full_chain import NPI as KALVARA_NPI, run_kalvara

NPI = "NPI-26-104"
GOLDEN = KALVARA_FIXTURES / "batch1_golden.json"
EXPECTED_A0 = ["LPC-PS-26104_RevA0_Product_Specification.docx", "LPC-BOM-26104_RevA0_BOM.xlsx",
               "LPC-DWG-26104_RevA0_Fanout_Drawing.pdf", "LPC-FO36-110_RevA0.step",
               "LPC-FO36-M12-LCS_RevA0.step"]
FANOUT_ROWS = ["Fibre count", "Trunk connectors", "Leg connectors", "End face", "Polarity", "Trunk length",
               "Leg length (mm)", "Trunk / leg cable OD (mm)", "Fan-out box L x W x H (mm)"]


def a0_fixture():
    return fixture_of("A0", "release", NPI)


def until_release(out_root):
    pipeline.intake(CVN_A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", npi=NPI)
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")


def render_a0(out_root, judgement=None):
    until_release(out_root)
    write_judgement(out_root, NPI, "A0", "release", judgement or a0_fixture())
    return {f.name: f for f in pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)}


def ctx_facts(out_root, rev):
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), rev, "release", INPUT_ROOT, out_root, "2026-11-02")
    return ctx, json.loads((ctx.station_dir / "facts.json").read_text(encoding="utf-8"))


def check_a0(out_root, judgement):
    until_release(out_root)
    return release.check(*ctx_facts(out_root, "A0"), judgement)


def until_b0_release(out_root):
    pipeline.intake(CVN_A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "A0", st, npi=NPI)
    pipeline.intake(CVN_B0_ECR, INPUT_ROOT, out_root)
    run_real(out_root, "B0", "dfm", npi=NPI)
    pipeline.decide(NPI, "B0", "全部接受", out_root)
    pipeline.prepare(NPI, "B0", "release", INPUT_ROOT, out_root, date="2026-11-02")


def check_b0(out_root, judgement):
    until_b0_release(out_root)
    return release.check(*ctx_facts(out_root, "B0"), judgement)


def docx_text(path):
    d = docx.Document(path)
    cells = [c.text for t in d.tables for r in t.rows for c in r.cells]
    return "\n".join([p.text for p in d.paragraphs] + cells)


def xlsx_text(path):
    wb = openpyxl.load_workbook(path)
    return "\n".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)


def pdf_text(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def three_texts(files):
    return {"spec": docx_text(files[EXPECTED_A0[0]]), "bom": xlsx_text(files[EXPECTED_A0[1]]),
            "drawing": pdf_text(files[EXPECTED_A0[2]])}


# STEP8-1
def test_STEP8_1_corvane_release_writes_five_files(out_root):
    files = render_a0(out_root)
    assert len(files) == 5 and all(f.exists() for f in files.values())


def test_STEP8_1_file_names_follow_input_pattern(out_root):
    assert sorted(render_a0(out_root)) == sorted(EXPECTED_A0)


def test_STEP8_1_fanout_needs_no_fiber_array_params(out_root):
    judgement = a0_fixture()
    assert not {"pitch_um", "substrate_w_mm", "lid_w_mm", "boot_w_mm"} & set(judgement["params"])
    assert check_a0(out_root, judgement) == []


# STEP8-2
def test_STEP8_2_spec_key_table_rows_are_fanout(out_root):
    files = render_a0(out_root)
    table = docx.Document(files[EXPECTED_A0[0]]).tables[1]
    labels = [r.cells[0].text.strip() for r in table.rows[1:]]
    assert labels == FANOUT_ROWS
    assert not any(w in " ".join(labels).lower() for w in ("pitch", "substrate", "lid"))


def test_STEP8_2_spec_key_values_from_customer_spec(out_root):
    files = render_a0(out_root)
    table = docx.Document(files[EXPECTED_A0[0]]).tables[1]
    rows = {r.cells[0].text.strip(): r.cells[1].text.strip() for r in table.rows[1:]}
    assert rows["Fibre count"] == "36"
    assert rows["Trunk connectors"] == "3 x MPO-12 APC female (unpinned), elite grade"
    assert rows["Leg connectors"] == "36 x LC/APC simplex"
    assert rows["Trunk length"] == "3.0 m +50 / 0 mm"
    assert rows["Leg length (mm)"] == "500 ± 20"
    assert rows["Fan-out box L x W x H (mm)"] == "62 x 20 x 10"


def test_STEP8_2_missing_fanout_param_rejected(out_root):
    judgement = a0_fixture()
    del judgement["params"]["box_h_mm"]
    assert any("box_h_mm" in e for e in check_a0(out_root, judgement))


# STEP8-3
def test_STEP8_3_tolerance_text_formats():
    assert P.tol_text(10, 10) == "± 10"
    assert P.tol_text(50, 0) == "+50 / 0"
    assert P.tol_text(50, 10) == "+50 / -10"


def test_STEP8_3_asymmetric_tolerance_in_spec_bom_drawing(out_root):
    for name, text in three_texts(render_a0(out_root)).items():
        assert "+50 / 0" in text, name
        assert not re.search(r"± 50\b|± 0(?![.\d])", text), name


def test_STEP8_3_spec_read_back_keeps_plus_and_minus(out_root):
    files = render_a0(out_root)
    got = read_spec_doc(files[EXPECTED_A0[0]])["params"]
    assert got["trunk_tol_plus_mm"] == 50 and got["trunk_tol_minus_mm"] == 0
    assert got == P.values(a0_fixture()["params"])


# STEP8-4
def test_STEP8_4_bom_item0_item10_names_are_fanout(out_root):
    files = render_a0(out_root)
    rows = {b["item"]: b for b in read_bom(files[EXPECTED_A0[1]])}
    assert "Fan-out" in rows["0"]["description"] and "36" in rows["0"]["description"]
    assert rows["10"]["description"] == "Fan-out box sub-assembly"
    assert rows["10"]["part_no"] == "LPC-FO36-110"


def test_STEP8_4_no_fibre_array_text_in_fanout_outputs(out_root):
    for name, text in three_texts(render_a0(out_root)).items():
        assert not re.search(r"fib(re|er) array", text, re.IGNORECASE), name


# STEP8-5
def test_STEP8_5_drawing_has_trunk_box_legs_and_dims(out_root):
    text = pdf_text(render_a0(out_root)[EXPECTED_A0[2]])
    for word in ("TRUNK", "FAN-OUT BOX", "LEGS", "NOT TO SCALE", "3.0 m +50 / 0 mm", "500 ± 20 mm", "62 x 20 x 10"):
        assert word in text, word


def test_STEP8_5_port_map_has_36_rows(out_root):
    text = pdf_text(render_a0(out_root)[EXPECTED_A0[2]])
    assert len(re.findall(r"\bF\d{2}\s+MPO \d+ / \d{2}\s+LEG \d{2}\b", text)) == 36


# STEP8-6
def test_STEP8_6_box_step_bounding_box_matches_spec(out_root):
    files = render_a0(out_root)
    bb = cq.importers.importStep(str(files["LPC-FO36-110_RevA0.step"])).val().BoundingBox()
    assert abs(bb.xlen - 20) < 0.01 and abs(bb.ylen - 62) < 0.01 and abs(bb.zlen - 10) < 0.01


# STEP8-7
def test_STEP8_7_unknown_product_type_rejected_names_type(out_root):
    judgement = a0_fixture()
    judgement["product_type"] = "Splitter"
    errors = check_a0(out_root, judgement)
    assert any("Splitter" in e and "不支援" in e for e in errors)


def test_STEP8_7_unknown_product_type_writes_no_files(out_root):
    judgement = a0_fixture()
    judgement["product_type"] = "Splitter"
    with pytest.raises(NpiError, match="Splitter"):
        render_a0(out_root, judgement)
    left = {p.name for p in (out_root / NPI / "A0" / "release").iterdir()}
    assert left == {"facts.json", "judgement.json"}


# STEP8-8
def test_STEP8_8_corvane_b0_changed_params_map_to_ch(out_root):
    assert check_b0(out_root, fixture_of("B0", "release", NPI)) == []


def test_STEP8_8_change_without_ch_rejected(out_root):
    judgement = fixture_of("B0", "release", NPI)
    del judgement["changes"]["leg_mm"]
    assert any("leg_mm" in e and "CH" in e for e in check_b0(out_root, judgement))


def test_STEP8_8_unmentioned_params_unchanged(out_root):
    until_b0_release(out_root)
    write_judgement(out_root, NPI, "B0", "release", fixture_of("B0", "release", NPI))
    pipeline.render(NPI, "B0", "release", INPUT_ROOT, out_root)
    pipeline.approve(NPI, "B0", "release", INPUT_ROOT, out_root)
    read = lambda rev: json.loads((out_root / NPI / rev / "release" / "reviewed.json").read_text(encoding="utf-8"))
    a0, b0 = read("A0")["params"], read("B0")["params"]
    for key in ("fibres", "trunk_conn_qty", "trunk_connector", "end_face", "polarity",
                "trunk_tol_plus_mm", "trunk_tol_minus_mm", "trunk_od_mm"):
        assert b0[key] == a0[key], key
    assert (b0["leg_conn_qty"], b0["leg_mm"], b0["trunk_m"]) == (18, 1000, 10)


# STEP8-9
def kalvara_snapshot(out_root):
    """Kalvara A0～C1 每站的 reviewed.json 和圖面 PDF 文字（PLANS P46）。"""
    run_kalvara(out_root)
    base = out_root / KALVARA_NPI
    snap = {}
    for p in sorted(base.rglob("reviewed.json")):
        snap[str(p.relative_to(base))] = json.loads(p.read_text(encoding="utf-8"))
    for p in sorted(base.rglob("*_Drawing.pdf")):
        snap[str(p.relative_to(base))] = pdf_text(p)
    return snap


# test_STEP8_9_kalvara_a0_to_c1_same_as_batch1 第 3 批起由 test_step12_rerun.py 的 STEP12-1 取代
# （VERIFY STEP12-1 排除 STEP8-9；使用者 2026-11-01 同意）


# 來自 PLANS
def test_PLANS_P36_product_type_needs_citation(out_root):
    judgement = a0_fixture()
    del judgement["product_type_sources"]
    assert any("product_type" in e for e in check_a0(out_root, judgement))
    judgement["product_type_sources"] = ["R-99"]
    assert any("R-99" in e for e in release.check(*ctx_facts(out_root, "A0"), judgement))


def test_PLANS_P36_ecr_cannot_change_product_type(out_root):
    judgement = fixture_of("B0", "release", NPI)
    judgement["product_type"] = "Fiber_Array"
    assert any("上一版" in e and "Fanout" in e for e in check_b0(out_root, judgement))


def test_PLANS_P39_port_map_method_a_and_b():
    v = {"fibres": 36, "trunk_conn_qty": 3, "leg_conn_qty": 36}
    b = P.port_map({**v, "polarity": "Method B"})
    a = P.port_map({**v, "polarity": "Method A"})
    assert len(a) == len(b) == 36
    assert b[0] == (1, 1, 1, 12) and a[0] == (1, 1, 1, 1)       # (芯號, MPO, 位置, 支線)
    assert b[12] == (13, 2, 1, 24) and a[12] == (13, 2, 1, 13)
    duplex_a = P.port_map({**v, "leg_conn_qty": 18, "polarity": "Method A"})
    duplex_b = P.port_map({**v, "leg_conn_qty": 18, "polarity": "Method B"})
    assert [r[3] for r in duplex_a[:3]] == [1, 1, 2]
    assert [r[3] for r in duplex_b[:3]] == [6, 6, 5]


def test_PLANS_P39_fibres_not_divisible_rejected(out_root):
    judgement = a0_fixture()
    judgement["params"]["trunk_conn_qty"] = {"value": 5, "sources": []}
    assert any("整除" in e for e in check_a0(out_root, judgement))


def test_PLANS_P35_approve_refuses_edited_fanout_param(out_root):
    files = render_a0(out_root)
    path = files[EXPECTED_A0[0]]
    d = docx.Document(path)
    for row in d.tables[1].rows:
        if row.cells[0].text.strip() == "Trunk length":
            row.cells[1].text = "3.5 m +50 / 0 mm"
    d.save(path)
    with pytest.raises(NpiError, match="trunk_m"):
        pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)


def test_PLANS_P44_compare_skips_fanout_params():
    reviewed = {"lpc_pn": "LPC-FO36-M12-LCS", "block_pn": "LPC-FO36-110", "product_type": "Fanout",
                "params": P.values(a0_fixture()["params"]), "bom": []}
    truth = {"project": {"lpc_pn": "LPC-FO36-M12-LCS", "block_pn": "LPC-FO36-110"},
             "geometry": {"n_ch": 24, "pitch": 0.127}, "bom": []}
    assert diff_release(reviewed, truth) == []

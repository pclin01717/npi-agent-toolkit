"""STEP 10 BOM 照內容深度規格 §5（第 3 批）。"""
import json

import openpyxl
import pytest
from pycel import ExcelCompiler

from npi import pipeline
from npi.errors import NpiError
from npi.sources import PENDING
from npi.stations import release

from conftest import CVN_A0_SPEC, INPUT_ROOT, KALVARA_FIXTURES, CORVANE_FIXTURES, fixture_of, run_real, write_judgement
from test_step6_full_chain import NPI, run_kalvara

HEADERS = ["Level", "Item No.", "Part No.", "Description", "Type", "Make/Buy", "Qty per Parent", "UoM",
           "Ext. Qty per pc", "Supplier", "Lead Time (days)", "Remark"]
TABLE_ROW = 8


def until_release(out_root, rev):
    run_kalvara(out_root, until=(rev, "release"))
    pipeline.decide(NPI, rev, "全部接受", out_root)
    pipeline.prepare(NPI, rev, "release", INPUT_ROOT, out_root, date="2026-11-02")


def render(out_root, rev, judgement=None):
    write_judgement(out_root, NPI, rev, "release", judgement or fixture_of(rev, "release"))
    files = pipeline.render(NPI, rev, "release", INPUT_ROOT, out_root)
    return next(f for f in files if f.name.endswith("_BOM.xlsx"))


def bom_of(out_root, rev, judgement=None):
    until_release(out_root, rev)
    return render(out_root, rev, judgement)


def check_of(out_root, rev, judgement):
    until_release(out_root, rev)
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), rev, "release", INPUT_ROOT, out_root, "2026-11-02")
    facts = json.loads((ctx.station_dir / "facts.json").read_text(encoding="utf-8"))
    return release.check(ctx, facts, judgement)


def table(ws):
    """表頭在第 8 列；回傳 [{表頭: 值}]，遇到空列就停。"""
    heads = [c.value for c in ws[TABLE_ROW]]
    rows = []
    for r in ws.iter_rows(min_row=TABLE_ROW + 1, values_only=True):
        if all(v is None for v in r):
            break
        rows.append({h: v for h, v in zip(heads, r) if h})
    return rows


def evaluate(path, ref):
    return ExcelCompiler(filename=str(path)).evaluate(ref)


def cell_of(ws, part_no, head):
    heads = [c.value for c in ws[TABLE_ROW]]
    for row in ws.iter_rows(min_row=TABLE_ROW + 1):
        if row[heads.index("Part No.")].value == part_no:
            return row[heads.index(head)]
    raise AssertionError(part_no)


# STEP10-1
def test_STEP10_1_a0_bom_has_four_sheets(out_root):
    wb = openpyxl.load_workbook(bom_of(out_root, "A0"))
    assert wb.sheetnames == ["BOM", "Channel Map", "Routing", "Revision"]


def test_STEP10_1_b0_bom_has_change_summary(out_root):
    wb = openpyxl.load_workbook(bom_of(out_root, "B0"))
    assert wb.sheetnames == ["Change Summary", "BOM", "Channel Map", "Routing", "Revision"]


# STEP10-2
def test_STEP10_2_level_from_item_number():
    assert [release.level_of(i) for i in ("0", "10", "10.10")] == [0, 1, 2]
    with pytest.raises(ValueError):
        release.level_of("10.10.10")


def test_STEP10_2_every_row_has_required_columns(out_root):
    ws = openpyxl.load_workbook(bom_of(out_root, "A0"))["BOM"]
    assert [c.value for c in ws[TABLE_ROW]][:len(HEADERS)] == HEADERS
    rows = table(ws)
    assert {r["Item No."] for r in rows} >= {"0", "10", "10.10", "60", "60.40"}
    for r in rows:
        for h in ("Level", "Item No.", "Part No.", "Description", "Type", "Make/Buy", "UoM"):
            assert r[h] not in (None, ""), (r["Item No."], h)
        if r["Item No."] != "0":
            assert str(r["Remark"]).startswith("Op "), r["Item No."]


def test_STEP10_2_blank_category_rejected(out_root):
    j = fixture_of("A0", "release")
    j["bom"].append({"item": "70", "part_no": "RM-XX-NOTEXIST", "description": "Unknown part", "make_buy": "Buy",
                     "qty_per": 1, "uom": "pcs", "op": "110", "sources": []})
    errors = check_of(out_root, "A0", j)
    assert any("RM-XX-NOTEXIST" in e and "類別" in e for e in errors)


# STEP10-3
def test_STEP10_3_category_from_mm002():
    c = release.category_of
    assert c("Buy", "Consumable - Optical Epoxy") == "RM"
    assert c("Buy", "Purchased Part - Protection") == "PKG"
    assert c("Buy", "Raw Material - V-Groove Substrate") == "RM"
    assert c("Buy", "Purchased Part - Connector") == "BUY"
    assert c("Buy", "Packaging") == "PKG"
    assert c("Buy", "Consumable - Polishing") == "CON"
    assert c("Make", None, children=["PKG", "PKG"]) == "PKG"
    assert c("Make", None, children=["RM", "BUY"]) == "MFG"
    assert c("Make", None) == "MFG"
    assert c("Buy", "New (ECR / NPI) material code") is None
    assert c("Buy", None) is None


def test_STEP10_3_new_material_code_needs_cited_category(out_root):
    j = fixture_of("A0", "release")
    row = {"item": "70", "part_no": "RM-XX-NOTEXIST", "description": "Unknown part", "make_buy": "Buy",
           "qty_per": 1, "uom": "pcs", "op": "110", "sources": [], "category": "RM"}
    j["bom"].append(row)
    assert any("RM-XX-NOTEXIST" in e and "類別" in e for e in check_of(out_root, "A0", j))   # 沒有出處
    row["category_sources"] = ["R-01"]
    assert not any("類別" in e for e in release.check(*_ctx_facts(out_root, "A0"), j))
    row["category"], row["category_sources"] = PENDING, []
    assert not any("類別" in e for e in release.check(*_ctx_facts(out_root, "A0"), j))


def _ctx_facts(out_root, rev):
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), rev, "release", INPUT_ROOT, out_root, "2026-11-02")
    return ctx, json.loads((ctx.station_dir / "facts.json").read_text(encoding="utf-8"))


# STEP10-4
def test_STEP10_4_extended_qty_formula(out_root):
    path = bom_of(out_root, "A0")
    wb = openpyxl.load_workbook(path)
    ws = wb["BOM"]
    ext = cell_of(ws, "PP-CAP-MPOF", "Ext. Qty per pc")
    assert str(ext.value).startswith("=")
    assert evaluate(path, f"BOM!{ext.coordinate}") == 2
    cell_of(ws, "LPC-FA24-PKG", "Qty per Parent").value = 2           # 上一階（item 60）用量改成 2
    wb.save(path)
    assert evaluate(path, f"BOM!{ext.coordinate}") == 4


# STEP10-5
def channel_rows(path):
    return table(openpyxl.load_workbook(path)["Channel Map"])


def test_STEP10_5_a0_channel_map_24_rows_ok(out_root):
    path = bom_of(out_root, "A0")
    rows = channel_rows(path)
    assert len(rows) == 24
    assert {"Channel", "MPO", "MPO Position", "Function", "Fibre Type"} <= set(rows[0])
    assert evaluate(path, release.CHANNEL_CHECK_CELL) == "OK"


def test_STEP10_5_missing_row_check_not_ok(out_root):
    j = fixture_of("A0", "release")
    j["channel_map"] = j["channel_map"][:-1]
    path = bom_of(out_root, "A0", j)
    assert len(channel_rows(path)) == 23
    assert evaluate(path, release.CHANNEL_CHECK_CELL) == "CHECK"


def test_STEP10_5_mpo_position_from_connector():
    assert release.fibres_per_mpo("2 x MPO-12 APC female (unpinned)") == 12
    assert release.fibres_per_mpo("2 x MPO-16 APC male (pinned), elite grade") == 16
    assert release.fibres_per_mpo("LC/APC") is None
    assert release.mpo_position(13, 12) == (2, 1)
    assert release.mpo_position(12, 12) == (1, 12)


# STEP10-6
def routing_rows(path):
    return table(openpyxl.load_workbook(path)["Routing"])


def test_STEP10_6_default_routing_run_time_pending(out_root):
    rows = routing_rows(bom_of(out_root, "A0"))
    assert [r["Work Centre"] for r in rows] == ["FPR", "VGA", "CUR", "POL", "EFI", "CPM", "VGA", "CON", "OPT", "PKG"]
    for r in rows:
        assert r["Setup (min / lot)"] == 20 and "RULES §4 整備時間" in r["Setup Basis"]
        assert r["Run (min / pc)"] == PENDING


def test_STEP10_6_base_sequence_required(out_root):
    j = fixture_of("A0", "release")
    j["routing"] = [o for o in j["routing"] if o["work_centre"] != "POL"]
    errors = check_of(out_root, "A0", j)
    assert any("基本工序" in e and "POL" in e for e in errors)


def test_STEP10_6_setup_must_be_20_unless_engineer(out_root):
    j = fixture_of("A0", "release")
    op = j["routing"][0]
    op["setup_min"] = {"value": 25, "sources": ["RULES §4 整備時間"]}
    assert any("整備時間" in e for e in check_of(out_root, "A0", j))
    pipeline.tell(NPI, "A0", "release", "Op 10 整備 25 分鐘", out_root)
    op["setup_min"] = {"value": 25, "sources": ["ENG-1"]}
    write_judgement(out_root, NPI, "A0", "release", j)
    pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)              # 通過
    op["setup_min"] = {"value": 35, "sources": ["ENG-1"]}
    write_judgement(out_root, NPI, "A0", "release", j)
    with pytest.raises(NpiError, match="10–30"):
        pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)


def test_STEP10_6_run_time_needs_source_or_pending(out_root):
    j = fixture_of("A0", "release")
    j["routing"][0]["run_min"] = {"value": 4, "sources": []}
    assert any("單件時間" in e for e in check_of(out_root, "A0", j))


# STEP10-7
def test_STEP10_7_pm_adds_two_pma_ops(out_root):
    j = fixture_of("B0", "release")
    j["routing"] = [o for o in j["routing"] if o["op"] != "85"]
    assert any("PMA" in e for e in check_of(out_root, "B0", j))


def test_STEP10_7_coating_needs_prebake_coating_incoming(out_root):
    j = fixture_of("C0", "release")
    for o in j["routing"]:
        if "incoming" in o["kinds"]:
            o["kinds"] = [k for k in o["kinds"] if k != "incoming"]
    errors = check_of(out_root, "C0", j)
    assert any("incoming" in e for e in errors)
    good = fixture_of("C0", "release")
    assert not [e for e in release.check(*_ctx_facts(out_root, "C0"), good) if "Routing" in e or "工序" in e]


def test_STEP10_7_unknown_work_centre_rejected(out_root):
    j = fixture_of("A0", "release")
    j["routing"][-1]["work_centre"] = "XYZ"
    assert any("XYZ" in e for e in check_of(out_root, "A0", j))


# STEP10-8
def test_STEP10_8_bom_op_must_exist_in_routing(out_root):
    j = fixture_of("A0", "release")
    j["bom"][0]["op"] = "999"
    assert any("999" in e for e in check_of(out_root, "A0", j))


# STEP10-9
def test_STEP10_9_change_summary_lists_bom_and_routing_diffs(out_root):
    rows = table(openpyxl.load_workbook(bom_of(out_root, "B0"))["Change Summary"])
    by_key = {(r["Change"], r["Part No. / Op."]): r for r in rows}
    assert by_key[("Removed", "LPC-FA24-110")]["CH"] == "CH1"
    assert by_key[("Added", "LPC-FA32-110")]["CH"] == "CH1"
    assert by_key[("Added", "RM-FB-PM1310")]["CH"] == "CH2"
    assert by_key[("Added", "Op 20")]["CH"] == "CH2"
    assert not any(k[1] in ("LPC-FA24-127-8A", "LPC-FA32-127-8B") for k in by_key)   # 成品料號換版不算變更項目


def test_STEP10_9_diff_without_ch_rejected(out_root):
    j = fixture_of("B0", "release")
    del j["change_map"]["RM-FB-PM1310"]
    assert any("RM-FB-PM1310" in e and "CH" in e for e in check_of(out_root, "B0", j))


# STEP10-10
def test_STEP10_10_revision_rows_carry_previous(out_root):
    rows = table(openpyxl.load_workbook(bom_of(out_root, "B0"))["Revision"])
    state = pipeline.load_state(NPI, out_root)
    dates = {r: next(s["date"] for s in state["revs"][r]["stations"] if s["name"] == "release") for r in ("A0", "B0")}
    assert [r["Rev."] for r in rows] == ["A0", "B0"]
    for r in rows:
        assert r["Date"] == dates[r["Rev."]]
        assert (r["Prepared"], r["Approved"]) == ("Alex Lin", "Jessica Liao")
        assert r["Zone"] and r["Description of Change"]
    assert "CH1" in rows[1]["Zone"]


# STEP10-11
def test_STEP10_11_tell_run_time_reaches_bom_and_cost(out_root):
    until_release(out_root, "A0")
    eng = pipeline.tell(NPI, "A0", "release", "Op 30 單件時間 11 分鐘", out_root)
    j = fixture_of("A0", "release")
    op30 = next(o for o in j["routing"] if o["op"] == "30")
    op30["run_min"] = {"value": 11, "sources": [eng]}
    path = render(out_root, "A0", j)
    assert next(r for r in routing_rows(path) if r["Op."] == "30")["Run (min / pc)"] == 11
    pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)
    facts = json.loads(pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root).read_text(encoding="utf-8"))
    assert next(o for o in facts["routing"] if o["op"] == "30")["run_min"] == 11


# 來自 PLANS
def test_PLANS_P61_fixture_parent_qty_is_one():
    for base in (KALVARA_FIXTURES, CORVANE_FIXTURES):
        for path in base.glob("*/release.json"):
            bom = json.loads(path.read_text(encoding="utf-8"))["bom"]
            qty = {b["item"]: b["qty_per"] for b in bom}
            qty["10"] = 1                                         # item 10 是程式自動加的（P26、P40）
            for b in bom:
                if release.level_of(b["item"]) == 2:
                    assert qty[b["item"].split(".")[0]] == 1, (path, b["item"])


def test_PLANS_P61_level2_without_parent_rejected(out_root):
    j = fixture_of("A0", "release")
    j["bom"] = [b for b in j["bom"] if b["item"] != "60"]
    assert any("60" in e and "上一階" in e for e in check_of(out_root, "A0", j))


def test_PLANS_P61_no_fau_in_bom_headers(out_root):
    wb = openpyxl.load_workbook(bom_of(out_root, "B0"))
    for ws in wb.worksheets:
        assert not any("FAU" in str(c.value) for c in ws[TABLE_ROW] if c.value), ws.title


def test_PLANS_P82_group_row_category(out_root):
    rows = {r["Item No."]: r for r in table(openpyxl.load_workbook(bom_of(out_root, "A0"))["BOM"])}
    assert (rows["60"]["Type"], rows["60"]["Make/Buy"]) == ("PKG", "Make")
    assert rows["10"]["Type"] == "MFG" and rows["60.40"]["Type"] == "PKG"


def test_PLANS_P65_fanout_channel_map_is_port_map(out_root):
    pipeline.intake(CVN_A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", npi="NPI-26-104")
    pipeline.decide("NPI-26-104", "A0", "全部接受", out_root)
    pipeline.prepare("NPI-26-104", "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, "NPI-26-104", "A0", "release", fixture_of("A0", "release", "NPI-26-104"))
    files = pipeline.render("NPI-26-104", "A0", "release", INPUT_ROOT, out_root)
    path = next(f for f in files if f.name.endswith("_BOM.xlsx"))
    rows = channel_rows(path)
    assert len(rows) == 36 and {"Fibre", "MPO", "MPO Position", "Leg"} <= set(rows[0])
    assert evaluate(path, release.CHANNEL_CHECK_CELL) == "OK"


def test_PLANS_P63_rel_not_in_routing(out_root):
    j = fixture_of("A0", "release")
    j["routing"].append({"op": "120", "description": "Lot qualification", "work_centre": "REL", "kinds": ["base"],
                         "setup_min": {"value": 20, "sources": ["RULES §4 整備時間"]}, "run_min": {"value": PENDING, "sources": []}})
    assert any("REL" in e for e in check_of(out_root, "A0", j))

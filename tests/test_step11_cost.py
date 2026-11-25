"""STEP 11 單位成本表照內容深度規格 §6、作業規則 §3（第 3 批）。"""
import json

import openpyxl
import pytest
from pycel import ExcelCompiler

from npi import costing, pipeline
from npi.errors import NpiError
from npi.readers.master import source_texts
from npi.readers.ours import read_cost
from npi.render import xlsx_out as X
from npi.sources import PENDING

from conftest import (A0_PO, CVN_A0_SPEC, INPUT_ROOT, fixture_of, write_judgement)
from test_step6_full_chain import CHAIN, NPI

RUN, QTY, SCRAP = 5, 0.1, 0.1


# ---- 測試資料：照工程師在對話裡給值的方式（PLANS P60、P83）把待填補上 ----
def filled_release(judgement, eng):
    for o in judgement["routing"]:
        if (o.get("run_min") or {}).get("value") == PENDING:
            o["run_min"] = {"value": RUN, "sources": [eng]}
    for b in judgement["bom"]:
        if b["qty_per"] == PENDING:
            b["qty_per"], b["sources"] = QTY, b.get("sources", []) + [eng]
    return judgement


def run_station(out_root, rev, station, fill=True, cost_override=None, npi=NPI):
    if station == "release":
        pipeline.decide(npi, rev, "全部接受", out_root)
    pipeline.prepare(npi, rev, station, INPUT_ROOT, out_root, date="2026-11-02")
    j = fixture_of(rev, station, npi)
    if fill and station == "release":
        j = filled_release(j, pipeline.tell(npi, rev, "release", f"測試用：單件時間 {RUN} 分鐘，待填用量 {QTY}", out_root))
    if fill and station == "cost" and npi == NPI:
        eng = pipeline.tell(npi, rev, "cost", f"測試用：報廢率 {SCRAP}", out_root)
        j["scrap_rate_override"] = {"value": SCRAP, "sources": [eng]}
    if cost_override:
        cost_override(j)
    write_judgement(out_root, npi, rev, station, j)
    files = pipeline.render(npi, rev, station, INPUT_ROOT, out_root)
    pipeline.approve(npi, rev, station, INPUT_ROOT, out_root)
    return files


def run_kalvara_filled(out_root, until=None, fill=True):
    for rev, doc, stations in CHAIN:
        pipeline.intake(doc, INPUT_ROOT, out_root)
        for st in stations:
            if until == (rev, st):
                return
            run_station(out_root, rev, st, fill=fill)


def cost_file(out_root, rev):
    return next((out_root / NPI / rev / "cost").glob("*_Unit_Cost.xlsx"))


def reviewed(out_root, rev, station="cost"):
    return json.loads((out_root / NPI / rev / station / "reviewed.json").read_text(encoding="utf-8"))


def table(ws, head_row=X.TABLE_ROW):
    heads = [c.value for c in ws[head_row]]
    rows = []
    for r in ws.iter_rows(min_row=head_row + 1, values_only=True):
        if all(v is None for v in r):
            break
        rows.append({h: v for h, v in zip(heads, r) if h})
    return rows


def evaluate(path, ref):
    return ExcelCompiler(filename=str(path)).evaluate(ref)


@pytest.fixture
def kalvara_b0(out_root):
    run_kalvara_filled(out_root, until=("B0", "po"))
    return out_root


# STEP11-1
def test_STEP11_1_a0_cost_has_seven_sheets(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    wb = openpyxl.load_workbook(cost_file(out_root, "A0"))
    assert wb.sheetnames == ["Summary", "Parameters", "Material", "Services", "Conversion", "Rates", "Approval"]


def test_STEP11_1_b0_cost_has_delta_vs_a0(kalvara_b0):
    wb = openpyxl.load_workbook(cost_file(kalvara_b0, "B0"))
    assert wb.sheetnames == ["Summary", "Delta vs A0", "Parameters", "Material", "Services", "Conversion",
                             "Rates", "Approval"]


# STEP11-2
def all_formula_cells(path):
    wb = openpyxl.load_workbook(path)
    return [f"{ws.title}!{c.coordinate}" for ws in wb for row in ws.iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")]


def test_STEP11_2_recalc_no_errors(kalvara_b0):
    for rev in ("A0", "B0"):
        path = cost_file(kalvara_b0, rev)
        xl = ExcelCompiler(filename=str(path))
        for ref in all_formula_cells(path):
            value = xl.evaluate(ref)
            assert not (isinstance(value, str) and value.startswith("#")), (rev, ref, value)


def test_STEP11_2_more_than_100_formulas(kalvara_b0):
    assert len(all_formula_cells(cost_file(kalvara_b0, "B0"))) > 100


def test_STEP11_2_total_equals_costing_function(kalvara_b0):
    for rev in ("A0", "B0"):
        r = reviewed(kalvara_b0, rev)
        assert r["complete"]
        assert abs(evaluate(cost_file(kalvara_b0, rev), X.SUMMARY_REF["total"]) - r["total"]) < 0.005
        assert evaluate(cost_file(kalvara_b0, rev), X.SUMMARY_REF["quote"]) == r["quote"]


# STEP11-3
def test_STEP11_3_pending_input_blank_with_status(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"), fill=False)
    ws = openpyxl.load_workbook(cost_file(out_root, "A0"))["Material"]
    row = next(r for r in table(ws) if r["Material Code"] == "CM-EP-UV365")
    assert row["Ext. Qty / pc"] is None and row["Status"] == PENDING


def test_STEP11_3_pending_makes_total_incomplete_no_error(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"), fill=False)
    path = cost_file(out_root, "A0")
    assert evaluate(path, X.SUMMARY_REF["total"]) == X.INCOMPLETE
    assert evaluate(path, X.SUMMARY_REF["quote"]) == X.INCOMPLETE
    xl = ExcelCompiler(filename=str(path))
    for ref in all_formula_cells(path):
        value = xl.evaluate(ref)
        assert not (isinstance(value, str) and value.startswith("#")), ref
    assert reviewed(out_root, "A0")["complete"] is False


# STEP11-4
def parameters(path):
    return {r["Parameter"]: r for r in table(openpyxl.load_workbook(path)["Parameters"])}


def test_STEP11_4_parameters_values_and_basis(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    p = parameters(cost_file(out_root, "A0"))
    expect = {"Material handling rate": (0.03, "RULES §3 單位成本 物料管理費"),
              "Manufacturing overhead rate": (0.22, "RULES §3 單位成本 製造費用"),
              "SG&A rate": (0.08, "RULES §3 單位成本 管銷"),
              "Target margin": (0.30, "RULES §3 報價 1"),
              "Quote rounding (USD)": (0.5, "RULES §3 報價 無條件進位到 USD")}
    for name, (value, basis) in expect.items():
        assert p[name]["Value"] == value and basis in p[name]["Basis"], name
    assert p["Cost lot size"]["Value"] == 1000 and "RULES §3 成本批量 一般" in p["Cost lot size"]["Basis"]
    assert p["Scrap rate"]["Value"] == SCRAP and "ENG-" in p["Scrap rate"]["Basis"]


# STEP9-13（第 3 項）：範圍裡選的值和依據寫在文件上
def test_STEP9_13_chosen_value_and_basis_in_output(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    lot = parameters(cost_file(out_root, "A0"))["Cost lot size"]
    assert lot["Value"] == 1000 and "500–1,500" in lot["Basis"]


# STEP11-5
def test_STEP11_5_scrap_rate_table_j():
    src = source_texts(INPUT_ROOT)
    s = costing.scrap_rate
    assert s("Fanout", 36, [], src)["value"] == 0.05
    assert s("Fiber_Array", 12, [], src)["value"] == 0.08
    assert s("Fiber_Array", 40, [], src)["value"] == 0.10
    assert s("Fiber_Array", 24, [], src)["value"] == PENDING
    pm32 = s("Fiber_Array", 32, ["PM"], src)
    assert pm32["value"] == PENDING
    assert {"RULES §3 報廢率 32–48 通道陣列", "RULES §3 報廢率 PM 陣列"} <= set(pm32["candidates"])


def test_STEP11_5_pending_scrap_lists_candidates_in_basis(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"), fill=False)
    scrap = parameters(cost_file(out_root, "A0"))["Scrap rate"]
    assert scrap["Value"] is None and scrap["Status"] == PENDING
    assert "候選" in scrap["Basis"]


def test_STEP11_5_pm_always_two_candidates():
    src = source_texts(INPUT_ROOT)
    pm16 = costing.scrap_rate("Fiber_Array", 16, ["PM"], src)
    assert pm16["value"] == PENDING
    assert set(pm16["candidates"]) == {"RULES §3 報廢率 PM 陣列", "RULES §3 報廢率 PM 陣列，端面在空氣中或有鍍膜"}


def test_STEP11_5_override_must_be_candidate_or_eng(out_root):
    run_kalvara_filled(out_root, until=("B0", "cost"))
    pipeline.prepare(NPI, "B0", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    j = fixture_of("B0", "cost")
    j["scrap_rate_override"] = {"value": 0.08, "sources": ["RULES §3 報廢率 一般光纖陣列（≤ 16 通道）"]}
    write_judgement(out_root, NPI, "B0", "cost", j)
    with pytest.raises(NpiError, match="候選"):
        pipeline.render(NPI, "B0", "cost", INPUT_ROOT, out_root)
    j["scrap_rate_override"] = {"value": 0.10, "sources": ["RULES §3 報廢率 32–48 通道陣列"]}
    write_judgement(out_root, NPI, "B0", "cost", j)
    pipeline.render(NPI, "B0", "cost", INPUT_ROOT, out_root)


# STEP11-6
def material(path):
    return {r["Material Code"]: r for r in table(openpyxl.load_workbook(path)["Material"])}


def test_STEP11_6_material_line_and_subtotals(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    path = cost_file(out_root, "A0")
    rows = material(path)
    r = rows["PP-MPO12-APC-F"]
    assert r["Ext. Qty / pc"] == 2
    lines = {l["part_no"]: l for l in reviewed(out_root, "A0")["lines"]}
    assert lines["PP-MPO12-APC-F"]["line_cost"] == pytest.approx(2 * lines["PP-MPO12-APC-F"]["unit_price"])
    for cat in ("RM", "BUY", "PKG"):
        assert evaluate(path, X.material_subtotal_ref(path, cat)) == pytest.approx(
            sum(l["line_cost"] for l in lines.values() if l["category"] == cat))


def test_STEP11_6_price_break_by_costing_qty():
    price = {"base": 10, "breaks": [(100, 9), (1000, 8)]}
    assert costing.unit_price(price, 2, 40) == 10           # 80 個
    assert costing.unit_price(price, 2, 50) == 9            # 100 個剛好到門檻
    assert costing.unit_price(price, 2, 500) == 8


# STEP11-7
def test_STEP11_7_lot_qualification_per_pc(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    svc = {s["code"]: s for s in reviewed(out_root, "A0")["inputs"]["services"]}
    assert svc["SV-REL-LOT"]["per_pc"] == pytest.approx(1650 / 1000)
    assert costing.service_per_pc({"price": 1650, "min_charge": 1650, "per": "lot"}, 1000) == pytest.approx(1.65)


def test_STEP11_7_coating_service_with_minimum_charge():
    assert costing.service_per_pc({"price": 3.2, "min_charge": 480, "per": "pcs"}, 100) == pytest.approx(4.8)
    assert costing.service_per_pc({"price": 3.2, "min_charge": 480, "per": "pcs"}, 150) == pytest.approx(3.2)


# STEP11-8
def test_STEP11_8_conversion_formula():
    assert costing.conversion_cost(20, 1000, 5, 22) == pytest.approx((20 / 1000 + 5) / 60 * 22)
    assert costing.conversion_cost(20, 1000, None, 22) is None


def test_STEP11_8_ops_same_as_reviewed_routing(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    ops = [r["Op."] for r in table(openpyxl.load_workbook(cost_file(out_root, "A0"))["Conversion"])]
    routing = [o["op"] for o in reviewed(out_root, "A0", "release")["routing"] if o["work_centre"] != "SUB"]
    assert ops == routing


def test_STEP11_8_sub_op_not_in_conversion(out_root):
    run_kalvara_filled(out_root, until=("C0", "po"))
    ops = [r["Op."] for r in table(openpyxl.load_workbook(cost_file(out_root, "C0"))["Conversion"])]
    assert "64" not in ops and "62" in ops
    assert "SV-ARC-1310" in {s["code"] for s in reviewed(out_root, "C0")["inputs"]["services"]}


# STEP11-9
def test_STEP11_9_rates_equal_rules_table(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    rows = table(openpyxl.load_workbook(cost_file(out_root, "A0"))["Rates"])
    assert {r["Work Centre"]: r["Rate (USD / hr)"] for r in rows} == {
        "FPR": 22, "PMA": 40, "VGA": 24, "CUR": 12, "POL": 30, "EFI": 45, "SCT": 28,
        "CPM": 55, "CON": 26, "OPT": 48, "PKG": 18, "REL": 15, "FOA": 22}


# STEP11-10
def test_STEP11_10_summary_order_table_i(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    ws = openpyxl.load_workbook(cost_file(out_root, "A0"))["Summary"]
    names = [r["Cost Element"] for r in table(ws, X.SUMMARY_TABLE_ROW)]
    assert names[:11] == X.SUMMARY_ELEMENTS
    r = reviewed(out_root, "A0")
    e = r["elements"]
    assert e["Material handling"] == pytest.approx((e["Material"] + e["Services"]) * 0.03, abs=1e-6)
    assert e["Manufacturing overhead"] == pytest.approx(e["Conversion"] * 0.22, abs=1e-6)
    assert r["total"] == pytest.approx(e["Manufacturing cost"] * 1.08, abs=1e-6)


def test_STEP11_10_quote_rounds_up_to_half():
    assert costing.quote(70.707, 0.30, 0.5) == 101.5
    assert costing.quote(70.0, 0.30, 0.5) == 100.0


def test_STEP11_10_target_price_compared(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    path = cost_file(out_root, "A0")
    assert evaluate(path, X.SUMMARY_REF["target"]) == 105.0
    r = reviewed(out_root, "A0")
    assert evaluate(path, X.SUMMARY_REF["vs_target"]) == pytest.approx(r["quote"] - 105.0)


# STEP11-11
def test_STEP11_11_packaging_not_in_scrap_base():
    base = {"lines": [{"part_no": "A", "category": "RM", "qty": 1, "price": {"base": 10, "breaks": []}},
                      {"part_no": "P", "category": "PKG", "qty": 1, "price": {"base": 2, "breaks": []}}],
            "services": [], "conversion": [],
            "params": {"costing_qty": 1, "lot_size": 1000, "scrap_rate": 0.1, "handling": 0.03, "overhead": 0.22,
                       "sga": 0.08, "margin": 0.3, "rounding": 0.5}}
    a = costing.model(base)
    base["lines"][1]["price"]["base"] = 5
    b = costing.model(base)
    assert b["Scrap"] == pytest.approx(a["Scrap"])                      # VERIFY STEP11-11：報廢那一列不變
    assert a["Scrap"] == pytest.approx((10 + 10 * 0.03) * 0.1)             # 包材和包材的物料管理費都不算（2026-11-02 使用者決定）


# STEP11-12
def nre(path):
    return table(openpyxl.load_workbook(path)["Summary"], X.NRE_TABLE_ROW)


def test_STEP11_12_a0_nre_four_rows(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    kinds = [r["Kind"] for r in nre(cost_file(out_root, "A0"))]
    assert kinds[:4] == ["fixture", "test_setup", "fai", "design_qualification"]


def test_STEP11_12_ecr_nre_required_from_b0(kalvara_b0):
    assert any(r["Kind"] == "ecr" for r in nre(cost_file(kalvara_b0, "B0")))
    out = kalvara_b0.parent / "o2" / "output"
    run_kalvara_filled(out, until=("B0", "cost"))
    pipeline.prepare(NPI, "B0", "cost", INPUT_ROOT, out, date="2026-11-02")
    j = fixture_of("B0", "cost")
    j["ecr_nre"] = []
    write_judgement(out, NPI, "B0", "cost", j)
    with pytest.raises(NpiError, match="ECR NRE"):
        pipeline.render(NPI, "B0", "cost", INPUT_ROOT, out)


def test_STEP11_12_nre_amount_needs_source_or_pending(out_root):
    run_kalvara_filled(out_root, until=("A0", "cost"))
    pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    j = fixture_of("A0", "cost")
    j["nre"][0]["amount"] = 4500
    write_judgement(out_root, NPI, "A0", "cost", j)
    with pytest.raises(NpiError, match="4500"):
        pipeline.render(NPI, "A0", "cost", INPUT_ROOT, out_root)


# STEP11-13
def small_inputs(lot=1000, extra_qty=0):
    return {"lines": [{"part_no": "A", "category": "RM", "qty": 1, "price": {"base": 10, "breaks": []}},
                      {"part_no": "B", "category": "BUY", "qty": 2 + extra_qty, "price": {"base": 3, "breaks": []}}],
            "services": [{"code": "SV-REL-LOT", "price": 1650, "min_charge": 1650, "per": "lot"}],
            "conversion": [{"op": "10", "work_centre": "FPR", "setup": 20, "run": 5, "rate": 22}],
            "params": {"costing_qty": 1000, "lot_size": lot, "scrap_rate": 0.1, "handling": 0.03, "overhead": 0.22,
                       "sga": 0.08, "margin": 0.3, "rounding": 0.5}}


def test_STEP11_13_delta_rows_sum_to_total():
    old, new = small_inputs(), small_inputs(lot=500, extra_qty=1)
    new["lines"].append({"part_no": "C", "category": "RM", "qty": 1, "price": {"base": 4, "breaks": []}})
    new["conversion"].append({"op": "20", "work_centre": "PMA", "setup": 20, "run": 3, "rate": 40})
    rows = costing.delta(old, new, {"B": "CH1", "C": "CH2", "Op 20": "CH2"})
    total = costing.model(new)["total"] - costing.model(old)["total"]
    assert sum(v for _, v in rows) == pytest.approx(total, abs=1e-9)
    assert [k for k, _ in rows] == [costing.PARAM_ROW, "CH1", "CH2"]


def test_STEP11_13_parameter_change_row():
    rows = dict(costing.delta(small_inputs(), small_inputs(lot=500), {}))
    assert rows[costing.PARAM_ROW] != 0
    assert set(rows) == {costing.PARAM_ROW}


def test_STEP11_13_delta_check_cell_ok(kalvara_b0):
    path = cost_file(kalvara_b0, "B0")
    assert evaluate(path, X.DELTA_CHECK_REF.format(prev="A0")) == "OK"


# STEP11-14
def test_STEP11_14_minor_keeps_previous_quote(out_root):
    run_kalvara_filled(out_root, until=("C1", "supply"))
    c0, c1 = reviewed(out_root, "C0"), reviewed(out_root, "C1")
    assert c1["quote"] == c0["quote"]
    assert c1["quote_basis"].startswith("沿用 C0")


def test_STEP11_14_margin_before_and_after(out_root):
    run_kalvara_filled(out_root, until=("C1", "supply"))
    c0, c1 = reviewed(out_root, "C0"), reviewed(out_root, "C1")
    path = cost_file(out_root, "C1")
    assert evaluate(path, X.DELTA_MARGIN_REF.format(prev="C0", col="B")) == pytest.approx(c0["margin"])
    assert evaluate(path, X.DELTA_MARGIN_REF.format(prev="C0", col="C")) == pytest.approx(c1["margin"])


# STEP11-15
def test_STEP11_15_approval_rows(out_root):
    run_kalvara_filled(out_root, until=("A0", "po"))
    rows = {r["Step"]: r for r in table(openpyxl.load_workbook(cost_file(out_root, "A0"))["Approval"])}
    state = pipeline.load_state(NPI, out_root)
    date = next(s["date"] for s in state["revs"]["A0"]["stations"] if s["name"] == "cost")
    assert (rows["Prepared"]["Name"], rows["Prepared"]["Date"]) == ("Alex Lin", date)
    assert rows["Reviewed"]["Status / Comment"] == "待確認"
    assert rows["Finance confirmed"]["Status / Comment"] == "待確認"
    assert rows["Reviewed"]["Name"] is None and rows["Finance confirmed"]["Date"] is None


# STEP11-16
def test_STEP11_16_tell_lot_size_reaches_po_check(out_root):
    run_kalvara_filled(out_root, until=("A0", "cost"))

    def lot_800(j):
        eng = pipeline.tell(NPI, "A0", "cost", "成本批量改成 800", out_root)
        j["lot_size"] = {"value": 800, "sources": [eng]}
    run_station(out_root, "A0", "cost", cost_override=lot_800)
    r = reviewed(out_root, "A0")
    assert r["lot_size"] == 800
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    facts = json.loads(pipeline.prepare(NPI, "A0", "po", INPUT_ROOT, out_root, date="2026-11-02").read_text(encoding="utf-8"))
    assert facts["cost"]["total"] == pytest.approx(r["total"])


# 來自 PLANS
def test_PLANS_P78_read_back_recomputes_from_inputs(out_root):
    run_kalvara_filled(out_root, until=("A0", "cost"))
    pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    j = fixture_of("A0", "cost")
    eng = pipeline.tell(NPI, "A0", "cost", f"測試用：報廢率 {SCRAP}", out_root)
    j["scrap_rate_override"] = {"value": SCRAP, "sources": [eng]}
    write_judgement(out_root, NPI, "A0", "cost", j)
    [path] = pipeline.render(NPI, "A0", "cost", INPUT_ROOT, out_root)
    before = read_cost(path)["total"]
    wb = openpyxl.load_workbook(path)
    ws = wb["Material"]
    heads = [c.value for c in ws[X.TABLE_ROW]]
    for row in ws.iter_rows(min_row=X.TABLE_ROW + 1):
        if row[heads.index("Material Code")].value == "PP-BOOT-FA24":
            row[heads.index("Base Price (USD)")].value += 1
            row[heads.index("Break 1 Price (USD)")].value = None
            row[heads.index("Break 2 Price (USD)")].value = None
    wb.save(path)
    pipeline.approve(NPI, "A0", "cost", INPUT_ROOT, out_root)
    assert reviewed(out_root, "A0")["total"] == pytest.approx(before + 1 * (1 + 0.03) * (1 + SCRAP) * (1 + 0.08))


def test_PLANS_P79_pycel_supports_used_functions(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"], ws["A2"] = 2, "待工程師填寫"
    formulas = {"B1": '=COUNTIF(A1:A5,"<>")', "B2": '=COUNTIF(A1:A5,"")', "B3": "=CEILING(101.01,0.5)",
                "B4": '=IF(ISBLANK(A3),"",A3)', "B5": "=ISNUMBER(A2)", "B6": '=SUMIF(A1:A2,"<>x",A1:A2)',
                "B7": '=IFERROR(1/0,"x")', "B8": "=ROUND(1.234,2)", "B9": "=ABS(-1)", "B10": "=MAX(1,2)"}
    for k, v in formulas.items():
        ws[k] = v
    wb.save(tmp_path / "f.xlsx")
    xl = ExcelCompiler(filename=str(tmp_path / "f.xlsx"))
    assert [xl.evaluate(f"S!{k}") for k in formulas] == [2, 3, 101.5, "", False, 2, "x", 1.23, 1, 2]


def test_PLANS_P73_fanout_has_no_lot_qualification(out_root):
    pipeline.intake(CVN_A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_station(out_root, "A0", st, npi="NPI-26-104")
    r = json.loads((out_root / "NPI-26-104" / "A0" / "cost" / "reviewed.json").read_text(encoding="utf-8"))
    assert r["scrap_rate"] == 0.05
    assert "SV-REL-LOT" not in {s["code"] for s in r["inputs"]["services"]}


def test_PLANS_P81_parameter_change_computed_first():
    rows = costing.delta(small_inputs(), small_inputs(lot=500, extra_qty=1), {"B": "CH1"})
    assert rows[0][0] == costing.PARAM_ROW
    ch1 = dict(rows)["CH1"]
    m = 3 * (1 + 0.03) * (1 + 0.1) * (1 + 0.08)             # 1 個 B（USD 3）套這一版的費率
    assert ch1 == pytest.approx(m)


def test_PLANS_P72_prev_quote_source_for_ecr(kalvara_b0):
    facts = json.loads((kalvara_b0 / NPI / "B0" / "cost" / "facts.json").read_text(encoding="utf-8"))
    a0 = reviewed(kalvara_b0, "A0")
    assert facts["sources"]["PREV quote"] == f"{a0['quote']:g}"
    assert parameters(cost_file(kalvara_b0, "B0"))["Target / comparison price"]["Value"] == a0["quote"]

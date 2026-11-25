import openpyxl

from npi import pipeline
from npi.readers.po import read_po
from npi.stations.po_check import po_findings

from conftest import (A0_PO, A0_SPEC, INPUT_ROOT, run_real, write_judgement)

NPI = "NPI-26-097"
OURS = {"LPC-FA24-127-8A": {"rev": "A0", "cust_rev": "A", "spec": "LPC-PS-26097 Rev A0"}}


def po_report(out_root, fill_cost=None):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    run_real(out_root, "A0", "release")
    pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    from conftest import fixture_of
    write_judgement(out_root, NPI, "A0", "cost", fixture_of("A0", "cost"))
    [uc] = pipeline.render(NPI, "A0", "cost", INPUT_ROOT, out_root)
    if fill_cost is not None:
        # 第 3 批：成本表是公式，approve 只讀輸入格（PLANS P78），所以填輸入格：
        # 報廢率、待填的材料用量、每道工序的單件時間（fill_cost 分鐘），讓單位成本遠高於 PO 單價（使用者 2026-11-01 同意）
        wb = openpyxl.load_workbook(uc)
        for name, value_col, status_col in (("Parameters", 2, 5), ("Material", 5, 16), ("Conversion", 6, 10)):
            ws = wb[name]
            for r in range(9, ws.max_row + 1):
                if ws.cell(r, status_col).value == "待工程師填寫":
                    ws.cell(r, value_col, 0.1 if name == "Parameters" else 1 if name == "Material" else fill_cost)
                    ws.cell(r, status_col, None)
        wb.save(uc)
    pipeline.approve(NPI, "A0", "cost", INPUT_ROOT, out_root)
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "po")
    report = out_root / NPI / "A0" / "po" / "PO_Check_KVP-PO-7700-2614_Rev0.md"
    return report.read_text(encoding="utf-8")


# STEP4-1
def test_STEP4_1_po_reader_kalvara_rev0():
    po = read_po(A0_PO)
    assert (po["po_no"], po["rev"], po["date"], po["total_qty"]) == ("KVP-PO-7700-2614", 0, "2026-07-28", 2000)
    assert [(s["line"], s["qty"], s["need_date"]) for s in po["schedule"]] == [
        ("1.1", 100, "2026-09-18"), ("1.2", 400, "2026-10-02"), ("1.3", 750, "2026-10-16"), ("1.4", 750, "2026-10-30")]
    assert all(s["unit_price"] == 112.00 and s["lpc_pn"] == "LPC-FA24-127-8A" and s["cust_rev"] == "A"
               for s in po["schedule"])


def test_STEP4_1_report_lists_po_fields(out_root):
    text = po_report(out_root)
    for s in ("KVP-PO-7700-2614", "Rev 0", "LPC-FA24-127-8A", "2,000", "112.00",
              "2026-09-18", "2026-10-02", "2026-10-16", "2026-10-30"):
        assert s in text, s


def test_STEP4_1_report_compares_spec_rev_and_unit_cost(out_root):
    text = po_report(out_root)
    assert "LPC-PS-26097 Rev A0" in text
    assert "無法比較" in text          # 單位成本不完整（P14）


# STEP4-2
def test_STEP4_2_part_number_mismatch_names_line_and_field():
    po = read_po(A0_PO)
    found = po_findings(po, {"LPC-FA24-127-8X": OURS["LPC-FA24-127-8A"]}, None)
    assert any("1.1" in f and "LPC P/N" in f and "不一致" in f for f in found)


def test_STEP4_2_revision_mismatch_flagged():
    po = read_po(A0_PO)
    ours = {"LPC-FA24-127-8A": {**OURS["LPC-FA24-127-8A"], "cust_rev": "B"}}
    assert any("1.1" in f and "客戶版次" in f and "不一致" in f for f in po_findings(po, ours, None))


# STEP4-3
def test_STEP4_3_price_below_unit_cost_flagged(out_root):
    text = po_report(out_root, fill_cost=50)
    assert "低於單位成本" in text


def test_STEP4_3_incomplete_cost_says_cannot_compare():
    po = read_po(A0_PO)
    found = po_findings(po, OURS, {"complete": False, "total": None, "rev": "A0"})
    assert any("無法比較" in f for f in found)
    assert not any("低於單位成本" in f for f in found)

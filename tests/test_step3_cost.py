import pytest

from npi import pipeline
from npi.readers.ours import read_cost
from npi.sources import PENDING

from conftest import (A0_SPEC, INPUT_ROOT, fixture_of, run_real, write_judgement)

NPI = "NPI-26-097"
UC = "LPC-UC-26097_RevA0_Unit_Cost.xlsx"


def cost_a0(out_root, extra_bom=None):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    rel = fixture_of("A0", "release")
    rel["bom"] += extra_bom or []
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", rel)
    pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "cost", fixture_of("A0", "cost"))
    [path] = pipeline.render(NPI, "A0", "cost", INPUT_ROOT, out_root)
    return path, read_cost(path)


def line(cost, part):
    return next(l for l in cost["lines"] if l["part_no"] == part)


# STEP3-1
def test_STEP3_1_unit_cost_xlsx_written(out_root):
    path, _ = cost_a0(out_root)
    assert path == out_root / NPI / "A0" / "cost" / UC


def test_STEP3_1_each_price_matches_price_list_with_source(out_root):
    from npi.readers.master import read_pl
    pl = read_pl(INPUT_ROOT)["materials"]
    _, cost = cost_a0(out_root)
    priced = [l for l in cost["lines"] if l["unit_price"] is not None]
    assert priced
    for l in priced:
        row = pl[l["part_no"]]
        prices = {row["Base Unit Price (USD)"], row["Break 1 Price (USD)"], row["Break 2 Price (USD)"]}
        assert l["unit_price"] in prices, l
        assert "LPC-PL-2026H2" in l["price_source"] and l["part_no"] in l["price_source"]


def test_STEP3_1_price_break_chosen_by_quantity(out_root):
    _, cost = cost_a0(out_root)        # 估價數量 2,000（fixture 引用 R-14）
    assert line(cost, "RM-VG-Q24-127")["unit_price"] == 12.9      # 1 x 2000 ≥ 1000 → Break 1
    assert "Break 1" in line(cost, "RM-VG-Q24-127")["price_source"]
    assert line(cost, "PP-MPO12-APC-F")["unit_price"] == 5.2      # 2 x 2000 ≥ 2000 → Break 1
    assert line(cost, "PP-BOOT-FA24")["unit_price"] == 0.48       # 2000 < 5000 → Base
    assert "Base" in line(cost, "PP-BOOT-FA24")["price_source"]


# STEP3-2
EXTRA = [{"item": "70", "part_no": "RM-XX-NOTEXIST", "description": "Unknown part", "make_buy": "Buy",
          "qty_per": 1, "uom": "pcs", "sources": ["R-01"],
          "op": "110", "category": "待工程師填寫"}]        # 第 3 批：補工序和類別（同 test_STEP2_4，斷言不變）


def test_STEP3_2_missing_price_pending_not_zero(out_root):
    _, cost = cost_a0(out_root, EXTRA)
    missing = line(cost, "RM-XX-NOTEXIST")
    assert missing["unit_price"] is None and missing["line_cost"] is None
    assert missing["price_text"] == PENDING
    known = sum(l["line_cost"] for l in cost["lines"] if l["line_cost"] is not None)
    assert cost["material_total"] == pytest.approx(known)


def test_STEP3_2_total_marked_incomplete(out_root):
    _, cost = cost_a0(out_root, EXTRA)
    assert cost["complete"] is False
    assert cost["total"] is None
    assert "不完整" in cost["total_note"]


# STEP3-3
def test_STEP3_3_line_cost_equals_qty_times_price(out_root):
    _, cost = cost_a0(out_root)
    assert line(cost, "RM-VG-Q24-127")["line_cost"] == pytest.approx(1 * 12.9)
    assert line(cost, "PP-MPO12-APC-F")["line_cost"] == pytest.approx(2 * 5.2)


# test_PLANS_P14_non_material_elements_pending：P14（只算直接材料）被 PLANS P69～P81 取代，
# 由 tests/test_step11_cost.py 接手（使用者 2026-11-01 同意拿掉）

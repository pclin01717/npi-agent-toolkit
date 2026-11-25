"""STEP 12 第 3 批重考（自動的部分）。STEP12-1 也取代第 2 批的 STEP8-9（使用者 2026-11-01 同意）。"""
import json
import re

from conftest import KALVARA_FIXTURES
from test_step8_fanout import kalvara_snapshot

GOLDEN = KALVARA_FIXTURES / "batch2_golden.json"
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_RFC = re.compile(r"\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} [+-]\d{4}")


def _norm(value):
    """PLANS 表 K：日期（含檔名、內文、eml Date）不比。"""
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items() if k.lower() != "date"}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    if isinstance(value, str):
        return _ISO.sub("<DATE>", _RFC.sub("<DATE>", value))
    return value


def _only_golden_keys(ours, golden):
    if isinstance(golden, dict) and isinstance(ours, dict):
        return {k: _only_golden_keys(ours.get(k), v) for k, v in golden.items()}
    if isinstance(golden, list) and isinstance(ours, list) and len(golden) == len(ours):
        return [_only_golden_keys(o, g) for o, g in zip(ours, golden)]
    return ours


def _table_k(snap):
    out = {}
    for path, value in snap.items():
        if path.split("/")[1] == "cost":                   # 成本站整份不比
            continue
        if path.endswith("release/reviewed.json"):
            value = {k: v for k, v in value.items() if k != "bom"}
        out[_ISO.sub("<DATE>", path)] = _norm(value)
    return out


# STEP12-1
def test_STEP12_1_kalvara_same_as_batch2_except_table_k(out_root):
    golden = _table_k(json.loads(GOLDEN.read_text(encoding="utf-8")))
    ours = _table_k(kalvara_snapshot(out_root))
    assert sorted(ours) == sorted(golden)
    for path in golden:
        assert _only_golden_keys(ours[path], golden[path]) == golden[path], path


def test_STEP12_1_compare_lists_cost_differences(out_root):
    from npi.compare import compare
    from conftest import INPUT_ROOT
    from test_step11_cost import run_kalvara_filled
    run_kalvara_filled(out_root, until=("A0", "po"))
    diffs = compare(out_root, INPUT_ROOT, "NPI-26-097", "A0")
    for label in ("成本／總計 USD", "成本／報價 USD", "成本／報廢 USD"):
        assert any(d.startswith(label) for d in diffs), label


# STEP12-2（自動的部分；Corvane A0～C1 用 /npi 重跑是手動）
def test_STEP12_2_corvane_a0_fixture_bom_and_cost(out_root):
    import openpyxl
    from npi import pipeline
    from conftest import CVN_A0_SPEC, INPUT_ROOT
    from test_step11_cost import run_station
    npi = "NPI-26-104"
    pipeline.intake(CVN_A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_station(out_root, "A0", st, npi=npi)
    base = out_root / npi / "A0"
    bom = openpyxl.load_workbook(next((base / "release").glob("*_BOM.xlsx")))
    cost = openpyxl.load_workbook(next((base / "cost").glob("*_Unit_Cost.xlsx")))
    assert len(bom.sheetnames) == 4 and len(cost.sheetnames) == 7
    routing = [r[2] for r in bom["Routing"].iter_rows(min_row=9, values_only=True) if r[0]]
    assert routing == ["FOA", "FOA", "CON", "SCT", "OPT", "PKG"]
    r = json.loads((base / "cost" / "reviewed.json").read_text(encoding="utf-8"))
    assert r["scrap_rate"] == 0.05
    assert "SV-REL-LOT" not in {s["code"] for s in r["inputs"]["services"]}
    for wb in (bom, cost):
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                assert not any("FAU" in str(v) for v in row if v), (ws.title, row)

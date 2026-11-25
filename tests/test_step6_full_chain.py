import hashlib
import json
import subprocess
import sys

import openpyxl

from npi import pipeline
from npi.compare import compare

from conftest import (A0_PO, A0_SPEC, B0_ECR, B0_PO, C0_ECR, C1_ECR, INPUT_ROOT, KALVARA, PROJECT,
                      fixture_of, run_real, write_judgement)

NPI = "NPI-26-097"
C0_PO = KALVARA / "C0/05_Customer_PO/KVP-PO-7700-2614_Rev2.pdf"
CHAIN = [("A0", A0_SPEC, ["dfm", "release", "cost"]), ("A0", A0_PO, ["po", "supply"]),
         ("B0", B0_ECR, ["dfm", "release", "cost"]), ("B0", B0_PO, ["po", "supply"]),
         ("C0", C0_ECR, ["dfm", "release", "cost"]), ("C0", C0_PO, ["po", "supply"]),
         ("C1", C1_ECR, ["dfm", "release", "cost", "supply"])]


def run_kalvara(out_root, date="2026-11-02", until=None):
    """Kalvara 照 CHAIN 跑；until=(版次, 站) 時跑到那一站之前就停（那一站不跑）。"""
    for rev, doc, stations in CHAIN:
        pipeline.intake(doc, INPUT_ROOT, out_root)
        for st in stations:
            if until == (rev, st):
                return
            run_real(out_root, rev, st, date=date)


def tree_hash(*dirs):
    out = {}
    for d in dirs:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


EXPECTED = {
    "A0": ["2026-11-02_DFM_Feedback_KVP-SPC-2408.eml", "LPC-PS-26097_RevA0_Product_Specification.docx",
           "LPC-FA24-127-8A_RevA0.step", "LPC-UC-26097_RevA0_Unit_Cost.xlsx",
           "PO_Check_KVP-PO-7700-2614_Rev0.md", "2026-11-02_Material_Preparation_NPI-26-097.eml"],
    "B0": ["2026-11-02_ECR-01_Impact_Assessment_NPI-26-097.eml", "LPC-BOM-26097_RevB0_BOM.xlsx",
           "LPC-UC-26097_RevB0_Unit_Cost.xlsx", "PO_Check_KVP-PO-7700-2614_Rev1.md",
           "2026-11-02_Material_Change_Notice_NPI-26-097.eml"],
    "C0": ["2026-11-02_ECR-02_Impact_Assessment_NPI-26-097.eml", "LPC-FA32-127-0C_RevC0.step",
           "PO_Check_KVP-PO-7700-2614_Rev2.md", "2026-11-02_Material_Change_Notice_NPI-26-097.eml"],
    "C1": ["2026-11-02_ECR-03_Impact_Assessment_NPI-26-097.eml", "LPC-DWG-26097_RevC1_Fiber_Array_Drawing.pdf",
           "LPC-UC-26097_RevC1_Unit_Cost.xlsx", "2026-11-02_Material_Change_Notice_NPI-26-097.eml"],
}


# STEP6-1
def test_STEP6_1_kalvara_a0_to_c1_all_outputs_exist(out_root):
    run_kalvara(out_root)
    for rev, names in EXPECTED.items():
        found = {p.name for p in (out_root / NPI / rev).rglob("*") if p.is_file()}
        for name in names:
            assert name in found, (rev, name)
    state = pipeline.load_state(NPI, out_root)
    assert all(s["status"] == "已審" for r in state["revs"].values() for s in r["stations"])


def test_STEP6_1_input_tree_unchanged(out_root):
    before = tree_hash(KALVARA, INPUT_ROOT / "00_Factory_Master_Data")
    run_kalvara(out_root)
    assert tree_hash(KALVARA, INPUT_ROOT / "00_Factory_Master_Data") == before


# STEP6-2
def test_STEP6_2_rerender_same_content(tmp_path):
    first, second = tmp_path / "run1", tmp_path / "run2"
    run_kalvara(first)
    run_kalvara(second)
    for p in sorted((first / NPI).rglob("reviewed.json")):
        q = second / p.relative_to(first)
        assert json.loads(p.read_text(encoding="utf-8")) == json.loads(q.read_text(encoding="utf-8")), p


def test_STEP6_2_rerender_no_extra_files(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", fixture_of("A0", "release"))
    pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    once = sorted(p.name for p in (out_root / NPI / "A0" / "release").iterdir())
    pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    assert sorted(p.name for p in (out_root / NPI / "A0" / "release").iterdir()) == once


# STEP6-3
def test_STEP6_3_next_station_from_files_only(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")

    def cli(*args):
        r = subprocess.run([sys.executable, "-m", "npi", "--out-root", str(out_root), *args],
                           cwd=PROJECT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout

    cli("decide", NPI, "A0", "全部接受")
    cli("prepare", NPI, "A0", "release", "--date", "2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", fixture_of("A0", "release"))
    assert "LPC-BOM-26097_RevA0_BOM.xlsx" in cli("render", NPI, "A0", "release")
    cli("approve", NPI, "A0", "release")
    assert "工程發行：已審" in cli("status", NPI)


# STEP6-4
def test_STEP6_4_compare_lists_differences(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", fixture_of("A0", "release"))
    files = pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    bom = next(f for f in files if f.suffix == ".xlsx")
    wb = openpyxl.load_workbook(bom)
    heads = [c.value for c in wb["BOM"][8]]             # 第 3 批：照表頭名稱找欄（使用者 2026-11-01 同意）
    for row in wb["BOM"].iter_rows():
        if row[heads.index("Part No.")].value == "RM-LD-Q24":
            row[heads.index("Qty per Parent")].value = 3
    wb.save(bom)
    pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)
    diffs = compare(out_root, INPUT_ROOT, NPI, "A0")
    assert any("RM-LD-Q24" in d and "3" in d for d in diffs)
    assert not any("channels" in d for d in diffs)     # 24 ch 跟答案一樣，不列


def test_STEP6_4_compare_does_not_fail_on_differences(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    run_real(out_root, "A0", "release")
    r = subprocess.run([sys.executable, "-m", "npi", "--out-root", str(out_root), "compare", NPI, "A0"],
                       cwd=PROJECT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "差異" in r.stdout

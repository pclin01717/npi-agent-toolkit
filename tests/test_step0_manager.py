import json
import re
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

from npi import pipeline
from npi.errors import NpiError
from npi.intake import identify
from npi.readers.ours import read_bom
from npi.render.xlsx_out import write_bom
from npi.state import PENDING, REVIEWED, NOT_RUN

from conftest import (A0_PO, A0_SPEC, B0_ECR, C1_ECR, INPUT_ROOT, KALVARA,
                      PROJECT, write_judgement)

NPI = "NPI-26-097"


def run_station(out_root, rev, station):
    """prepare → 判讀檔 → render → approve，一站走完。工程發行站先記客戶決定。"""
    if station == "release":
        pipeline.decide(NPI, rev, "全部接受", out_root)
    pipeline.prepare(NPI, rev, station, INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, rev, station, {})
    pipeline.render(NPI, rev, station, INPUT_ROOT, out_root)
    pipeline.approve(NPI, rev, station, INPUT_ROOT, out_root)


def stations_of(out_root, rev):
    state = pipeline.load_state(NPI, out_root)
    return {s["name"]: s["status"] for s in state["revs"][rev]["stations"]}


# STEP0-1
def test_STEP0_1_draft_spec_identified():
    doc = identify(A0_SPEC, INPUT_ROOT)
    assert (doc.npi_no, doc.rev, doc.kind) == (NPI, "A0", "draft_spec")


def test_STEP0_1_next_station_is_dfm_others_not_run(out_root):
    summary = pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    assert summary["next"] == "dfm"
    assert stations_of(out_root, "A0") == {"dfm": NOT_RUN, "release": NOT_RUN, "cost": NOT_RUN}


def test_STEP0_1_release_prepare_refused_before_dfm_reviewed(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    with pytest.raises(NpiError, match="DFM"):
        pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root)


# STEP0-2
def test_STEP0_2_ecr_identified_with_previous_rev():
    doc = identify(B0_ECR, INPUT_ROOT)
    assert (doc.rev, doc.kind, doc.previous_rev) == ("B0", "ecr", "A0")


def test_STEP0_2_ecr_next_station_is_impact(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_station(out_root, "A0", st)
    summary = pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    assert summary["next"] == "dfm"
    assert "變更影響" in pipeline.format_status(pipeline.load_state(NPI, out_root))


# STEP0-3
def test_STEP0_3_ecr_refused_names_unreviewed_station(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    with pytest.raises(NpiError, match="A0.*工程發行"):
        pipeline.intake(B0_ECR, INPUT_ROOT, out_root)


def test_STEP0_3_ecr_accepted_when_previous_all_reviewed(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_station(out_root, "A0", st)
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    for st in ("po", "supply"):
        run_station(out_root, "A0", st)
    summary = pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    assert summary["rev"] == "B0"


# STEP0-4
def test_STEP0_4_c1_schedule_no_po_supply_after_release():
    doc = identify(C1_ECR, INPUT_ROOT)
    order = pipeline.schedule_for(doc)
    assert "po" not in order
    assert order.index("supply") > order.index("release")


# STEP0-5
def test_STEP0_5_master_data_file_rejected_with_name_and_reason():
    path = INPUT_ROOT / "00_Factory_Master_Data/LPC-PL-2026H2_Material_Price_List.xlsx"
    with pytest.raises(NpiError, match="LPC-PL-2026H2_Material_Price_List.xlsx.*不在案子的版次資料夾"):
        identify(path, INPUT_ROOT)


def test_STEP0_5_our_document_rejected():
    path = KALVARA / "A0/02_DFM_Feedback/2026-07-03_DFM_Feedback_KVP-SPC-2408.eml"
    with pytest.raises(NpiError, match="2026-07-03_DFM_Feedback_KVP-SPC-2408.eml.*不是客戶文件"):
        identify(path, INPUT_ROOT)


def test_STEP0_5_file_outside_input_rejected(tmp_path):
    path = tmp_path / "spec.docx"
    path.write_bytes(b"")
    with pytest.raises(NpiError, match="spec.docx.*不在案子的版次資料夾"):
        identify(path, INPUT_ROOT)


# STEP0-6
def test_STEP0_6_render_sets_pending_review(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    write_judgement(out_root, NPI, "A0", "dfm", {})
    pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    assert stations_of(out_root, "A0")["dfm"] == PENDING


def test_STEP0_6_approve_sets_reviewed_and_unlocks_next(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    assert stations_of(out_root, "A0")["dfm"] == REVIEWED
    assert (out_root / NPI / "A0/dfm/reviewed.json").exists()
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root)


def test_STEP0_6_next_station_refused_while_pending(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    write_judgement(out_root, NPI, "A0", "dfm", {})
    pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    with pytest.raises(NpiError, match="待審"):
        pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root)


# STEP0-7
class BomStation:
    """工程發行站的替身：用真正的 BOM 範本寫出、讀回。"""
    ROWS = [{"item": "10", "part_no": "RM-VG-Q24-127", "description": "V-groove substrate",
             "make_buy": "Buy", "qty_per": 1, "uom": "pcs"}]

    @staticmethod
    def prepare(ctx):
        return {}

    @staticmethod
    def check(ctx, facts, judgement):
        return []

    @staticmethod
    def render(ctx, facts, judgement):
        path = ctx.station_dir / "LPC-BOM-26097_RevA0_BOM.xlsx"
        write_bom(path, {"doc_no": "LPC-BOM-26097", "rev": "A0", "product": "LPC-FA24-127-8A",
                         "npi_no": NPI, "date": ctx.date}, BomStation.ROWS)
        return [path]

    @staticmethod
    def read_back(ctx, facts, judgement):
        return {"bom": read_bom(ctx.station_dir / "LPC-BOM-26097_RevA0_BOM.xlsx")}


class CostReadsUpstream:
    @staticmethod
    def prepare(ctx):
        return {"bom": pipeline.upstream(ctx, "release")["bom"]}


def test_STEP0_7_edited_bom_qty_reaches_next_station(out_root, fake_stations, monkeypatch):
    from npi import stations
    monkeypatch.setitem(stations.REGISTRY, "release", BomStation)
    monkeypatch.setitem(stations.REGISTRY, "cost", CostReadsUpstream)
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", {})
    [bom_path] = pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)

    wb = openpyxl.load_workbook(bom_path)
    ws = wb["BOM"]
    heads = [c.value for c in ws[8]]                    # 第 3 批：照表頭名稱找欄（使用者 2026-11-01 同意）
    for row in ws.iter_rows():
        if row[heads.index("Part No.")].value == "RM-VG-Q24-127":
            row[heads.index("Qty per Parent")].value = 2
    wb.save(bom_path)

    pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)
    facts_path = pipeline.prepare(NPI, "A0", "cost", INPUT_ROOT, out_root)
    facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
    assert facts["bom"][0]["qty_per"] == 2


# STEP0-8
def test_STEP0_8_status_from_fresh_process_shows_pending(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root)
    write_judgement(out_root, NPI, "A0", "release", {})
    pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    result = subprocess.run([sys.executable, "-m", "npi", "--out-root", str(out_root), "status", NPI],
                            cwd=PROJECT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "工程發行：待審" in result.stdout
    assert "DFM：已審" in result.stdout
    assert "下一步：審「工程發行」" in result.stdout


def test_STEP0_8_reviewed_stations_not_rerun(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    with pytest.raises(NpiError, match="已審.*reopen"):
        pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root)


# 來自 PLANS P5
def test_PLANS_P5_render_refused_after_approve(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    with pytest.raises(NpiError, match="已審.*reopen"):
        pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)


def test_PLANS_P5_reopen_resets_downstream(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    run_station(out_root, "A0", "release")
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    assert stations_of(out_root, "A0") == {"dfm": NOT_RUN, "release": NOT_RUN, "cost": NOT_RUN}


# 來自補充：第 2 批起可以用 Corvane 的客戶文件，但不能讀它的我方文件（02～04、06）和答案檔（PLANS P45）
MENTIONS_CORVANE = re.compile("NPI-26-" + "104|FO36_" + "Fanout|CORVANE|CVN_")
OUR_DOCS = re.compile(r"(?:^|[/\"'])0[2346]_[A-Z]|_ground_" + "truth")


def test_補充_tests_never_reference_corvane_our_docs():
    for path in Path(__file__).parent.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".txt", ".md"} and path != Path(__file__):
            text = path.read_text(encoding="utf-8")
            if MENTIONS_CORVANE.search(text):
                assert not OUR_DOCS.search(text), (path, OUR_DOCS.search(text).group())


# Fixes #26（突變測試沒抓到）：守門的樣式要認得我方文件資料夾和答案檔，不誤認客戶文件和 Kalvara 的 ECR 檔名
def test_issue26_corvane_guard_patterns():
    for bad in ('CORVANE / "B0/02_DFM_Feedback"', 'CORVANE / "03_Product_Spec"', "A0/_ground_" + "truth.json"):
        assert OUR_DOCS.search(bad), bad
    for ok in ('CORVANE / "A0/01_Customer_Draft_Spec"', 'CORVANE / "B0/05_Customer_PO"', "KVP-ECR-2408-02_Engineering"):
        assert not OUR_DOCS.search(ok), ok

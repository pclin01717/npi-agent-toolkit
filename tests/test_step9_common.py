"""STEP 9 共通：事件日、編號登記、作業規則當出處、版次種類、待填清單、工程師在對話裡改值（第 3 批）。"""
import datetime
import email
import email.utils
import json
import re

import docx
import openpyxl
import pdfplumber
import pytest

from npi import pipeline, registry, timeline
from npi.compare import compare
from npi.errors import NpiError
from npi.pending import pending_items
from npi.readers import rules
from npi.readers.master import source_texts
from npi.render.eml import people
from npi.sources import PENDING, field_errors, value_errors

from conftest import A0_PO, A0_SPEC, B0_ECR, INPUT_ROOT, fixture_of, run_real, write_judgement
from test_step6_full_chain import NPI, run_kalvara

DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def events(out_root, rev):
    return {e["event"]: e for e in pipeline.timeline(NPI, rev, INPUT_ROOT, out_root)}


def run_a0_all(out_root, date=None):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "A0", st, date=date)
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    for st in ("po", "supply"):
        run_real(out_root, "A0", st, date=date)


def a0_spec_stations(out_root, date="2026-11-02"):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "A0", st, date=date)


def until_release(out_root, rev, date="2026-11-02"):
    """跑到這個版次的工程發行 prepare 完（判讀檔還沒寫）。"""
    run_kalvara(out_root, date=date, until=(rev, "release"))
    pipeline.decide(NPI, rev, "全部接受", out_root)
    pipeline.prepare(NPI, rev, "release", INPUT_ROOT, out_root, date=date)


def render_release(out_root, rev, judgement):
    write_judgement(out_root, NPI, rev, "release", judgement)
    return pipeline.render(NPI, rev, "release", INPUT_ROOT, out_root)


def header_value(ws, label):
    for row in ws.iter_rows(min_col=1, max_col=1):
        if row[0].value == label:
            return ws.cell(row[0].row, 2).value
    raise AssertionError(f"找不到 {label}")


def days_of():
    return rules.timeline_days(INPUT_ROOT)


# STEP9-1
def test_STEP9_1_a0_timeline_has_events_and_basis(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    ev = events(out_root, "A0")
    assert ev["收到草稿 spec"]["date"] == "2026-06-29"
    for name in ("DFM 回覆日", "規格發行日", "成本送財務日", "備料通知日"):
        assert DATE.fullmatch(ev[name]["date"]), name
        assert ev[name]["basis"], name
    assert "RULES §2" in ev["DFM 回覆日"]["basis"]
    assert (out_root / NPI / "A0" / "timeline.json").exists()


def test_STEP9_1_a0_timeline_counts_working_days():
    d = {e["event"]: e["date"] for e in timeline.compute("initial", "2026-06-29", days_of())}
    assert d["DFM 回覆日"] == "2026-07-02"
    assert d["客戶同意"] == "2026-07-08"
    assert d["規格發行日"] == "2026-07-15"
    assert d["成本送財務日"] == "2026-07-17"
    d = {e["event"]: e["date"] for e in timeline.compute("initial", "2026-06-29", days_of(), po_date="2026-07-28")}
    assert (d["收到 PO"], d["備料通知日"]) == ("2026-07-28", "2026-07-29")


def test_STEP9_1_no_date_is_today(out_root):
    run_a0_all(out_root, date=None)
    today = datetime.date.today().isoformat()
    state = pipeline.load_state(NPI, out_root)
    dates = [s["date"] for s in state["revs"]["A0"]["stations"]]
    assert len(dates) == 5 and today not in dates
    assert not [p for p in (out_root / NPI / "A0").rglob("*") if today in p.name]


# STEP9-2
def b0_intaken(out_root):
    a0_spec_stations(out_root)
    pipeline.intake(B0_ECR, INPUT_ROOT, out_root)


def test_STEP9_2_b0_timeline_has_impact_assessment(out_root):
    b0_intaken(out_root)
    ev = events(out_root, "B0")
    assert ev["收到 ECR"]["date"] == "2026-08-14"
    assert ev["影響評估日"]["date"] == timeline.add_workdays("2026-08-14", 2)
    for name in ("規格發行日", "成本送財務日", "備料通知日"):
        assert DATE.fullmatch(ev[name]["date"]), name


def test_STEP9_2_ecr_gaps_basis_says_reused_from_initial(out_root):
    b0_intaken(out_root)
    ev = events(out_root, "B0")
    for name in ("客戶核准", "規格發行日", "成本送財務日"):
        assert "沿用初版" in ev[name]["basis"], name


# STEP9-3
def test_STEP9_3_each_output_date_matches_timeline(out_root):
    run_a0_all(out_root, date=None)
    ev = {k: v["date"] for k, v in events(out_root, "A0").items()}
    base = out_root / NPI / "A0"
    assert next((base / "dfm").glob("*.eml")).name.startswith(ev["DFM 回覆日"])
    release_day = ev["規格發行日"]
    spec = docx.Document(next((base / "release").glob("*.docx")))
    assert any(c.text == release_day for c in spec.tables[0].columns[1].cells)
    assert header_value(openpyxl.load_workbook(next((base / "release").glob("*BOM.xlsx")))["BOM"], "Date") == release_day
    with pdfplumber.open(next((base / "release").glob("*.pdf"))) as pdf:
        assert release_day in pdf.pages[0].extract_text()
    cost = openpyxl.load_workbook(next((base / "cost").glob("*.xlsx")))["Summary"]
    assert header_value(cost, "Date") == ev["成本送財務日"]
    assert next((base / "supply").glob("*.eml")).name.startswith(ev["備料通知日"])


def test_STEP9_3_eml_file_date_equals_header_date_10am(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", date=None)
    path = next((out_root / NPI / "A0" / "dfm").glob("*.eml"))
    msg = email.message_from_bytes(path.read_bytes())
    when = email.utils.parsedate_to_datetime(msg["Date"])
    assert path.name.startswith(when.date().isoformat())
    assert (when.hour, when.minute) == (10, 0)
    assert when.utcoffset() == datetime.timedelta(hours=8)


# STEP9-4
def test_STEP9_4_working_days_skip_weekend():
    assert timeline.add_workdays("2026-11-06", 1) == "2026-11-09"     # 星期五 + 1 = 星期一
    assert timeline.add_workdays("2026-11-07", 1) == "2026-11-09"     # 星期六起算
    assert timeline.add_workdays("2026-11-02", 0) == "2026-11-02"


def test_STEP9_4_events_in_order(out_root):
    run_kalvara(out_root, date=None)
    for rev in ("A0", "B0", "C0", "C1"):
        dates = [e["date"] for e in pipeline.timeline(NPI, rev, INPUT_ROOT, out_root)]
        assert dates == sorted(dates), rev
        for d in dates:
            assert datetime.date.fromisoformat(d).weekday() < 5, (rev, d)
    c1 = events(out_root, "C1")
    assert c1["成本送財務日"]["date"] == c1["備料通知日"]["date"]


def test_STEP9_4_weekend_override_rejected(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    with pytest.raises(NpiError, match="週"):
        pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root, date="2026-11-01")


# STEP9-5
def test_STEP9_5_override_moves_later_events(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", date=None)
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-07-14")
    ev = events(out_root, "A0")
    assert ev["規格發行日"]["date"] == "2026-07-14"
    assert "工程師指定" in ev["規格發行日"]["by"]
    assert ev["成本送財務日"]["date"] == timeline.add_workdays("2026-07-14", 2)


def test_STEP9_5_reviewed_station_date_unchanged(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", date=None)
    before = pipeline.load_state(NPI, out_root)["revs"]["A0"]["stations"][0]["date"]
    eml_before = next((out_root / NPI / "A0" / "dfm").glob("*.eml")).name
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-07-14")
    assert pipeline.load_state(NPI, out_root)["revs"]["A0"]["stations"][0]["date"] == before
    assert next((out_root / NPI / "A0" / "dfm").glob("*.eml")).name == eml_before
    assert events(out_root, "A0")["DFM 回覆日"]["date"] == before


# STEP9-6
def test_STEP9_6_compare_lists_timeline_differences(out_root):
    run_kalvara(out_root, date=None)
    for rev in ("A0", "B0", "C0", "C1"):
        diffs = compare(out_root, INPUT_ROOT, NPI, rev)
        assert any(d.startswith("時程／") for d in diffs), rev


# STEP9-7
def test_STEP9_7_suffix_must_change_from_previous_rev(out_root):
    until_release(out_root, "B0")
    j = fixture_of("B0", "release")
    j["lpc_pn"] = "LPC-FA32-127-8A"                    # A0 是 …-8A
    with pytest.raises(NpiError, match="字尾"):
        render_release(out_root, "B0", j)


def test_STEP9_7_minor_rev_also_changes_suffix(out_root):
    until_release(out_root, "C1")
    j = fixture_of("C1", "release")
    j["lpc_pn"] = "LPC-FA32-127-0C"                    # C0 是 …-0C；C1 是小改也要換
    with pytest.raises(NpiError, match="字尾"):
        render_release(out_root, "C1", j)


def test_STEP9_7_render_registers_product_pn(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    run_real(out_root, "A0", "release")
    hits = [e for e in registry.load(out_root) if e["number"] == "LPC-FA24-127-8A"]
    assert len(hits) == 1 and hits[0]["owner"] == f"{NPI} A0" and hits[0]["kind"] == "product_pn"


# STEP9-8
def test_STEP9_8_rerender_same_pn_no_new_entry(out_root):
    until_release(out_root, "A0")
    render_release(out_root, "A0", fixture_of("A0", "release"))
    count = len(registry.load(out_root))
    render_release(out_root, "A0", fixture_of("A0", "release"))
    entries = registry.load(out_root)
    assert len(entries) == count
    assert len([e for e in entries if e["number"] == "LPC-FA24-127-8A"]) == 1


# STEP9-9
def test_STEP9_9_pn_used_by_other_rev_rejected(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    entries = registry.register(registry.load(out_root), "LPC-FA24-127-8A", "product_pn", "NPI-26-999 A0", "2026-06-01")
    registry.save(out_root, entries)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    with pytest.raises(NpiError, match="LPC-FA24-127-8A"):
        render_release(out_root, "A0", fixture_of("A0", "release"))


def test_STEP9_9_pn_in_mm002_or_ll003_rejected(out_root):
    until_release(out_root, "A0")
    j = fixture_of("A0", "release")
    j["lpc_pn"] = "LPC-FA08-127-8A"                    # LL-003 P01 的料號
    with pytest.raises(NpiError, match="LPC-FA08-127-8A"):
        render_release(out_root, "A0", j)


# STEP9-10
def test_STEP9_10_registry_seeded_from_master_data(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    found = {e["number"]: e for e in json.loads((out_root / "registry.json").read_text(encoding="utf-8"))}
    assert found["PO-L26-0612"]["date"] == "2026-06-08"
    assert found["PO-L26-0612"]["kind"] == "lpc_po"
    assert found["LPC-FA08-127-8A"]["kind"] == "product_pn"


def test_STEP9_10_quote_number_hidden_before_its_date(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    assert "LPC-Q-26-0391" not in (out_root / "registry.json").read_text(encoding="utf-8")
    b0_intaken_after_a0 = out_root                      # 同一個 output，A0 跑完再交 B0
    for st in ("dfm", "release", "cost"):
        run_real(b0_intaken_after_a0, "A0", st)
    pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    found = {e["number"]: e for e in registry.load(out_root)}
    assert found["LPC-Q-26-0391"]["date"] == "2026-07-23"
    assert found["LPC-Q-26-0391"]["kind"] == "quote"


# STEP9-11
def test_STEP9_11_rules_sources_hold_one_value():
    s = source_texts(INPUT_ROOT)
    assert "22" in s["RULES §3 工作站費率 FPR"]
    assert "55" not in s["RULES §3 工作站費率 FPR"]
    assert "55" in s["RULES §3 工作站費率 CPM"]
    assert "5 %" in s["RULES §3 報廢率 扇出線"]
    assert "300" in s["RULES §3 成本批量 PM 陣列"]


def test_STEP9_11_cited_rule_number_accepted():
    s = source_texts(INPUT_ROOT)
    assert field_errors("費率", "22", ["RULES §3 工作站費率 FPR"], s) == []


# STEP9-12
def test_STEP9_12_wrong_number_for_cited_rule_rejected():
    s = source_texts(INPUT_ROOT)
    errors = field_errors("費率", "55", ["RULES §3 工作站費率 FPR"], s)
    assert errors and "55" in errors[0]


def test_STEP9_12_unknown_rule_section_rejected():
    s = source_texts(INPUT_ROOT)
    errors = field_errors("費率", "22", ["RULES §9 工作站費率 FPR"], s)
    assert errors and "不存在" in errors[0]


# STEP9-13（第 3 項「文件上寫出選的值和依據」要等 STEP 11 才有 Parameters，放在 test_step11_cost.py）
def test_STEP9_13_value_inside_range_accepted():
    s = source_texts(INPUT_ROOT)
    assert value_errors("成本批量", 1000, ["RULES §3 成本批量 一般"], s) == []
    assert value_errors("成本批量", 500, ["RULES §3 成本批量 一般"], s) == []
    assert value_errors("整備時間", 20, ["RULES §4 整備時間"], s) == []


def test_STEP9_13_value_outside_range_rejected():
    s = source_texts(INPUT_ROOT)
    errors = value_errors("成本批量", 2000, ["RULES §3 成本批量 一般"], s)
    assert errors and "500" in errors[0] and "1500" in errors[0].replace(",", "")


# STEP9-14
def test_STEP9_14_revision_kind_from_fixture(out_root):
    run_kalvara(out_root, until=("C1", "release"))
    kinds = {}
    for rev in ("A0", "B0", "C0", "C1"):
        reviewed = json.loads((out_root / NPI / rev / "dfm" / "reviewed.json").read_text(encoding="utf-8"))
        kinds[rev] = reviewed["revision_kind"]
    assert kinds == {"A0": "initial", "B0": "major", "C0": "major", "C1": "minor"}


def test_STEP9_14_minor_without_no_po_revision_rejected(out_root):
    b0_intaken(out_root)
    pipeline.prepare(NPI, "B0", "dfm", INPUT_ROOT, out_root, date="2026-11-02")
    j = fixture_of("B0", "dfm")
    j["revision_kind"] = {"value": "minor", "sources": ["ECR affected"]}
    write_judgement(out_root, NPI, "B0", "dfm", j)
    with pytest.raises(NpiError, match="revision_kind"):
        pipeline.render(NPI, "B0", "dfm", INPUT_ROOT, out_root)


def test_STEP9_14_a0_is_initial(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    reviewed = json.loads((out_root / NPI / "A0" / "dfm" / "reviewed.json").read_text(encoding="utf-8"))
    assert reviewed["revision_kind"] == "initial"


# STEP9-15
def count_pending(path):
    if path.suffix == ".xlsx":
        wb = openpyxl.load_workbook(path)
        return sum(str(c.value).count(PENDING) for ws in wb for row in ws.iter_rows() for c in row if c.value)
    if path.suffix == ".docx":
        d = docx.Document(path)
        n = sum(p.text.count(PENDING) for p in d.paragraphs)
        for t in d.tables:
            seen = set()
            for row in t.rows:
                for c in row.cells:
                    if id(c._tc) not in seen:
                        seen.add(id(c._tc))
                        n += c.text.count(PENDING)
        return n
    if path.suffix == ".eml":
        return email.message_from_bytes(path.read_bytes()).get_payload(decode=True).decode("utf-8").count(PENDING)
    return 0


def test_STEP9_15_pending_items_have_location(out_root):
    until_release(out_root, "A0")
    files = render_release(out_root, "A0", fixture_of("A0", "release"))
    items = pending_items(files)
    xlsx = [i for i in items if i["file"].endswith("BOM.xlsx")]
    assert xlsx and all(re.search(r"「.+」 [A-Z]+\d+", i["where"]) for i in xlsx)


def test_STEP9_15_pending_count_matches_documents(out_root):
    until_release(out_root, "A0")
    files = render_release(out_root, "A0", fixture_of("A0", "release"))
    expected = sum(count_pending(f) for f in files)
    assert expected > 0
    assert len(pending_items(files)) == expected


# 來自 PLANS
def test_PLANS_P51_minor_ecr_cost_and_supply_next_day():
    d = {e["event"]: e["date"] for e in timeline.compute("ecr", "2026-10-08", days_of(), minor=True)}
    nxt = timeline.add_workdays(d["規格發行日"], 1)
    assert d["成本送財務日"] == nxt and d["備料通知日"] == nxt
    assert "收到 PO" not in d


def test_PLANS_P50_po_date_only_after_intake(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    assert events(out_root, "A0")["收到 PO"]["by"] == "推算"
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    po = events(out_root, "A0")["收到 PO"]
    assert (po["date"], po["by"]) == ("2026-07-28", "客戶文件")


def test_PLANS_P52_date_option_means_engineer_override(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root, date="2026-07-01")
    dfm = events(out_root, "A0")["DFM 回覆日"]
    assert (dfm["date"], dfm["by"]) == ("2026-07-01", "工程師指定")
    saved = json.loads((out_root / NPI / "A0" / "timeline.json").read_text(encoding="utf-8"))
    assert saved["overrides"]["DFM 回覆日"] == "2026-07-01"


def test_PLANS_P52_rerender_keeps_date(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    write_judgement(out_root, NPI, "A0", "dfm", fixture_of("A0", "dfm"))
    first = pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)[0].name
    again = pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)[0].name
    assert first == again and first.startswith(events(out_root, "A0")["DFM 回覆日"]["date"])


def test_PLANS_P56_mm002_codes_always_used(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    used = registry.used(registry.load(out_root), as_of="2000-01-01", owner=f"{NPI} A0")
    assert "RM-VG-Q24-127" in used
    assert "PO-L26-0612" not in used                   # 2026-06-08 才有，2000 年還沒用


def test_PLANS_P60_tell_adds_eng_source(out_root):
    until_release(out_root, "A0")
    j = fixture_of("A0", "release")
    row = next(b for b in j["bom"] if b["item"] == "10.30")
    row["qty_per"], row["sources"] = 0.096, ["ENG-1"]
    with pytest.raises(NpiError, match="ENG-1"):
        render_release(out_root, "A0", j)
    assert pipeline.tell(NPI, "A0", "release", "10.30 光學膠用量 0.096 g", out_root) == "ENG-1"
    render_release(out_root, "A0", j)
    saved = json.loads((out_root / NPI / "A0" / "release" / "engineer.json").read_text(encoding="utf-8"))
    assert saved == [{"id": "ENG-1", "text": "10.30 光學膠用量 0.096 g"}]


def test_PLANS_P60_tell_refused_after_review(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    with pytest.raises(NpiError, match="已審"):
        pipeline.tell(NPI, "A0", "dfm", "改一下", out_root)


def test_PLANS_P68_people_json_matches_rules():
    from_rules = rules.people(INPUT_ROOT)
    p = people()
    assert p["sender"]["name"] == from_rules["NPI 負責人"]["name"] == "Alex Lin"
    assert p["scm"]["name"] == from_rules["供應鏈"]["name"] == "Nina Ho"
    assert from_rules["工程主管"]["name"] == "Jessica Liao"


def test_PLANS_P95_quote_number_from_customer_po(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    assert "LPC-Q-26-0391" not in {e["number"] for e in registry.load(out_root)}     # VERIFY STEP9-10 照舊
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    found = {e["number"]: e for e in registry.load(out_root)}
    assert found["LPC-Q-26-0391"]["date"] == "2026-07-23" and found["LPC-Q-26-0391"]["kind"] == "quote"


def test_PLANS_P95_superseded_quote_does_not_take_next_date():
    from npi.readers.po import quote_refs, read_po
    from conftest import KALVARA
    refs = quote_refs(read_po(KALVARA / "C0/05_Customer_PO/KVP-PO-7700-2614_Rev2.pdf")["text"])
    assert ("LPC-Q-26-0391-R2", "2026-10-01") in refs and ("LPC-Q-26-0391-R1", "2026-09-02") in refs
    assert not any(no == "LPC-Q-26-0391" and date != "2026-07-23" for no, date in refs)

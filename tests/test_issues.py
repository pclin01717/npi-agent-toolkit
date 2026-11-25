"""progress.md Issues 的回歸測試：每條先失敗、修好後通過。"""
import json
import re
import subprocess
import sys
from pathlib import Path

import docx
import openpyxl
import pytest

from npi import pipeline
from npi.compare import compare
from npi.errors import NpiError
from npi.pipeline import Ctx
from npi.readers import one_file
from npi.readers.master import read_ll003, read_mm002, read_pl
from npi.readers.ours import read_spec_doc
from npi.sources import field_errors, number_errors
from npi.stations import cost, dfm, release
from npi.stations.po_check import po_findings
from npi.readers.po import read_po

from conftest import (A0_PO, A0_SPEC, INPUT_ROOT, PROJECT, fixture_of, run_real, write_judgement)

NPI = "NPI-26-097"
CASE = "NPI-26-097_CPO_Fiber_Array"
CODE = re.compile(r"^[A-Z0-9][A-Za-z0-9-]*$")


# Fixes #1：表格下方的註解列不能當成料號或條目
def test_issue1_master_readers_skip_footnote_rows():
    pl = read_pl(INPUT_ROOT)
    for key in list(pl["materials"]) + list(pl["services"]) + list(read_mm002(INPUT_ROOT)):
        assert CODE.match(key), key
    for key in read_ll003(INPUT_ROOT):
        assert re.match(r"^(LL-\d+|DR-\d+|P\d+)$", key), key


# Fixes #2：先交 PO 再交客戶文件，排程不能互等
def test_issue2_po_before_spec_keeps_station_order(out_root):
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    names = [s["name"] for s in pipeline.load_state(NPI, out_root)["revs"]["A0"]["stations"]]
    assert names == ["dfm", "release", "cost", "po", "supply"]


# Fixes #3：reopen 之後，下游不能拿舊的檔案直接 render，也讀不到舊的審過結果
def test_issue3_render_refused_when_upstream_reopened(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    run_real(out_root, "A0", "release")
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    with pytest.raises(NpiError, match="DFM"):
        pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    assert not (out_root / NPI / "A0" / "release" / "reviewed.json").exists()


# Fixes #4：工程師在正式 spec 改了關鍵參數，BOM／圖面／STEP 不會跟著變 → approve 要擋下
def test_issue4_approve_refuses_edited_spec_param(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "release", fixture_of("A0", "release"))
    files = pipeline.render(NPI, "A0", "release", INPUT_ROOT, out_root)
    spec = next(f for f in files if f.suffix == ".docx")
    d = docx.Document(spec)
    for row in d.tables[1].rows:
        if row.cells[0].text == "Channels":
            row.cells[1].text = "25"
    d.save(spec)
    with pytest.raises(NpiError, match="channels"):
        pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)


# Fixes #5：Make/Buy 只有 Make、Buy（Kit 會被成本和備料默默略過）
def test_issue5_kit_rejected(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    facts = json.loads(pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root).read_text(encoding="utf-8"))
    j = fixture_of("A0", "release")
    j["bom"][0]["make_buy"] = "Kit"
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), "A0", "release", INPUT_ROOT, out_root, "2026-11-02")
    assert any("Make/Buy" in e for e in release.check(ctx, facts, j))


# Fixes #6：找不到客戶文件時，錯誤要指出資料夾
def test_issue6_missing_file_is_npi_error(tmp_path):
    with pytest.raises(NpiError, match=str(tmp_path.name)):
        one_file(tmp_path, "*.docx")


# Fixes #7：日期不能拆成年、月、日當成可用數字
def test_issue7_date_parts_not_available_numbers():
    assert number_errors("10 weeks, 15 days", ["due 2026-10-15"]) == ["10", "15"]


# Fixes #8：文字裡提到的 §、LL、DR、R、CH 編號要存在
@pytest.mark.parametrize("mention", ["§13", "LL-99", "DR-99", "R-99", "CH9"])
def test_issue8_mentioned_codes_must_exist(mention):
    sources = {"QM-021 §4.1": "x", "LL-003 LL-01": "x", "LL-003 DR-01": "x", "R-01": "x", "CH1": "x"}
    errors = field_errors("欄位", f"See {mention} for details.", ["QM-021 §4.1"], sources)
    assert any(mention in e for e in errors)
    assert field_errors("欄位", "See §4.1, LL-01, DR-01, R-01 and CH1.", ["QM-021 §4.1"], sources) == []


# Fixes #9：會印進文件的欄位都要查數字
def test_issue9_title_and_po_change_checked(out_root):
    ctx = Ctx(INPUT_ROOT, out_root, NPI, CASE, "A0", "dfm", "2026-11-02")
    ctx.station_dir.mkdir(parents=True)
    facts = dfm.prepare(ctx)
    j = fixture_of("A0", "dfm")
    j["items"][0]["title"] = "Core pitch on 99 channels"
    assert any("title" in e and "99" in e for e in dfm.check(ctx, facts, j))
    ctx_b = Ctx(INPUT_ROOT, out_root, NPI, CASE, "B0", "dfm", "2026-11-02")
    ctx_b.station_dir.mkdir(parents=True)
    facts_b = dfm.prepare(ctx_b)
    jb = fixture_of("B0", "dfm")
    assert dfm.check(ctx_b, facts_b, jb) == []
    jb["po_change"] = "Change order for 7,777 pcs."
    assert any("po_change" in e and "7777" in e.replace(",", "") for e in dfm.check(ctx_b, facts_b, jb))


def test_issue9_bom_remark_and_section_title_checked(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    facts = json.loads(pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root).read_text(encoding="utf-8"))
    j = fixture_of("A0", "release")
    j["bom"][0]["remark"] = "Use 9876 pcs safety stock"
    j["spec_sections"][0]["title"] = "Scope 4321"
    ctx = pipeline._ctx(pipeline.load_state(NPI, out_root), "A0", "release", INPUT_ROOT, out_root, "2026-11-02")
    errors = release.check(ctx, facts, j)
    assert any("9876" in e for e in errors) and any("4321" in e for e in errors)


# Fixes #10：intake 回報用中文的文件種類
def test_issue10_intake_reports_chinese_kind(out_root):
    r = subprocess.run([sys.executable, "-m", "npi", "--out-root", str(out_root), "intake", str(A0_SPEC)],
                       cwd=PROJECT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "NPI-26-097／A0／客戶草稿 spec" in r.stdout


# Fixes #11：compare 也要比 DFM 站
def test_issue11_compare_includes_dfm(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm")
    diffs = compare(out_root, INPUT_ROOT, NPI, "A0")
    assert any(d.startswith("DFM") and "R-05" in d for d in diffs)    # fixture 沒列 R-05，答案有


# Fixes #12：我方客戶版次不明時，要寫出「無法比較」
def test_issue12_unknown_cust_rev_reported():
    po = read_po(A0_PO)
    ours = {"LPC-FA24-127-8A": {"rev": "A0", "cust_rev": None, "spec": "LPC-PS-26097 Rev A0"}}
    assert any("客戶版次" in f and "無法比較" in f for f in po_findings(po, ours, None))


# Fixes #13：成本站拿得到已審的 PO 數量（P13：spec／ECR 沒寫就用 PO 數量）
def test_issue13_cost_facts_include_latest_po(out_root):
    root = out_root / NPI
    (root / "B0" / "release").mkdir(parents=True)
    (root / "B0" / "release" / "reviewed.json").write_text(json.dumps(
        {"bom": [], "lpc_pn": "LPC-X", "description": "x", "files": {"bom": "b.xlsx"}}))
    (root / "A0" / "po").mkdir(parents=True)
    (root / "A0" / "po" / "reviewed.json").write_text(json.dumps(
        {"po": {"po_no": "KVP-PO-7700-2614", "rev": 0, "total_qty": 2000}}))
    ctx = Ctx(INPUT_ROOT, out_root, NPI, CASE, "B0", "cost", "2026-11-02")
    ctx.station_dir.mkdir(parents=True)
    facts = cost.prepare(ctx)
    assert "PO" in facts["sources"] and "2000" in facts["sources"]["PO"]


# Fixes #14（突變測試沒抓到）：05_Customer_PO 底下不是 PDF 的檔案不算客戶 PO
def test_issue14_po_folder_non_pdf_rejected(tmp_path):
    from npi.intake import identify
    path = tmp_path / "NPI-26-097_X" / "A0" / "05_Customer_PO" / "po.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    with pytest.raises(NpiError, match="po.docx.*不是客戶文件"):
        identify(path, tmp_path)


# Fixes #15（突變測試沒抓到）：購買數量剛好等於分段門檻時用那一段（P13 的「≥」）
def test_issue15_price_break_boundary():
    from npi.stations.cost import pick_price
    price = {"base": 3.1, "breaks": [(2000, 2.85), (None, None)]}
    assert pick_price(price, 2000) == (2.85, "Break 1")
    assert pick_price(price, 1999) == (3.1, "Base")


# Fixes #16（使用者核准改表 D）：代號只認「大寫開頭＋連字號／點」或「1～3 個字母＋1～2 位數字」，其他字母開頭的數字要查
def test_issue16_letter_prefixed_numbers_checked():
    assert number_errors("USD5000, x500, 交期12週, Approx.15, Ø0.9", []) == ["5000", "500", "12", "15", "0.9"]
    codes = "R-03 §4.1 G.657.A2 MPO-12 A0 X1 CH1 P01 R6.3 LPC-FA24-127-8A DR-13 KVP-ECR-2408-01"
    assert number_errors(codes, []) == []


# Fixes #17（使用者核准改表 D）：上一版只能引用到單一參數或單一 BOM 列，不能引用整份 JSON
def test_issue17_previous_release_sources_are_per_field():
    from npi.params import prev_sources
    previous = {"params": {"pigtail_mm": 800, "connector": "2 x MPO-12"},
                "bom": [{"part_no": "RM-LD-Q24", "description": "Lid 5.0 x 5.0 x 0.7 mm", "qty_per": 1, "uom": "pcs"}]}
    s = prev_sources(previous)
    assert s == {"PREV pigtail_mm": "800", "PREV connector": "2 x MPO-12",
                 "PREV BOM RM-LD-Q24": "Lid 5.0 x 5.0 x 0.7 mm | qty 1 pcs"}
    assert field_errors("x", "pigtail 500 mm", ["PREV pigtail_mm"], s) != []


# Fixes #19（STEP8-10 重考）：PO 表頭排版不同（「PURCHASE ORDER Rev 0」、PO 號和日期同一行、沒有 Date 字樣）也要讀得出來
def test_issue19_corvane_po_header_layout():
    from conftest import CORVANE
    po = read_po(CORVANE / "A0/05_Customer_PO/CVN-PO-55-30418_Rev0.pdf")
    assert (po["po_no"], po["rev"], po["date"], po["total_qty"]) == ("CVN-PO-55-30418", 0, "2026-08-06", 3000)
    assert [s["qty"] for s in po["schedule"]] == [50, 950, 1000, 1000]
    assert {(s["cust_rev"], s["lpc_pn"]) for s in po["schedule"]} == {("A", "LPC-FO36-M12LS-A")}
    for rev, n in (("B0", 1), ("C0", 2)):
        later = read_po(CORVANE / f"{rev}/05_Customer_PO/CVN-PO-55-30418_Rev{n}.pdf")
        assert (later["po_no"], later["rev"]) == ("CVN-PO-55-30418", n) and later["schedule"]


# Fixes #22（突變測試沒抓到）：每個 MPO 的芯數要能分給整數條支線（36 芯、3 個 MPO、4 條支線 → 每 MPO 12 芯分不成 9 芯一條）
def test_issue22_fibres_per_mpo_must_split_into_legs():
    from npi.params import fanout_errors
    v = {"fibres": 36, "trunk_conn_qty": 3, "leg_conn_qty": 4, "polarity": "Method A"}
    assert any("整除" in e for e in fanout_errors(v))


# Fixes #23（突變測試沒抓到）：極性只收 Method A／B（P39）
def test_issue23_unknown_polarity_rejected():
    from npi.params import fanout_errors
    v = {"fibres": 36, "trunk_conn_qty": 3, "leg_conn_qty": 36, "polarity": "Method C"}
    assert any("polarity" in e and "Method C" in e for e in fanout_errors(v))


# Fixes #24（突變測試沒抓到）：ECR 版改了文字參數（接頭種類）也要對到 CH
def test_issue24_text_param_change_needs_ch(out_root):
    from test_step8_fanout import check_b0, fixture_of
    judgement = fixture_of("B0", "release", "NPI-26-104")
    judgement["params"]["trunk_connector"] = {"value": "MPO-12 APC male (pinned), elite grade", "sources": []}
    assert any("trunk_connector" in e and "CH" in e for e in check_b0(out_root, judgement))


# Fixes #25（突變測試沒抓到）：fan-out 不檢查文字裡的通道數（P43）
def test_issue25_fanout_text_channel_count_not_checked(out_root):
    from test_step8_fanout import a0_fixture, check_a0
    judgement = a0_fixture()
    judgement["spec_sections"].append({"title": "Trunk", "text": "Each MPO carries 12 channels.", "sources": ["R-02"]})
    assert check_a0(out_root, judgement) == []


# Fixes #27（第 2 批唯讀審查）：spec 關鍵參數表認不出是哪種產品時，要直接說認不出類型，不要當成光纖陣列再報「不認得的列」
def test_issue27_unknown_key_table_type_reported(out_root):
    from test_step8_fanout import EXPECTED_A0, render_a0
    path = render_a0(out_root)[EXPECTED_A0[0]]
    d = docx.Document(path)
    d.tables[1].rows[1].cells[0].text = "Ports"
    d.save(path)
    with pytest.raises(NpiError, match="認不出.*產品"):
        read_spec_doc(path)


# Fixes #21（STEP8-10 重考）：料號寫「待工程師填寫」的 BOM 列不能當成料號——不產生 PREV BOM 出處、不算進新增／取消，另列成「料號待填」
def test_issue21_pending_part_number_not_used_as_part_number():
    from npi.params import prev_sources
    from npi.sources import PENDING
    from npi.stations.supply import bom_changes
    row = {"part_no": PENDING, "description": "MPO-12 APC female elite kit", "make_buy": "Buy", "qty_per": 3, "uom": "pcs"}
    known = {"part_no": "PP-LC-APC-DU", "description": "LC duplex kit", "make_buy": "Buy", "qty_per": 18, "uom": "pcs"}
    assert f"PREV BOM {PENDING}" not in prev_sources({"params": {}, "bom": [row, known]})
    dropped = bom_changes([row, known], [known])
    assert PENDING not in dropped["removed"] and dropped.get("pending_pn", []) == []
    added = bom_changes([known], [known, row])
    assert PENDING not in added["added"] and added.get("pending_pn") == ["MPO-12 APC female elite kit"]


# Fixes #28（第 3 批突變測試沒抓到）：基本工序的工作站順序不對（沒少工序）也要報錯（P63）
def test_issue28_base_routing_order_checked(out_root):
    from test_step10_bom import check_of
    from conftest import fixture_of
    j = fixture_of("A0", "release")
    cur = next(o for o in j["routing"] if o["work_centre"] == "CUR")
    pol = next(o for o in j["routing"] if o["work_centre"] == "POL")
    cur["work_centre"], pol["work_centre"] = "POL", "CUR"          # 固化、研磨對調
    assert any("基本工序" in e for e in check_of(out_root, "A0", j))


# Fixes #29（第 3 批突變測試沒抓到）：有 PM 又有鍍膜時，兩個 PM 列都是候選（表 J）
def test_issue29_pm_with_coating_lists_both_pm_rows():
    from npi import costing
    from npi.readers.master import source_texts
    s = costing.scrap_rate("Fiber_Array", 16, ["PM", "coating"], source_texts(INPUT_ROOT))
    assert s["value"] == "待工程師填寫"
    assert set(s["candidates"]) == {"RULES §3 報廢率 PM 陣列", "RULES §3 報廢率 PM 陣列，端面在空氣中或有鍍膜"}


# Fixes #30（第 3 批突變測試沒抓到）：讀回 BOM 的展開用量要乘上一階的用量（P61）
def test_issue30_read_bom_ext_qty_multiplies_parent(out_root):
    import openpyxl
    from test_step10_bom import bom_of, cell_of
    from npi import pipeline
    path = bom_of(out_root, "A0")
    wb = openpyxl.load_workbook(path)
    cell_of(wb["BOM"], "LPC-FA24-PKG", "Qty per Parent").value = 2   # 分組列（item 60）改成 2
    wb.save(path)
    pipeline.approve(NPI, "A0", "release", INPUT_ROOT, out_root)
    rows = {b["part_no"]: b for b in json.loads((out_root / NPI / "A0" / "release" / "reviewed.json").read_text(encoding="utf-8"))["bom"]}
    assert rows["PP-CAP-MPOF"]["ext_qty"] == 4                        # 2（每組）× 2（組數）
    assert rows["PP-CAP-MPOF"]["qty_per"] == 2


# ---- 第 3 批唯讀審查（progress 第 49 次）----
def _non_formula_pending(path):
    """獨立的數法：只數不是公式的格（xlsx），內容含「待工程師填寫」幾次。"""
    import openpyxl
    wb = openpyxl.load_workbook(path)
    return sum(str(c.value).count("待工程師填寫") for ws in wb for row in ws.iter_rows() for c in row
               if c.value is not None and not str(c.value).startswith("="))


# Fixes #31：待填清單不能把公式、標籤、NRE 的依據欄算進去（VERIFY STEP9-15，每一站）
def test_issue31_pending_list_counts_real_pending_cells_every_station(out_root):
    from npi.pending import pending_items
    from test_step9_common import count_pending, run_a0_all
    run_a0_all(out_root)
    for station in ("dfm", "release", "cost", "po", "supply"):
        files = [p for p in (out_root / NPI / "A0" / station).iterdir() if p.suffix in (".xlsx", ".docx", ".eml", ".md")]
        expected = sum(_non_formula_pending(f) if f.suffix == ".xlsx" else
                       f.read_text(encoding="utf-8").count("待工程師填寫") if f.suffix == ".md" else count_pending(f)
                       for f in files)
        assert len(pending_items(files)) == expected, station
    cost = next((out_root / NPI / "A0" / "cost").glob("*.xlsx"))
    import openpyxl
    ws = openpyxl.load_workbook(cost)["Summary"]
    nre = [r for r in ws.iter_rows(min_row=28, max_row=31, values_only=True)]
    assert all(r[3] != "待工程師填寫" for r in nre)                  # 依據欄不重複寫待填


# Fixes #32：工程師指定的日期不能早於前一個事件（VERIFY STEP9-4）
def test_issue32_override_earlier_than_previous_event_rejected(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "dfm", date=None)                       # DFM 回覆日 2026-07-02
    pipeline.decide(NPI, "A0", "全部接受", out_root)
    with pytest.raises(NpiError, match="早於"):
        pipeline.prepare(NPI, "A0", "release", INPUT_ROOT, out_root, date="2026-06-30")


# Fixes #33：直接在 xlsx 清掉一個輸入格，Summary 也要顯示不完整（VERIFY STEP11-3、P70）
def test_issue33_blank_input_without_status_makes_summary_incomplete(out_root):
    import openpyxl
    from pycel import ExcelCompiler
    from npi.render import xlsx_out as X
    from test_step11_cost import cost_file, run_kalvara_filled
    run_kalvara_filled(out_root, until=("A0", "po"))
    path = cost_file(out_root, "A0")
    wb = openpyxl.load_workbook(path)
    ws = wb["Material"]
    for row in ws.iter_rows(min_row=9):
        if row[1].value == "RM-VG-Q24-127":
            row[4].value = None                                       # 只清用量，狀態欄沒寫待填
    wb.save(path)
    assert ExcelCompiler(filename=str(path)).evaluate(X.SUMMARY_REF["total"]) == X.INCOMPLETE


# Fixes #34：工具自己登記的成品料號不套日期過濾（VERIFY STEP9-7、9-9）
def test_issue34_tool_registered_pn_always_used():
    from npi import registry
    entries = registry.register([], "LPC-FA32-127-8B", "product_pn", "NPI-26-097 B0", "2026-08-31")
    assert "LPC-FA32-127-8B" in registry.used(entries, as_of="2026-06-29", owner="NPI-26-097 A0")


# Fixes #35：Delta 的參數變動列只寫有變的參數（BRIEF 3-7）
def test_issue35_parameter_row_names_changed_parameters(out_root):
    import openpyxl
    from test_step11_cost import cost_file, run_kalvara_filled
    run_kalvara_filled(out_root, until=("B0", "po"))
    ws = openpyxl.load_workbook(cost_file(out_root, "B0"))["Delta vs A0"]
    row = next(r for r in ws.iter_rows(values_only=True) if r[0] == "參數變動")
    assert "成本批量" in row[2] and "計價數量" in row[2]
    assert "報廢率" not in row[2]                                    # A0、B0 都是 0.1


# Fixes #36：成本站可以引用 PO 的每一批（PLANS P72）
def test_issue36_cost_sources_include_po_lines(out_root):
    from test_step11_cost import run_kalvara_filled
    run_kalvara_filled(out_root, until=("B0", "release"))
    run_real(out_root, "B0", "release")
    facts = json.loads(pipeline.prepare(NPI, "B0", "cost", INPUT_ROOT, out_root, date="2026-11-02").read_text(encoding="utf-8"))
    assert "PO line 1.1" in facts["sources"] and "100" in facts["sources"]["PO line 1.1"]


# Fixes #37：作業規則一個出處只放一個值（P57）
def test_issue37_rules_list_items_hold_one_value():
    import re
    from npi.readers.rules import rule_sources
    s = rule_sources(INPUT_ROOT)
    hits = {k: v for k, v in s.items() if k.startswith("RULES §5 一次性驗證")}
    assert len(hits) == 3
    for v in hits.values():
        assert len(re.findall(r"\d+", v)) == 1, v


# Fixes #39：待填和數字之間的變化不算 ECR 變更（Change Summary，P66）
def test_issue39_pending_to_number_is_not_a_change():
    from npi.stations import release
    old = [{"item": "10.30", "part_no": "CM-EP-UV365", "qty_per": 0.1}]
    assert release.bom_diff(old, [{"item": "10.30", "part_no": "CM-EP-UV365", "qty_per": "待工程師填寫"}]) == []
    assert release.bom_diff([{"item": "10.30", "part_no": "CM-EP-UV365", "qty_per": None}],
                            [{"item": "10.30", "part_no": "CM-EP-UV365", "qty_per": 0.1}]) == []
    ops = [{"op": "10", "work_centre": "FPR", "setup_min": 20, "run_min": None}]
    new = [{"op": "10", "work_centre": "FPR", "setup_min": {"value": 20}, "run_min": {"value": 5}}]
    assert release.routing_diff(ops, new) == []


# Fixes #38：小改的成本有變時，Delta 看得出毛利率從多少變多少（VERIFY STEP11-14）
def test_issue38_minor_cost_change_shows_margin_change(out_root):
    from test_step11_cost import (QTY, RUN, SCRAP, cost_file, evaluate, filled_release, reviewed, run_kalvara_filled)
    from npi.render import xlsx_out as X
    run_kalvara_filled(out_root, until=("C1", "release"))
    pipeline.decide(NPI, "C1", "全部接受", out_root)
    pipeline.prepare(NPI, "C1", "release", INPUT_ROOT, out_root, date="2026-11-02")
    eng = pipeline.tell(NPI, "C1", "release", f"測試用：單件時間 {RUN} 分鐘，待填用量 {QTY}，CH1 尾纖加長後光纖用量 0.2", out_root)
    j = filled_release(fixture_of("C1", "release"), eng)
    fibre = next(b for b in j["bom"] if b["part_no"] == "RM-FB-G657A2")
    fibre["qty_per"] = 0.2                                            # CH1：尾纖 500 → 520 mm，光纖用量變多
    j["change_map"] = {"RM-FB-G657A2": "CH1"}
    write_judgement(out_root, NPI, "C1", "release", j)
    pipeline.render(NPI, "C1", "release", INPUT_ROOT, out_root)
    pipeline.approve(NPI, "C1", "release", INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "C1", "cost", INPUT_ROOT, out_root, date="2026-11-02")
    c = fixture_of("C1", "cost")
    c["scrap_rate_override"] = {"value": SCRAP, "sources": [pipeline.tell(NPI, "C1", "cost", f"測試用：報廢率 {SCRAP}", out_root)]}
    write_judgement(out_root, NPI, "C1", "cost", c)
    pipeline.render(NPI, "C1", "cost", INPUT_ROOT, out_root)
    pipeline.approve(NPI, "C1", "cost", INPUT_ROOT, out_root)
    c0, c1 = reviewed(out_root, "C0"), reviewed(out_root, "C1")
    assert c1["total"] > c0["total"] and c1["quote"] == c0["quote"] and c1["margin"] < c0["margin"]
    path = cost_file(out_root, "C1")
    assert evaluate(path, X.DELTA_MARGIN_REF.format(prev="C0", col="B")) == pytest.approx(c0["margin"])
    assert evaluate(path, X.DELTA_MARGIN_REF.format(prev="C0", col="C")) == pytest.approx(c1["margin"])


# Fixes #40：其他都填齊時，只有一個料查不到價，總成本也要是不完整（VERIFY STEP3-2；補回 test_STEP3_2 的意思）
def test_issue40_missing_price_alone_makes_total_incomplete(out_root):
    from test_step11_cost import run_station, reviewed
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    import test_step11_cost as T
    original = T.fixture_of

    def with_extra(rev, station, npi=NPI):
        j = original(rev, station, npi)
        if station == "release":
            j["bom"].append({"item": "70", "part_no": "RM-XX-NOTEXIST", "description": "Unknown part", "make_buy": "Buy",
                             "qty_per": 1, "uom": "pcs", "sources": ["R-01"], "op": "110", "category": "RM",
                             "category_sources": ["R-01"]})
        return j
    T.fixture_of = with_extra
    try:
        run_station(out_root, "A0", "release")
        run_station(out_root, "A0", "cost")
    finally:
        T.fixture_of = original
    r = reviewed(out_root, "A0")
    missing = [l for l in r["lines"] if l["unit_price"] is None]
    assert [l["part_no"] for l in missing] == ["RM-XX-NOTEXIST"]          # 只缺這一個價
    assert r["complete"] is False and r["total"] is None


def test_issue45_manager_relays_document_kind():
    """#45：VERIFY STEP0-1 要總管告訴工程師收到的是哪種客戶文件；intake 印出的那一行有種類，總管說明要叫它轉述。"""
    text = (Path(__file__).resolve().parents[1] / ".claude" / "commands" / "npi.md").read_text(encoding="utf-8")
    step1 = text.split("## 1.")[1].split("## 2.")[0]
    assert "文件種類" in step1 and "intake" in step1


def _bom_sheet(path):
    from test_step10_bom import table
    return table(openpyxl.load_workbook(path)["BOM"])


def test_issue41_change_summary_complete(out_root):
    """#41：VERIFY STEP10-9 要每個新增、取消、用量改變的料都列出並對到 CH。
    這裡不用 release.bom_diff，自己從 A0、B0 兩份 BOM 工作表算差異，要跟 Change Summary 的 BOM 列一模一樣。"""
    from test_step10_bom import bom_of, table
    j = fixture_of("B0", "release")
    flag = next(b for b in j["bom"] if b["part_no"] == "PP-LBL-FLAG")    # 測試資料 A0→B0 沒有用量改變，自己造一個
    flag["qty_per"] = 2
    j["change_map"]["PP-LBL-FLAG"] = "CH1"
    b0 = bom_of(out_root, "B0", j)
    a0 = next((out_root / "NPI-26-097" / "A0" / "release").glob("*_BOM.xlsx"))

    def keyed(path):
        return {str(r["Part No."]): r["Qty per Parent"] for r in _bom_sheet(path)
                if str(r["Item No."]) != "0" and r["Part No."] not in (None, "待工程師填寫")}
    old, new = keyed(a0), keyed(b0)
    expected = {("Removed", p) for p in old if p not in new} | {("Added", p) for p in new if p not in old}
    expected |= {("Qty changed", p) for p in new if p in old and isinstance(old[p], (int, float))
                 and isinstance(new[p], (int, float)) and old[p] != new[p]}
    rows = [r for r in table(openpyxl.load_workbook(b0)["Change Summary"])
            if not str(r["Part No. / Op."]).startswith("Op ")]
    assert {(r["Change"], str(r["Part No. / Op."])) for r in rows} == expected
    assert len(rows) == len(expected)
    assert all(r["CH"] for r in rows)
    assert any(c == "Qty changed" for c, _ in expected)      # 測試資料裡真的有用量改變，否則這條測不到那一類


def test_issue46_cost_sheet_material_row_formula(out_root):
    """#46（STEP3-3）：成本表 xlsx 上 PP-MPO12-APC-F 那一列的金額（用 pycel 算公式）＝ 用量 2 × 級距價 5.2。
    原本的 test_STEP3_3 讀回的是 Python 模型，不是表上那一列。"""
    from test_step11_cost import cost_file, material, run_kalvara_filled
    from pycel import ExcelCompiler
    run_kalvara_filled(out_root, until=("A0", "po"))
    path = cost_file(out_root, "A0")
    ws = openpyxl.load_workbook(path)["Material"]
    heads = {c.value: c.column_letter for c in ws[8] if c.value}
    row = next(c.row for c in ws[heads["Material Code"]] if c.value == "PP-MPO12-APC-F")
    cost_col = heads["Extended (USD / pc)"]
    assert str(ws[f"{cost_col}{row}"].value).startswith("=")                  # 是公式，不是寫死的數字
    assert material(path)["PP-MPO12-APC-F"]["Ext. Qty / pc"] == 2
    value = ExcelCompiler(filename=str(path)).evaluate(f"Material!{cost_col}{row}")
    assert value == pytest.approx(2 * 5.2)


def test_issue46_supply_email_quantities(out_root):
    """#46（STEP5-2）：備料通知信上每個 Buy 料的需求量 ＝ 每顆用量 × PO 總數 2,000（自己用測試資料算，不讀 facts.json）。"""
    from test_step5_supply import a0_supply, body_of
    path, _ = a0_supply(out_root)
    _, body = body_of(path)
    lines = {ln.split()[1]: ln for ln in body.splitlines() if ln.startswith("- ") and "/FAU ->" in ln}
    checked = 0
    for b in fixture_of("A0", "release")["bom"]:           # 測試資料的上一階用量都是 1，展開用量＝每顆用量
        qty = b.get("qty_per")
        if b.get("make_buy") != "Buy" or not isinstance(qty, (int, float)):
            continue
        shown = lines[b["part_no"]].split("->")[1].split()[0]
        assert shown == f"{qty * 2000:,}".replace(".0", ""), (b["part_no"], shown)
        checked += 1
    assert checked >= 5


def test_issue47_spec_part_no_label(tmp_path):
    """#47：客戶草稿 spec 的料號欄寫「Part no.」（NPI-26-124）也要讀得到，不只「<客戶> P/N」。"""
    from npi.readers.spec import read_spec
    d = docx.Document(A0_SPEC)
    cell = next(c for t in d.tables for r in t.rows for c in r.cells if c.text.strip() == "Kalvara P/N")
    cell.paragraphs[0].runs[0].text = "Part no."
    for run in cell.paragraphs[0].runs[1:]:
        run.text = ""
    path = tmp_path / "spec.docx"
    d.save(path)
    assert read_spec(path)["meta"]["part_no"] == "KVP-FAU-2408"


def test_P96_dfm_raises_direction_without_reference():
    """PLANS P96（NPI-26-124 R-08 漏判）：方向／位置描述沒寫觀看基準時，DFM 要列出來請客戶確認。"""
    text = (PROJECT / ".claude/agents/npi-dfm.md").read_text()
    assert "觀看基準" in text and "Medium" in text.split("觀看基準")[1][:200]


def test_P97_cost_general_lot_is_500():
    """PLANS P97：一般光纖陣列的成本批量用 500（兩個案子的答案都是 500）。"""
    text = (PROJECT / ".claude/agents/npi-cost.md").read_text()
    line = next(l for l in text.splitlines() if l.startswith("- 成本批量"))
    assert "500" in line and "一律" in line


# Fixes #48：reopen 把舊結果搬出站資料夾（PLANS P100），站代理看不到；第二次 reopen 不能蓋掉第一次的
def test_issue48_reopen_moves_old_results_out_of_station_folder(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    station = out_root / NPI / "A0" / "dfm"
    run_real(out_root, "A0", "dfm")
    first = {f: (station / f).read_bytes() for f in ("reviewed.json", "facts.json")}
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    assert not list(station.glob("*reviewed*.json")) and not list(station.glob("*facts*.json"))
    old1 = out_root / NPI / "A0" / "_reopened" / "dfm_1"
    assert {f: (old1 / f).read_bytes() for f in first} == first
    run_real(out_root, "A0", "dfm")
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    assert {f: (old1 / f).read_bytes() for f in first} == first
    assert (out_root / NPI / "A0" / "_reopened" / "dfm_2" / "reviewed.json").exists()
    assert not list(station.glob("*.reopened.json"))


# Fixes #58：P100 的下游站（同一版次和後面版次）也要搬；只 prepare 過的站搬 facts；沒有檔案的站不建空資料夾
def test_issue58_reopen_moves_downstream_and_later_revisions(out_root, fake_stations):
    from conftest import B0_ECR
    from test_step0_manager import run_station
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for s in ("dfm", "release", "cost"):
        run_station(out_root, "A0", s)
    pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    run_station(out_root, "B0", "dfm")
    pipeline.decide(NPI, "B0", "全部接受", out_root)
    pipeline.prepare(NPI, "B0", "release", INPUT_ROOT, out_root, date="2026-11-02")
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    # #60 之後 judgement.json 也會搬，所以只看 reviewed／facts 在不在（使用者 2026-11-24 決定 P100 範圍）
    for rev, s, moved in (("A0", "dfm", {"reviewed.json", "facts.json"}), ("A0", "release", {"reviewed.json", "facts.json"}),
                          ("A0", "cost", {"reviewed.json", "facts.json"}), ("B0", "dfm", {"reviewed.json", "facts.json"}),
                          ("B0", "release", {"facts.json"})):
        names = {f.name for f in (out_root / NPI / rev / "_reopened" / f"{s}_1").iterdir()}
        assert moved <= names and ({"reviewed.json", "facts.json"} - moved).isdisjoint(names), (rev, s, names)
        assert ("judgement.json" in names) == (s != "release" or rev == "A0"), (rev, s, names)   # #60：判讀檔也搬（B0 release 只 prepare 過，沒有判讀檔）
        assert not list((out_root / NPI / rev / s).glob("*reviewed*")) and not list((out_root / NPI / rev / s).glob("*facts*"))
    assert not (out_root / NPI / "B0" / "_reopened" / "cost_1").exists()


# Fixes #60（使用者 2026-11-24 決定 P100 範圍）：reopen 把站資料夾裡除了 engineer.json 以外的檔案都搬走
def test_issue60_reopen_keeps_only_engineer_words(out_root, fake_stations):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    pipeline.prepare(NPI, "A0", "dfm", INPUT_ROOT, out_root, date="2026-11-02")
    write_judgement(out_root, NPI, "A0", "dfm", {})
    pipeline.render(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    pipeline.tell(NPI, "A0", "dfm", "R-03 的交期 6 週", out_root)
    pipeline.approve(NPI, "A0", "dfm", INPUT_ROOT, out_root)
    station = out_root / NPI / "A0" / "dfm"
    words = (station / "engineer.json").read_bytes()
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    assert [p.name for p in station.iterdir()] == ["engineer.json"]
    assert (station / "engineer.json").read_bytes() == words
    old = out_root / NPI / "A0" / "_reopened" / "dfm_1"
    assert {p.name for p in old.iterdir()} == {"reviewed.json", "facts.json", "judgement.json", "dfm.txt"}


# Fixes #66：站資料夾裡的子資料夾（例如 Numbers 存的 .numbers 套件是資料夾）也要搬，不能留給站代理看到
def test_issue66_reopen_moves_subfolders(out_root, fake_stations):
    from test_step0_manager import run_station
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    run_station(out_root, "A0", "dfm")
    station = out_root / NPI / "A0" / "dfm"
    (station / "draft.numbers").mkdir()
    (station / "draft.numbers" / "Index.zip").write_text("x", encoding="utf-8")
    pipeline.reopen(NPI, "A0", "dfm", out_root)
    assert not list(station.iterdir())
    assert (out_root / NPI / "A0" / "_reopened" / "dfm_1" / "draft.numbers" / "Index.zip").read_text(encoding="utf-8") == "x"

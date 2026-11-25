"""品質量測（開發用）：照內容深度規格 §9 量工具產出的文件，再加上「待工程師填寫」的數量。只報告，不擋 commit。

用法：
  .venv/bin/python check_quality.py            用 tests/fixtures 的判讀檔重新產生 Kalvara A0～C1、Corvane A0～B0 到暫存資料夾再量
  .venv/bin/python check_quality.py output     不重新產生，直接量這個資料夾（<NPI 號>/<版次>/<站>/）

重新產生的條件跟第 54 次一樣：全部接受、日期用時程表、不補任何待填。只讀工具自己的產出和工廠主資料，不讀答案檔。

量什麼（每個版次一欄；✓ 到了、✗ 沒到、？ 量不到、— 沒有那份文件或不適用）：

| 項目 | 怎麼量 | 標準（§9） |
| --- | --- | --- |
| 規格：章節 1–16 | docx 標題（Heading 樣式）寫成「章號 空白 章名」的，1～16 出現幾個；只有 2.1 沒有 2 不算有第 2 章。章號改用 Word 自動編號或自訂樣式時量不到，要改量法 | 16 個 |
| 規格：附錄 A | 有沒有標題含「Appendix A」「Annex A」「附錄 A」「附件 A」（不分大小寫） | 有 |
| 規格：2.1–2.3 | 初版之後才量：標題開頭 2.1、2.2、2.3 出現幾個 | 3 個 |
| 圖面：頁數 | PDF 頁數 | 3 頁 |
| 圖面：修訂欄版次數 | 圖面文字裡沒有「REVISION」或「修訂」就當沒有修訂欄；有的話，案子到這一版為止的版次代號出現幾個（看整張圖的文字，不是只看修訂欄那一格） | 全部 |
| BOM：工作表 | BOM、Channel Map、Routing、Revision，初版之後加 Change Summary（§5：變更摘要初版之後才有），出現幾個；只看名稱，不看內容 | 初版 4、之後 5 |
| BOM：通道檢查格 | 用 pycel 重算 Channel Map 的檢查格 | OK |
| 成本表：工作表數 | 工作表幾個 | ≥ 7 |
| 成本表：公式格數 | 以 = 開頭的格子幾個 | > 100 |
| 成本表：重算錯誤 | 用 pycel 重算每個公式，結果是 #… 或算不出來的幾個 | 0 |
| 成本表：總額 | 重算 Summary 的總成本，跟 reviewed.json 的 total 比；成本不完整（有待填輸入）而且表上也寫不完整時量不到，表上卻有數字算沒到；還沒 approve（沒有 reviewed.json）也量不到 | 相符 |
| 客戶信、備料信：HTML 版 | 信裡 HTML 那一段的標題（h1～h6）數和表格數，跟 EMAIL_ITEMS 比；只數標籤，不看是哪一節 | 不少於 EMAIL_ITEMS |
| 信件日期 | 檔名開頭的日期、信頭 Date，都等於 timeline.json 對應事件的日期；工程師用 --date 指定的日期也會進時程表，所以分不出是不是隨手填今天 | 每一封都是 |
| 保密 | 給客戶的文件（DFM／影響評估信、正式規格、圖面）逐行找價格表單價和料表庫存數字，規則和抓不到的寫法見 secret_hits；命中的行列在表後面，要人看是不是真的。0 行不代表沒有洩漏 | 0 行 |
| 待填（分工程發行、成本表、信件和 PO 核對三列） | npi.pending.pending_items 數到的「待工程師填寫」 | 沒有標準，只列數字 |
"""
import email
import email.header
import email.utils
import html
import json
import re
import sys
import tempfile
from pathlib import Path

import docx
import openpyxl
import pdfplumber
from pycel import ExcelCompiler

from npi.pending import pending_items
from npi.readers import master
from npi.render import xlsx_out as X
from npi.stations.release import CHANNEL_CHECK_CELL

ROOT = Path(__file__).resolve().parent
INPUT_ROOT = ROOT / "input"
OK, BAD, UNKNOWN, NA = "✓", "✗", "？", "—"

BOM_SHEETS = ["BOM", "Channel Map", "Routing", "Revision"]
# 內容深度規格 §1、§2、§8 列的項目數：(章節標題, 表格)，鍵是（站, 是不是初版）。
# 標題算粗體列出的段落，主旨、附件、「同時有文字版和 HTML 版」不算；表格只算名字裡有「表」的。
# §1：DFM 項目表、依生產經驗、建議交期表、商業說明、下一步。§2：醒目區塊、逐項評估表、生效範圍和交期表、商業影響、下一步。
# §8：批次計畫表、毛需求表、淨需求重算、動作清單、版次管制；變更通知多「本版變了什麼」。
EMAIL_ITEMS = {("dfm", True): (5, 2), ("dfm", False): (5, 2), ("supply", True): (5, 2), ("supply", False): (6, 2)}
EMAIL_EVENTS = {"dfm": ("DFM 回覆日", "影響評估日"), "supply": ("備料通知日",)}
PRICE_COLS = ["Base Unit Price (USD)", "Break 1 Price (USD)", "Break 2 Price (USD)", "Unit Price (USD)",
              "Minimum Charge (USD / order)"]
STOCK_COLS = ["On Hand", "Allocated", "Available", "Safety Stock"]
STOCK_WORDS = re.compile(r"stock|on[- ]hand|inventory|allocated|QOH|庫存|在庫|在手|可用量|已分配", re.I)
AMOUNT = r"\d[\d,]*(?:\.\d+)?"
WORD = "A-Za-z0-9_"                                                  # 不用 \w：\w 連中文也算，「庫存1200顆」會抓不到
NUMBER = re.compile(rf"(?<![{WORD}.,-]){AMOUNT}(?![{WORD}-]|[.,]\d)")   # 代碼裡的數字（MPO-12、R-04）不算
PRICED = re.compile(rf"(?:USD|\$)[\s:：)]*({AMOUNT})|({AMOUNT})\s*(?:USD|美元)", re.I)   # 緊貼著幣別的數字


def generate(out):
    """用測試的 fixture 判讀檔把兩個案子跑到有 fixture 的最後一站。"""
    sys.path.insert(0, str(ROOT / "tests"))
    from conftest import CVN_A0_SPEC, CVN_B0_ECR, run_real
    from test_step6_full_chain import CHAIN

    from npi import pipeline
    corvane = [("A0", CVN_A0_SPEC, ["dfm", "release", "cost"]), ("B0", CVN_B0_ECR, ["dfm", "release"])]
    for npi, chain in (("NPI-26-097", CHAIN), ("NPI-26-104", corvane)):
        for rev, doc, stations in chain:
            pipeline.intake(doc, INPUT_ROOT, out)
            for station in stations:
                run_real(out, rev, station, date=None, npi=npi)


class Case:
    def __init__(self, npi_dir, revs, i, secrets):
        self.label = f"{npi_dir.name[-3:]} {revs[i]}"
        self.dir = npi_dir / revs[i]
        self.revs_so_far, self.initial, self.secrets = revs[:i + 1], revs[i] == "A0", secrets   # 初版的判斷跟 pipeline 一樣
        self.hits = []

    def files(self, station, pattern="*"):
        return [p for p in sorted((self.dir / station).glob(pattern))
                if p.is_file() and not p.name.startswith(("~$", "."))]       # Office 開著檔案時留下的鎖定檔不看

    def file(self, station, pattern):
        return next(iter(self.files(station, pattern)), None)


def evaluate(path, refs):
    """用 pycel 重算這些格子。算不出來（例如公式指到不存在的工作表）記成 #ERROR，不讓整張表停下來。"""
    xl = ExcelCompiler(filename=str(path))
    out = []
    for ref in refs:
        try:
            out.append(xl.evaluate(ref))
        except Exception as e:  # noqa: BLE001 pycel 算不出來時丟的例外種類不固定
            out.append(f"#ERROR {type(e).__name__}")
    return out


def ratio(n, need, exact=False):
    return f"{n}/{need} {OK if (n == need if exact else n >= need) else BAD}"


# ---- 正式規格 ----
def _headings(c):
    path = c.file("release", "*.docx")
    return path and [p.text.strip() for p in docx.Document(path).paragraphs if p.style.name.startswith("Heading")]


def spec_chapters(c):
    heads = _headings(c)
    if heads is None:
        return NA
    found = {int(m.group(1)) for h in heads if (m := re.match(r"(\d{1,2})\.?\s+\S", h))}
    return ratio(len(found & set(range(1, 17))), 16)


def spec_appendix(c):
    heads = _headings(c)
    if heads is None:
        return NA
    found = any(re.search(r"(?<![A-Za-z])(Appendix|Annex)\s*A(?![A-Za-z])|附[錄件]\s*A(?![A-Za-z])", h, re.I)
                for h in heads)
    return f"有 {OK}" if found else f"沒有 {BAD}"


def spec_changes(c):
    heads = _headings(c)
    if heads is None or c.initial:
        return NA
    return ratio(sum(any(re.match(rf"{n}(?!\d)", h) for h in heads) for n in ("2\\.1", "2\\.2", "2\\.3")), 3)


# ---- 圖面 ----
def _drawing_pages(c):
    path = c.file("release", "*.pdf")
    if path is None:
        return None
    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def drawing_pages(c):
    pages = _drawing_pages(c)
    return NA if pages is None else ratio(len(pages), 3, exact=True)


def drawing_revs(c):
    pages = _drawing_pages(c)
    if pages is None:
        return NA
    text = "\n".join(pages)
    if not re.search(r"REVISION|修訂", text, re.I):
        return f"沒有修訂欄 {BAD}"
    return ratio(sum(bool(re.search(rf"(?<![A-Za-z0-9]){r}(?![A-Za-z0-9])", text)) for r in c.revs_so_far),
                 len(c.revs_so_far))


# ---- BOM ----
def bom_sheets(c):
    path = c.file("release", "*BOM.xlsx")
    if path is None:
        return NA
    need = BOM_SHEETS + ([] if c.initial else ["Change Summary"])
    names = openpyxl.load_workbook(path).sheetnames
    return ratio(sum(s in names for s in need), len(need))


def bom_check(c):
    path = c.file("release", "*BOM.xlsx")
    if path is None:
        return NA
    value = evaluate(path, [CHANNEL_CHECK_CELL])[0]
    return f"{value} {OK if value == 'OK' else BAD}"


# ---- 單位成本 ----
def _formulas(path):
    wb = openpyxl.load_workbook(path)
    return [f"{ws.title}!{cell.coordinate}" for ws in wb for row in ws.iter_rows() for cell in row
            if isinstance(cell.value, str) and cell.value.startswith("=")]


def cost_sheets(c):
    path = c.file("cost", "*_Unit_Cost.xlsx")
    if path is None:
        return NA
    n = len(openpyxl.load_workbook(path).sheetnames)
    return f"{n} {OK if n >= 7 else BAD}"


def cost_formulas(c):
    path = c.file("cost", "*_Unit_Cost.xlsx")
    if path is None:
        return NA
    n = len(_formulas(path))
    return f"{n} {OK if n > 100 else BAD}"


def cost_errors(c):
    path = c.file("cost", "*_Unit_Cost.xlsx")
    if path is None:
        return NA
    n = sum(isinstance(v, str) and v.startswith("#") for v in evaluate(path, _formulas(path)))
    return f"{n} {OK if n == 0 else BAD}"


def cost_total(c):
    path = c.file("cost", "*_Unit_Cost.xlsx")
    if path is None:
        return NA
    reviewed_path = c.dir / "cost" / "reviewed.json"
    if not reviewed_path.exists():
        return f"還沒審 {UNKNOWN}"
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    shown = evaluate(path, [X.SUMMARY_REF["total"]])[0]
    if not reviewed["complete"]:
        return f"不完整 {UNKNOWN}" if shown == X.INCOMPLETE else f"表上 {shown}、程式不完整 {BAD}"
    same = isinstance(shown, (int, float)) and abs(shown - reviewed["total"]) < 0.005
    return f"相符 {OK}" if same else f"表上 {shown}、程式 {reviewed['total']} {BAD}"


# ---- 信件 ----
def _mail(c, station):
    path = c.file(station, "*.eml")
    return path and (path, email.message_from_bytes(path.read_bytes()))


def _part_text(part):
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


def mail_html(station):
    def measure(c):
        found = _mail(c, station)
        if found is None:
            return NA
        page = next((_part_text(p) for p in found[1].walk() if p.get_content_type() == "text/html"), None)
        if page is None:
            return f"沒有 {BAD}"
        need_h, need_t = EMAIL_ITEMS[station, c.initial]
        h, t = len(re.findall(r"<h[1-6][\s>]", page, re.I)), len(re.findall(r"<table[\s>]", page, re.I))
        return f"標題 {h}/{need_h}、表 {t}/{need_t} {OK if h >= need_h and t >= need_t else BAD}"
    return measure


def mail_dates(c):
    mails = {station: found for station in EMAIL_EVENTS if (found := _mail(c, station))}
    if not mails:
        return NA
    timeline = c.dir / "timeline.json"
    if not timeline.exists():
        return f"沒有時程表 {UNKNOWN}"
    events = {e["event"]: e["date"] for e in json.loads(timeline.read_text(encoding="utf-8"))["events"]}
    right = total = 0
    for station, found in mails.items():
        names = EMAIL_EVENTS[station]
        total += 1
        day = next((events[n] for n in names if n in events), None)
        header = email.utils.parsedate_to_datetime(found[1]["Date"]).date().isoformat()
        right += day is not None and found[0].name.startswith(day) and header == day
    return ratio(right, total, exact=True)


# ---- 保密 ----
def load_secrets():
    """{"own": {代碼: 那一列的單價和庫存數字}, "prices": 所有單價, "stock": 所有庫存數字}，只收大於 0 的數字。"""
    pl, mm = master.read_pl(INPUT_ROOT), master.read_mm002(INPUT_ROOT)

    def values(row, cols):
        return {float(row[k]) for k in cols if isinstance(row.get(k), (int, float)) and row[k] > 0}
    own, prices, stock = {}, set(), set()
    for code, row in [*pl["materials"].items(), *pl["services"].items()]:
        own.setdefault(code, set()).update(values(row, PRICE_COLS))
        prices |= values(row, PRICE_COLS)
    for code, row in mm.items():
        own.setdefault(code, set()).update(values(row, STOCK_COLS))
        stock |= values(row, STOCK_COLS)
    return {"own": own, "prices": prices, "stock": stock}


def _lines(path):
    if path.suffix == ".eml":
        msg = email.message_from_bytes(path.read_bytes())
        texts = [html.unescape(re.sub(r"<[^>]+>", " ", _part_text(p))).replace("\xa0", " ")
                 for p in msg.walk() if p.get_content_maintype() == "text"]
        subject = str(email.header.make_header(email.header.decode_header(msg["Subject"] or "")))
        return [subject, *"\n".join(texts).splitlines()]
    if path.suffix == ".docx":
        d = docx.Document(path)
        margins = [p.text for sec in d.sections for part in (sec.header, sec.footer) for p in part.paragraphs]
        return margins + [p.text for p in d.paragraphs] + [" | ".join(cell.text for cell in row.cells)
                                                           for t in d.tables for row in t.rows]
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages).splitlines()


def _number(text):
    return float(text.replace(",", ""))


def _has_code(line, code):
    return code in line and re.search(rf"(?<![{WORD}-]){re.escape(code)}(?![{WORD}-])", line) is not None


def _numbers(text):
    return {_number(t) for t in NUMBER.findall(text)}


def secret_hits(c):
    """給客戶的文件一行一行看，命中的記進 c.hits。規則（照順序，中了就不往下）：
    a. 這一行有價格表或料表的代碼，又有那個代碼自己的單價或庫存數字。
    b. 緊貼著幣別（USD、$、美元）的數字，是價格表的任何一個單價。
    c. 庫存字眼（STOCK_WORDS）前後 30 個字以內，有料表的任何一個庫存數字。
    只比數字，所以巧合也會中：報價、一次性費用剛好等於某個料的單價或最低收費，「stocked」旁邊的數量剛好等於某個庫存數字。
    抓不到的：沒寫幣別也沒寫代碼的單價；表頭寫 USD、數字在下一列的表格；四捨五入過的單價；available 這種太常見的字；
    docx 的文字方塊和巢狀表格。所以 0 行只代表這三條規則沒中。命中的行要人看。"""
    files = c.files("dfm", "*.eml") + c.files("release", "*.docx") + c.files("release", "*.pdf")
    if not files:
        return NA
    s = c.secrets
    for path in files:
        for line in _lines(path):
            priced = {_number(a or b) for a, b in PRICED.findall(line)}
            words = list(STOCK_WORDS.finditer(line))
            near_stock = {_number(n.group()) for n in NUMBER.finditer(line)
                          if any(n.end() > w.start() - 30 and n.start() < w.end() + 30 for w in words)}
            rule = ("a" if any(_has_code(line, code) and _numbers(line) & own for code, own in s["own"].items()) else
                    "b" if priced & s["prices"] else
                    "c" if near_stock & s["stock"] else None)
            if rule:
                c.hits.append(f"{c.label} {path.name}〔{rule}〕{' '.join(line.split())[:120]}")
    return f"{len(c.hits)} {OK if not c.hits else BAD}"


# ---- 待填 ----
def pending(*stations):
    def measure(c):
        files = [p for st in stations for p in c.files(st)]
        return str(len(pending_items(files))) if files else NA
    return measure


ROWS = [("規格：章節 1–16", "16", spec_chapters),
        ("規格：附錄 A", "有", spec_appendix),
        ("規格：2.1–2.3", "3（初版之後）", spec_changes),
        ("圖面：頁數", "3", drawing_pages),
        ("圖面：修訂欄版次數", "到這一版的版次數", drawing_revs),
        ("BOM：工作表", "初版 4、之後 5", bom_sheets),
        ("BOM：通道檢查格", "OK", bom_check),
        ("成本表：工作表數", "≥ 7", cost_sheets),
        ("成本表：公式格數", "> 100", cost_formulas),
        ("成本表：重算錯誤", "0", cost_errors),
        ("成本表：總額", "相符", cost_total),
        ("客戶信：HTML 版", "標題 5、表 2", mail_html("dfm")),
        ("備料信：HTML 版", "標題 5（變更通知 6）、表 2", mail_html("supply")),
        ("信件日期", "等於時程事件日", mail_dates),
        ("保密：疑似命中的行", "0", secret_hits),
        ("待填：工程發行", "只列數字", pending("release")),
        ("待填：成本表", "只列數字", pending("cost")),
        ("待填：信件、PO 核對", "只列數字", pending("dfm", "po", "supply"))]


def measure(out):
    secrets = load_secrets()
    cases = []
    if not Path(out).is_dir():
        sys.exit(f"品質量測：找不到資料夾 {out}。")
    for npi_dir in sorted(p for p in Path(out).iterdir() if re.fullmatch(r"NPI-\d+-\d+", p.name)):
        revs = sorted(d.name for d in npi_dir.iterdir() if d.is_dir() and re.fullmatch(r"[A-Z]\d", d.name))
        cases += [Case(npi_dir, revs, i, secrets) for i in range(len(revs))]
    if not cases:
        sys.exit(f"品質量測：{out} 底下找不到 <NPI 號>/<版次>/ 資料夾。")
    lines = ["| 項目 | 標準 | " + " | ".join(c.label for c in cases) + " |", "| --- " * (len(cases) + 2) + "|"]
    cells = []
    for label, standard, fn in ROWS:
        row = [fn(c) for c in cases]
        cells += row
        lines.append(f"| {label} | {standard} | " + " | ".join(row) + " |")
    count = {mark: sum(cell.endswith(mark) for cell in cells) for mark in (OK, BAD, UNKNOWN)}
    lines.append(f"\n品質量測：{len(cases)} 個版次，到了 {count[OK]} 格、沒到 {count[BAD]} 格、量不到 {count[UNKNOWN]} 格。"
                 "只報告，不擋 commit。")
    hits = [h for c in cases for h in c.hits]
    if hits:
        lines += ["\n保密疑似命中的行（要人看）：", *hits]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.exit("用法：check_quality.py [要量的資料夾]")
    if len(sys.argv) == 2:
        print(measure(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp) / "output")
            print(measure(Path(tmp) / "output"))

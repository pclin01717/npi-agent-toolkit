"""PLANS P59：產出文件裡每一個「待工程師填寫」的位置，給工程師照著補。"""
import email
from pathlib import Path

import docx
import openpyxl
import pdfplumber

from .sources import PENDING


def _xlsx(path):
    wb = openpyxl.load_workbook(path)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is None or str(c.value).startswith("="):     # 公式不是待填格（issue #31）
                    continue
                for _ in range(str(c.value).count(PENDING)):
                    yield f"「{ws.title}」 {c.coordinate}"


def _docx(path):
    d = docx.Document(path)
    for n, p in enumerate(d.paragraphs, 1):
        for _ in range(p.text.count(PENDING)):
            yield f"第 {n} 段"
    for t_no, t in enumerate(d.tables, 1):
        seen = set()
        for r_no, row in enumerate(t.rows, 1):
            for c_no, c in enumerate(row.cells, 1):
                if id(c._tc) in seen:            # 合併儲存格只算一次
                    continue
                seen.add(id(c._tc))
                for _ in range(c.text.count(PENDING)):
                    yield f"表 {t_no} 第 {r_no} 列第 {c_no} 欄"


def _eml(path):
    body = email.message_from_bytes(path.read_bytes()).get_payload(decode=True).decode("utf-8")
    for n, line in enumerate(body.splitlines(), 1):
        for _ in range(line.count(PENDING)):
            yield f"第 {n} 行"


def _pdf(path):
    with pdfplumber.open(path) as pdf:
        for p_no, page in enumerate(pdf.pages, 1):
            for _ in range((page.extract_text() or "").count(PENDING)):
                yield f"第 {p_no} 頁"


def _md(path):
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        for _ in range(line.count(PENDING)):
            yield f"第 {n} 行"


READERS = {".xlsx": _xlsx, ".docx": _docx, ".eml": _eml, ".pdf": _pdf, ".md": _md}


def pending_items(paths):
    """[{"file": 檔名, "where": 位置}]，一個「待工程師填寫」一筆。STEP 檔不看。"""
    out = []
    for path in map(Path, paths):
        reader = READERS.get(path.suffix.lower())
        if reader:
            out += [{"file": path.name, "where": where} for where in reader(path)]
    return out

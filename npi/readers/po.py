"""客戶 PO（PDF）：用 pdfplumber 取文字，抓 PO 號、版次、日期、成品總數、各交貨行。"""
import re
from pathlib import Path

import pdfplumber

from ..errors import NpiError

PO_NO = re.compile(r"\b([A-Z]{2,}-PO-[\d-]+)\s+(\d+)\s*$", re.MULTILINE)
DATE = re.compile(r"\bDate (\d{4}-\d{2}-\d{2})")
# 另一種表頭（issue #19）：「PURCHASE ORDER Rev 0」或「CHANGE ORDER 01 Rev 1」，下面一行是「<PO 號> <日期>」
REV_TITLE = re.compile(r"(?:PURCHASE|CHANGE) ORDER(?: \d+)? Rev (\d+)")
PO_NO_DATE = re.compile(r"\b([A-Z]{2,}-PO-[\d-]+)\s+(\d{4}-\d{2}-\d{2})\b")
TOTAL = re.compile(r"^1\s+.*?\s([\d,]+)\s+EA\b", re.MULTILINE)
SCHEDULE = re.compile(r"^(1\.\d+)\s+Delivery:.*?\s([\d,]+)\s+EA\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(\d{4}-\d{2}-\d{2})",
                      re.MULTILINE)
LINE_PN = re.compile(r"Customer Rev ([A-Z]) / LPC P/N (LPC-[A-Z0-9-]+)")


def _n(text):
    return float(text.replace(",", ""))


def read_po(path):
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    m, date = PO_NO.search(text), DATE.search(text)
    title, no_date = REV_TITLE.search(text), PO_NO_DATE.search(text)
    if m:
        po_no, rev = m.group(1), int(m.group(2))
    elif title and no_date:
        po_no, rev = no_date.group(1), int(title.group(1))
        date = date or no_date
    else:
        raise NpiError(f"{path.name}：找不到 PO 號和版次")
    date = date.group(date.lastindex) if date else None
    total = TOTAL.search(text)
    if not date or not total:
        raise NpiError(f"{path.name}：找不到{'PO 日期' if not date else '第 1 行的成品總數'}")
    schedule = []
    matches = list(SCHEDULE.finditer(text))
    for i, s in enumerate(matches):
        tail = text[s.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        pn = LINE_PN.search(tail)
        if not pn:
            raise NpiError(f"{path.name}：交貨行 {s.group(1)} 找不到「Customer Rev / LPC P/N」")
        schedule.append({"line": s.group(1), "qty": int(_n(s.group(2))), "unit_price": _n(s.group(3)),
                         "extended": _n(s.group(4)), "need_date": s.group(5),
                         "cust_rev": pn.group(1), "lpc_pn": pn.group(2)})
    if not schedule:
        raise NpiError(f"{path.name}：找不到交貨行（1.1 Delivery: …）")
    return {"file": path.name, "po_no": po_no, "rev": rev, "date": date,
            "total_qty": int(_n(total.group(1))), "schedule": schedule, "text": text}


_QUOTE_NO = re.compile(r"LPC-Q-\d{2}-\d{4}(?:-R\d+)?")
_DATED = re.compile(r"\bdated\b[\s\S]{0,200}?(\d{4}-\d{2}-\d{2})")


def quote_refs(text):
    """PO 上的報價單號和日期（PLANS P95）。PDF 是多欄排版，「dated」和日期可能被別欄的字隔開，
    所以在號碼後面 250 字內找「dated」之後的第一個日期；範圍到下一個報價單號為止，
    找不到 dated 的（例如 supersedes 提到的舊號）不收。"""
    out = []
    for m in _QUOTE_NO.finditer(text):
        window = text[m.end(): m.end() + 250]
        nxt = _QUOTE_NO.search(window)
        d = _DATED.search(window[: nxt.start()] if nxt else window)
        if d and (m.group(0), d.group(1)) not in out:
            out.append((m.group(0), d.group(1)))
    return out

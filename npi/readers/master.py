"""四份工廠主資料：QM-021（製程能力）、LL-003（生產經驗）、MM-002（物料主檔）、PL（價格表）。"""
import re
from pathlib import Path

import docx
import openpyxl

from ..errors import NpiError
from .rules import rule_sources
from .docx_util import blocks, table_rows

MASTER_DIR = "00_Factory_Master_Data"
FILES = {
    "qm021": "LPC-QM-021_Process_Capability_RevC.docx",
    "ll003": "LPC-LL-003_FAU_Production_Experience.xlsx",
    "mm002": "LPC-MM-002_Factory_Material_Master_List.xlsx",
    "pl": "LPC-PL-2026H2_Material_Price_List.xlsx",
}
SECTION = re.compile(r"^(\d+(?:\.\d+)?)\s+\S")


def _path(input_root, key):
    path = Path(input_root) / MASTER_DIR / FILES[key]
    if not path.exists():
        raise NpiError(f"找不到工廠主資料：{path}")
    return path


def read_qm021(input_root):
    """回傳 {"§4.1": 該節全文}，表格每列用「 | 」接起來。"""
    path = _path(input_root, "qm021")
    sections, current = {}, None
    for kind, b in blocks(docx.Document(path)):
        if kind == "p":
            if b.style.name.startswith("Heading"):
                m = SECTION.match(b.text.strip())
                if m:
                    current = "§" + m.group(1)
                    sections[current] = [b.text.strip()]
                    continue
            if current and b.text.strip():
                sections[current].append(b.text.strip())
        elif current:
            sections[current] += [" | ".join(r) for r in table_rows(b)]
    if not sections:
        raise NpiError(f"{path.name}：讀不到任何章節")
    return {k: "\n".join(v) for k, v in sections.items()}


def _sheet_rows(path, ws, first_head):
    """找到第一格是 first_head 的表頭列，回傳 [{表頭: 值}]。"""
    head_row = None
    for row in ws.iter_rows():
        if row[0].value == first_head:
            head_row = row[0].row
            break
    if head_row is None:
        raise NpiError(f"{path.name}「{ws.title}」：找不到表頭「{first_head}」")
    heads = [str(c.value).replace("\n", " ") if c.value is not None else None for c in ws[head_row]]
    out = []
    for r in ws.iter_rows(min_row=head_row + 1, values_only=True):
        if not _is_code(r[0]):          # 空列、表格下方的註解、TOTAL 列都不是資料
            continue
        out.append({h: v for h, v in zip(heads, r) if h})
    return out


def _is_code(value):
    text = str(value).strip() if value is not None else ""
    return bool(text) and not any(c.isspace() for c in text) and text.upper() != "TOTAL"


def _row_text(row):
    return " | ".join(f"{k}: {v}" for k, v in row.items() if v is not None)


def read_ll003(input_root):
    """回傳 {"LL-01": 全文, "DR-01": 全文, "P01": 全文}。"""
    path = _path(input_root, "ll003")
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    for sheet, head in (("Products", "ID"), ("Lessons Learned", "LL ID"), ("Design Rules", "Rule ID")):
        for row in _sheet_rows(path, wb[sheet], head):
            out[str(row[head])] = _row_text(row)
    for sheet in ("Key Characteristics", "Production Results"):
        for row in _sheet_rows(path, wb[sheet], "ID"):
            key = str(row["ID"])
            out[key] = out.get(key, "") + "\n" + _row_text(row)
    return out


def read_ll003_products(input_root):
    """LL-003「Products」的每一列（登記表要用 LPC P/N 和 NPI Start，PLANS 表 G）。"""
    path = _path(input_root, "ll003")
    wb = openpyxl.load_workbook(path, data_only=True)
    return _sheet_rows(path, wb["Products"], "ID")


def read_mm002(input_root):
    """回傳 {料號: 該列}。"""
    path = _path(input_root, "mm002")
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = _sheet_rows(path, wb["Material Master"], "Material Code")
    return _by_code(path, rows, "Material Code")


def read_pl(input_root):
    """回傳 {"materials": {料號: 該列}, "services": {服務碼: 該列}}。"""
    path = _path(input_root, "pl")
    wb = openpyxl.load_workbook(path, data_only=True)
    return {"materials": _by_code(path, _sheet_rows(path, wb["Material Prices"], "Material Code"), "Material Code"),
            "services": _by_code(path, _sheet_rows(path, wb["Services"], "Service Code"), "Service Code")}


def _by_code(path, rows, key):
    out = {}
    for row in rows:
        code = str(row[key]).strip()
        if code in out:
            raise NpiError(f"{path.name}：{key} 重複：{code}")
        out[code] = row
    return out


def source_texts(input_root):
    """給「不編數字」用的出處：{出處編號: 原文}。"""
    out = {f"QM-021 {k}": v for k, v in read_qm021(input_root).items()}
    out.update({f"LL-003 {k}": v.strip() for k, v in read_ll003(input_root).items()})
    out.update({f"MM-002 {k}": _row_text(v) for k, v in read_mm002(input_root).items()})
    pl = read_pl(input_root)
    out.update({f"PL {k}": _row_text(v) for k, v in pl["materials"].items()})
    out.update({f"PL {k}": _row_text(v) for k, v in pl["services"].items()})
    out.update(rule_sources(input_root))          # 第 3 批：作業規則（PLANS P57）
    return out

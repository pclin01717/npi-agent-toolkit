"""客戶 ECR（docx）：基本資料、變更表（CH）、受影響文件表、聯絡人表。"""
import re
from pathlib import Path

import docx

from ..errors import NpiError
from .docx_util import blocks, label_values, pick, table_rows

META_ALIASES = {
    "ecr_no": ["ECR no. / rev", "ECR no.", "ECR No."],
    "date": ["ECR date", "Date"],
    "part_no": ["Part no.", "Part No.", "Customer P/N"],
    "description": ["Description"],
    "current": ["Current revision"],
    "proposed": ["Proposed revision"],
    "change_class": ["Change class"],
    "originator": ["Originator"],
    "reply_by": ["Supplier reply by"],
    "purchase_order": ["Purchase order"],
    "quotation": ["Supplier quotation"],
}
CH_ID = re.compile(r"^CH\d+$")
CUST_REV = re.compile(r"\bRev\s+([A-Z])\b")


def read_ecr(path):
    path = Path(path)
    d = docx.Document(path)
    meta, changes, affected, contacts = None, [], [], []
    for kind, t in blocks(d):
        if kind != "t":
            continue
        rows = table_rows(t)
        values = label_values(t)
        if meta is None and pick(values, META_ALIASES["ecr_no"]):
            meta = {k: pick(values, a) for k, a in META_ALIASES.items()}
            continue
        if any(CH_ID.match(r[0]) for r in rows if r):
            head = rows[0]
            for r in rows:
                if CH_ID.match(r[0]):
                    changes.append({"id": r[0], "change": r[1], "from": r[2], "to": r[3],
                                    "reason": r[4] if len(r) > 4 else "", "header": head})
            continue
        head = rows[0] if rows else []
        if head and head[0].startswith("Document / part"):
            affected += [{"item": r[0], "status": r[1], "affected_by": r[2]} for r in rows[1:]]
        elif any(h.lower() in ("e-mail", "email") for h in head):
            contacts += [dict(zip(head, r)) for r in rows[1:]]
    if meta is None:
        raise NpiError(f"{path.name}：找不到基本資料表（ECR 編號）")
    missing = [k for k in ("ecr_no", "date", "part_no", "current", "proposed", "originator") if not meta.get(k)]
    if missing:
        raise NpiError(f"{path.name}：基本資料表缺少欄位：{'、'.join(missing)}")
    no = meta["ecr_no"].split("/")[0].strip()
    meta["ecr_rev"] = meta["ecr_no"].split("/")[1].strip() if "/" in meta["ecr_no"] else None
    meta["ecr_no"] = no
    meta["seq"] = no.rsplit("-", 1)[-1]
    for key in ("current", "proposed"):
        m = CUST_REV.search(meta[key])
        if not m:
            raise NpiError(f"{path.name}：「{key}」看不出客戶版次（Rev X）：{meta[key]}")
        meta[f"{key}_cust_rev"] = m.group(1)
    if not changes:
        raise NpiError(f"{path.name}：找不到變更表（CH1、CH2…）")
    po_rows = [a for a in affected if a["item"].lower().startswith("purchase order")]
    po_revision = not any("no po revision" in a["affected_by"].lower() for a in po_rows)
    return {"file": path.name, "meta": meta, "changes": changes, "affected": affected,
            "contacts": contacts, "po_revision": po_revision}


def read_text(path):
    """ECR 全文（段落和表格），給登記表找報價單號（PLANS 表 G 第 4 列）。"""
    d = docx.Document(path)
    cells = [c.text for t in d.tables for row in t.rows for c in row.cells]
    return "\n".join([p.text for p in d.paragraphs] + cells)

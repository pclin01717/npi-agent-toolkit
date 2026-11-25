"""客戶草稿 spec（docx）。用 R 編號和表頭找表，不靠表格順序；基本資料欄名接受同義字。"""
import re
from pathlib import Path

import docx

from ..errors import NpiError
from .docx_util import blocks, label_values, label_values_rows, pick, table_rows

META_ALIASES = {
    "spec_no": ["Spec no.", "Spec No.", "Document", "Document no.", "Spec number"],
    "rev": ["Revision / status", "Revision", "Rev.", "Issue"],
    "date": ["Date", "Issue date", "Release date"],
    "rfq": ["RFQ", "RFQ no.", "RFQ No."],
    "description": ["Description", "Title"],
    "drawing": ["Drawing", "Customer drawing"],
}
R_ID = re.compile(r"^R-\d{2}$")
OP_ID = re.compile(r"^OP-\d{2}$")


def read_spec(path):
    path = Path(path)
    d = docx.Document(path)
    tables = [t for kind, t in blocks(d) if kind == "t"]
    meta, requirements, open_points, contacts, params = None, [], [], [], {}
    for t in tables:
        rows = table_rows(t)
        values = label_values(t)
        if meta is None and pick(values, META_ALIASES["spec_no"]):
            meta = {k: pick(values, a) for k, a in META_ALIASES.items()}
            pn_label = next((k for k in values if k.endswith("P/N") and "Supplier" not in k), None)
            meta["part_no"] = values.get(pn_label) if pn_label else pick(values, ["Part no.", "Part No."])  # #47
            continue
        if any(R_ID.match(r[0]) for r in rows if r):
            group = None
            for r in rows:
                if R_ID.match(r[0]):
                    requirements.append({"id": r[0], "group": group, "text": r[1]})
                elif len(set(r)) == 1 and r[0]:
                    group = r[0]
            continue
        if any(OP_ID.match(r[0]) for r in rows if r):
            open_points += [{"id": r[0], "ref": r[1], "text": r[2]} for r in rows if OP_ID.match(r[0])]
            continue
        head = rows[0] if rows else []
        if head and head[0] == "Parameter":
            params.update({k: v for k, v in label_values_rows(rows[1:]).items()})
            continue
        if any(h.lower() in ("e-mail", "email") for h in head):
            contacts += [dict(zip(head, r)) for r in rows[1:]]
    if meta is None:
        raise NpiError(f"{path.name}：找不到基本資料表（spec 編號）")
    missing = [k for k in ("spec_no", "rev", "rfq", "part_no", "description", "date") if not meta.get(k)]
    if missing:
        raise NpiError(f"{path.name}：基本資料表缺少欄位：{'、'.join(missing)}")
    meta["rev"] = meta["rev"].split()[0]
    if not requirements:
        raise NpiError(f"{path.name}：找不到要求表（R-01、R-02…）")
    ids = [r["id"] for r in requirements]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise NpiError(f"{path.name}：要求編號重複：{'、'.join(dup)}")
    empty = [r["id"] for r in requirements if not r["text"]]
    if empty:
        raise NpiError(f"{path.name}：要求內容是空的：{'、'.join(empty)}")
    if not contacts:
        raise NpiError(f"{path.name}：找不到聯絡人表（有 E-mail 欄的表）")
    return {"file": path.name, "meta": meta, "requirements": requirements,
            "open_points": open_points, "contacts": contacts, "params": params}

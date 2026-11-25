"""供應鏈站：備料通知（A0）／物料變更通知（B0 之後）。需求量 = 每個成品用量 × PO 數量（P16，不含損耗、不扣庫存）。"""
import json

from ..errors import NpiError
from ..intake import REVS
from ..readers.ecr import read_ecr
from ..readers.master import read_mm002
from ..render.eml import people, read_eml, render_text, write_eml
from ..sources import PENDING, field_errors


def _reviewed(ctx, station, rev):
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def requirements(bom, po_qty, mm):
    """純函式：BOM 的買料 → 毛需求。用量待填的，需求量也待填（None）。"""
    out = []
    for b in bom:
        if b["make_buy"] != "Buy":
            continue
        qty = b.get("ext_qty", b["qty_per"])           # 第 3 批：展開用量（P61）
        gross = None if qty is None else round(qty * po_qty, 4)
        if gross is not None and float(gross).is_integer():
            gross = int(gross)
        row = mm.get(b["part_no"], {})
        out.append({"part_no": b["part_no"], "description": b["description"], "qty_per": qty, "uom": b["uom"],
                    "gross_qty": gross, "lead_time_days": row.get("Lead Time (days)"),
                    "available": row.get("Available"), "in_mm002": bool(row)})
    return out


def bom_changes(old, new):
    """純函式：上一版 BOM 對這一版 BOM 的買料差異。料號待填的列另列成 pending_pn（issue #21）。"""
    o = {b["part_no"]: b["qty_per"] for b in old if b["make_buy"] == "Buy" and b["part_no"] != PENDING}
    n = {b["part_no"]: b["qty_per"] for b in new if b["make_buy"] == "Buy" and b["part_no"] != PENDING}
    out = {"added": [p for p in n if p not in o], "removed": [p for p in o if p not in n],
           "changed": [{"part_no": p, "from": o[p], "to": n[p]} for p in n if p in o and o[p] != n[p]]}
    pending = [b["description"] for b in new if b["make_buy"] == "Buy" and b["part_no"] == PENDING]
    if pending:
        out["pending_pn"] = pending
    return out


def prepare(ctx):
    release = _reviewed(ctx, "release", ctx.rev)
    if release is None:
        raise NpiError(f"{ctx.rev} 的工程發行還沒審")
    po_rev = next((r for r in reversed(REVS[: REVS.index(ctx.rev) + 1]) if _reviewed(ctx, "po", r)), None)
    if po_rev is None:
        raise NpiError(f"{ctx.rev} 和之前的版次都沒有已審的 PO 核對，算不出需求量")
    po = _reviewed(ctx, "po", po_rev)["po"]
    mm = read_mm002(ctx.input_root)
    facts = {"rev": ctx.rev, "date": ctx.date, "kind": "preparation" if ctx.rev == "A0" else "change",
             "po": po, "po_from_rev": po_rev, "lpc_pn": release.get("lpc_pn"),
             "requirements": requirements(release["bom"], po["total_qty"], mm)}
    if ctx.rev != "A0":
        prev = _reviewed(ctx, "release", REVS[REVS.index(ctx.rev) - 1])
        facts["changes"] = bom_changes(prev["bom"] if prev else [], release["bom"])
        ecr = sorted((ctx.rev_input_dir / "01_Customer_ECR").glob("*.docx"))
        facts["ecr_no"] = read_ecr(ecr[0])["meta"]["ecr_no"] if ecr else None
    facts["sources"] = {"PO": f"{po['po_no']} Rev {po['rev']} total {po['total_qty']} pcs (from {po_rev})"}
    facts["sources"].update({f"REQ {r['part_no']}": f"{r['qty_per']} {r['uom']}/FAU x {po['total_qty']} = {r['gross_qty']} {r['uom']}"
                             for r in facts["requirements"]})
    facts["sources"].update({f"MM-002 {r['part_no']}": json.dumps(mm.get(r["part_no"], {}), default=str)
                             for r in facts["requirements"]})
    return facts


def check(ctx, facts, judgement):
    errors = []
    for n, note in enumerate(judgement.get("notes", []), 1):
        errors += field_errors(f"備註 {n}", note.get("text", ""), note.get("sources", []), facts["sources"])
    return errors


def file_name(facts, npi_no):
    kind = "Material_Preparation" if facts["kind"] == "preparation" else "Material_Change_Notice"
    return f"{facts['date']}_{kind}_{npi_no}.eml"


def render(ctx, facts, judgement):
    p = people()
    subject, body = render_text("supply_email.txt.j2", facts=facts, j=judgement, npi_no=ctx.npi_no,
                                sender=p["sender"], to=p["scm"])
    path = ctx.station_dir / file_name(facts, ctx.npi_no)
    write_eml(path, p["sender"], [p["scm"]], [], subject, body, facts["date"])
    return [path]


def read_back(ctx, facts, judgement):
    return {"rev": facts["rev"], "po": facts["po"], "requirements": facts["requirements"],
            "changes": facts.get("changes"), "email": read_eml(ctx.station_dir / file_name(facts, ctx.npi_no))}

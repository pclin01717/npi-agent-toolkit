"""PO 核對站：PO 各交貨行對我方已審的正式 spec（料號、客戶版次）與單位成本。"""
import json

from ..errors import NpiError
from ..intake import REVS
from ..readers import one_file
from ..readers.po import read_po
from ..render.eml import _env
from ..sources import field_errors


def _reviewed(ctx, station, rev):
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def po_findings(po, ours, cost):
    """純函式。ours：{LPC P/N: {"rev", "cust_rev", "spec"}}；cost：這個版次的單位成本（或 None）。"""
    found = []
    for s in po["schedule"]:
        where = f"PO 第 {s['line']} 行"
        mine = ours.get(s["lpc_pn"])
        if mine is None:
            found.append(f"{where}「LPC P/N」{s['lpc_pn']} 跟我方已審的料號不一致（我方：{'、'.join(ours) or '無'}）")
            continue
        if not mine.get("cust_rev"):
            found.append(f"{where}「客戶版次」：我方 {mine['rev']} 的客戶版次不明，無法比較")
        elif s["cust_rev"] != mine["cust_rev"]:
            found.append(f"{where}「客戶版次」{s['cust_rev']} 跟我方 {mine['rev']} 對應的客戶版次 {mine['cust_rev']} 不一致")
        if cost and mine["rev"] == cost["rev"]:
            if not cost["complete"]:
                found.append(f"{where}：單位成本不完整，無法比較單價")
            elif s["unit_price"] < cost["total"]:
                found.append(f"{where}：單價 USD {s['unit_price']:.2f} 低於單位成本 USD {cost['total']:.2f}")
    return found


def prepare(ctx):
    po = read_po(one_file(ctx.rev_input_dir / "05_Customer_PO", "*.pdf"))
    digits = ctx.npi_no.replace("NPI-", "").replace("-", "")
    ours = {}
    for rev in REVS[: REVS.index(ctx.rev) + 1]:
        rel = _reviewed(ctx, "release", rev)
        if rel:
            ours[rel["lpc_pn"]] = {"rev": rev, "cust_rev": rel.get("cust_rev"), "spec": f"LPC-PS-{digits} Rev {rev}"}
    cost = _reviewed(ctx, "cost", ctx.rev)
    if cost is None:
        raise NpiError(f"{ctx.rev} 的成本還沒審")
    cost_view = {"rev": ctx.rev, "complete": cost["complete"], "total": cost["total"]}
    current = next((pn for pn, o in ours.items() if o["rev"] == ctx.rev), None)
    return {"rev": ctx.rev, "date": ctx.date, "po": {k: v for k, v in po.items() if k != "text"},
            "ours": ours, "current_pn": current, "cost": cost_view,
            "findings": po_findings(po, ours, cost_view),
            "sources": {"PO": po["text"], "COST": json.dumps(cost_view), "OURS": json.dumps(ours)}}


def check(ctx, facts, judgement):
    errors = []
    for n, note in enumerate(judgement.get("notes", []), 1):
        errors += field_errors(f"備註 {n}", note.get("text", ""), note.get("sources", []), facts["sources"])
    return errors


def file_name(facts):
    return f"PO_Check_{facts['po']['po_no']}_Rev{facts['po']['rev']}.md"


def render(ctx, facts, judgement):
    text = _env.get_template("po_check.md.j2").render(facts=facts, j=judgement, npi_no=ctx.npi_no)
    path = ctx.station_dir / file_name(facts)
    path.write_text(text, encoding="utf-8")
    return [path]


def read_back(ctx, facts, judgement):
    path = ctx.station_dir / file_name(facts)
    return {"rev": facts["rev"], "po": facts["po"], "findings": facts["findings"],
            "report": path.read_text(encoding="utf-8"), "file": path.name}

"""DFM（A0 草稿 spec）／變更影響（ECR）站。"""
import json

from ..params import prev_sources
from ..readers import one_file
from ..readers.ecr import read_ecr
from ..readers.master import source_texts
from ..readers.spec import read_spec
from ..render.eml import people, read_eml, render_text, write_eml
from ..sources import field_errors

ITEM_FIELDS = {"dfm": ["title", "risk", "requirement", "capability", "proposal", "impact"],
               "impact": ["title", "feasibility", "assessment", "cost"]}


def _client_doc(ctx, kind):
    return one_file(ctx.rev_input_dir / ("01_Customer_Draft_Spec" if kind == "dfm" else "01_Customer_ECR"), "*.docx")


def _contact(c):
    return {"name": c.get("Name", ""), "email": c.get("E-mail") or c.get("Email", ""),
            "function": c.get("Function", ""), "company": c.get("Company", "")}


def prepare(ctx):
    kind = "dfm" if ctx.rev == "A0" else "impact"
    path = _client_doc(ctx, kind)
    sources = source_texts(ctx.input_root)
    if kind == "dfm":
        spec = read_spec(path)
        items = [{"id": r["id"], "text": r["text"]} for r in spec["requirements"]]
        sources.update({r["id"]: r["text"] for r in spec["requirements"]})
        sources.update({o["id"]: f"{o['ref']}: {o['text']}" for o in spec["open_points"]})
        sources.update({f"SPEC {k}": v for k, v in spec["params"].items()})
        facts = {"meta": spec["meta"], "contacts": [_contact(c) for c in spec["contacts"]], "po_revision": None}
    else:
        ecr = read_ecr(path)
        items = [{"id": c["id"], "text": f"{c['change']} | From: {c['from']} | To: {c['to']} | Reason: {c['reason']}"}
                 for c in ecr["changes"]]
        sources.update({i["id"]: i["text"] for i in items})
        sources["ECR"] = "\n".join(f"{k}: {v}" for k, v in ecr["meta"].items() if v)
        sources["ECR affected"] = "\n".join(f"{a['item']} | {a['status']} | {a['affected_by']}" for a in ecr["affected"])
        prev = ctx.station_dir_of("release", _previous(ctx.rev)) / "reviewed.json"
        if prev.exists():
            sources.update(prev_sources(json.loads(prev.read_text(encoding="utf-8"))))
        facts = {"meta": ecr["meta"], "contacts": [_contact(c) for c in ecr["contacts"]],
                 "po_revision": ecr["po_revision"]}
    return {"kind": kind, "rev": ctx.rev, "date": ctx.date, "input_file": path.name,
            **facts, "items": items, "sources": sources}


def _previous(rev):
    from ..intake import REVS
    return REVS[REVS.index(rev) - 1]


def check(ctx, facts, judgement):
    errors = []
    kind, sources = facts["kind"], facts["sources"]
    ids = [i["id"] for i in facts["items"]]
    items = judgement.get("items", [])
    refs = [i.get("ref") for i in items]
    for r in sorted({r for r in refs if refs.count(r) > 1}):
        errors.append(f"{r} 出現不只一次")
    for n, item in enumerate(items, 1):
        ref = item.get("ref")
        label = f"第 {n} 項（{ref}）"
        if ref not in ids:
            errors.append(f"{label}：{ref} 不在客戶文件的編號裡")
            continue
        cited = [ref] + item.get("sources", [])
        if kind == "dfm":
            cap = item.get("capability_sources", [])
            if not cap:
                errors.append(f"{label}：能力沒有附來源（QM-021 章節或 LL-003 條目）")
            for c in cap:
                if not (c.startswith("QM-021 ") or c.startswith("LL-003 ")):
                    errors.append(f"{label}：能力來源「{c}」不是 QM-021 章節或 LL-003 條目")
            cited += cap
        for field in ITEM_FIELDS[kind]:
            errors += field_errors(f"{label} {field}", item.get(field, ""), cited, sources)
    if kind == "impact":
        for missing in [i for i in ids if i not in refs]:
            errors.append(f"{missing}：ECR 的每個變更都要有一段判斷，這項沒有")
        if facts["po_revision"] is False and judgement.get("po_change", "").strip():
            errors.append("ECR 寫明不改 PO（No PO revision），po_change 要留空")
        errors += field_errors("po_change", judgement.get("po_change", ""), ids + ["ECR affected"], sources)
        errors += _revision_kind_errors(facts, judgement)
    for n, note in enumerate(judgement.get("notes", []), 1):
        errors += field_errors(f"備註 {n}", note.get("text", ""), note.get("sources", []), sources)
    return errors


REVISION_KINDS = {"major", "minor"}


def _revision_kind_errors(facts, judgement):
    """PLANS P54：ECR 版判大改／小改並引用 ECR；要跟 ECR 寫的 PO 改版一致。"""
    rk = judgement.get("revision_kind") or {}
    value, cited = rk.get("value"), rk.get("sources", [])
    if value not in REVISION_KINDS:
        return [f"revision_kind 要是 major 或 minor，現在是 {value!r}"]
    errors = [] if cited else ["revision_kind 要引用 ECR（例如 ECR affected）"]
    errors += [f"revision_kind 引用的出處「{i}」不存在" for i in cited if i not in facts["sources"]]
    if facts["po_revision"] is False and value != "minor":
        errors.append("revision_kind：ECR 寫明不改 PO（No PO revision），應該是 minor")
    if facts["po_revision"] is True and value != "major":
        errors.append("revision_kind：ECR 沒寫 No PO revision（要改 PO），應該是 major")
    return errors


def _recipients(facts, sender):
    domain = sender["email"].split("@")[-1]
    customer = [c for c in facts["contacts"] if not c["email"].endswith("@" + domain)]
    if facts["kind"] == "dfm":
        to = next((c for c in customer if "engineering" in c["function"].lower()), customer[0])
    else:
        name = facts["meta"]["originator"].split(",")[0].strip()
        to = next((c for c in customer if c["name"] == name), customer[0])
    return [to], [c for c in customer if c is not to]


def file_name(facts, npi_no):
    if facts["kind"] == "dfm":
        return f"{facts['date']}_DFM_Feedback_{facts['meta']['spec_no']}.eml"
    return f"{facts['date']}_ECR-{facts['meta']['seq']}_Impact_Assessment_{npi_no}.eml"


def render(ctx, facts, judgement):
    p = people()
    to, cc = _recipients(facts, p["sender"])
    template = "dfm_email.txt.j2" if facts["kind"] == "dfm" else "impact_email.txt.j2"
    subject, body = render_text(template, facts=facts, j=judgement, npi_no=ctx.npi_no,
                                sender=p["sender"], to=to[0])
    path = ctx.station_dir / file_name(facts, ctx.npi_no)
    write_eml(path, p["sender"], to, cc, subject, body, facts["date"])
    return [path]


def read_back(ctx, facts, judgement):
    path = ctx.station_dir / file_name(facts, ctx.npi_no)
    return {"kind": facts["kind"], "email": read_eml(path), "items": judgement.get("items", []),
            "notes": judgement.get("notes", []), "po_change": judgement.get("po_change", ""),
            "revision_kind": "initial" if facts["kind"] == "dfm" else judgement["revision_kind"]["value"]}

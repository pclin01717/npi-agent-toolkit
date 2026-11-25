"""成本站：單位成本表 7／8 個工作表、公式（PLANS P69～P81、表 I、表 J）。"""
import json

from .. import costing
from ..errors import NpiError
from ..intake import REVS
from ..readers import one_file, rules
from ..readers.ecr import read_ecr
from ..readers.master import FILES, read_pl, source_texts
from ..readers.ours import read_cost
from ..readers.spec import read_spec
from ..render.xlsx_out import PENDING_TEXT, write_cost
from ..sources import PENDING, field_errors, value_errors

PL_DOC = FILES["pl"].split("_")[0]          # LPC-PL-2026H2
LOT_SERVICE = "SV-REL-LOT"
NRE_KINDS = ["fixture", "test_setup", "fai", "design_qualification"]
NOT_REQUIRED = "Not required"


def _reviewed(ctx, station, rev=None):
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    if not path.exists():
        raise NpiError(f"找不到審過的結果：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _optional(ctx, station, rev):
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pick_price(price, purchase_qty):
    """P13：購買數量落在哪一段就用哪一段。回傳 (單價, 段名)。"""
    return costing.unit_price(price, purchase_qty, 1), costing.break_name(price, purchase_qty, 1)


def _price(row):
    return {"uom": row["UoM"], "base": row["Base Unit Price (USD)"],
            "breaks": [(row["Break 1 Qty ≥"], row["Break 1 Price (USD)"]), (row["Break 2 Qty ≥"], row["Break 2 Price (USD)"])]}


def prepare(ctx):
    release = _reviewed(ctx, "release")
    pl = read_pl(ctx.input_root)
    parts = {b["part_no"] for b in release["bom"]}
    sources = source_texts(ctx.input_root)
    if ctx.rev == "A0":
        spec = read_spec(one_file(ctx.rev_input_dir / "01_Customer_Draft_Spec", "*.docx"))
        sources.update({r["id"]: r["text"] for r in spec["requirements"]})
    else:
        ecr = read_ecr(one_file(ctx.rev_input_dir / "01_Customer_ECR", "*.docx"))
        sources.update({c["id"]: f"{c['change']} | From: {c['from']} | To: {c['to']}" for c in ecr["changes"]})
    previous = None if ctx.rev == "A0" else _optional(ctx, "cost", REVS[REVS.index(ctx.rev) - 1])
    if previous:
        sources["PREV costing_qty"] = str(previous["costing_qty"])
        if previous.get("quote") is not None:
            sources["PREV quote"] = f"{previous['quote']:g}"          # P72、P76（使用者 2026-11-01 同意）
    sources.update({f"ROUTING {o['op']}": f"Op {o['op']} {o['work_centre']} {o.get('description') or ''}"
                    for o in release.get("routing", [])})
    po_rev = next((r for r in reversed(REVS[: REVS.index(ctx.rev) + 1])
                   if (ctx.station_dir_of("po", r) / "reviewed.json").exists()), None)
    if po_rev:
        po = _reviewed(ctx, "po", po_rev)["po"]
        sources["PO"] = json.dumps({"po_no": po["po_no"], "rev": po["rev"], "total_qty": po["total_qty"], "from": po_rev})
        sources.update({f"PO line {s['line']}": f"line {s['line']} qty {s['qty']} need {s['need_date']}"
                        for s in po.get("schedule", [])})                 # issue #36
    dfm = _optional(ctx, "dfm", ctx.rev) or {}
    ptype = release.get("product_type", "Fiber_Array")
    params = release.get("params", {})
    count = params.get("channels") or params.get("fibres")
    people = rules.people(ctx.input_root)["NPI 負責人"]
    return {"rev": ctx.rev, "date": ctx.date, "npi_digits": ctx.npi_no.replace("NPI-", "").replace("-", ""),
            "lpc_pn": release["lpc_pn"], "description": release["description"], "bom_file": release["files"]["bom"],
            "bom": release["bom"], "routing": release.get("routing", []), "product_type": ptype,
            "routing_adds": release.get("routing_adds", []), "revision_kind": dfm.get("revision_kind", "initial"),
            "prices": {code: _price(row) for code, row in pl["materials"].items() if code in parts},
            "services_pl": {code: {"supplier": row.get("Supplier Name"), "description": row.get("Description"),
                                   "per": "pcs" if row.get("UoM") == "pcs" else "lot", "price": row.get("Unit Price\n(USD)") or row.get("Unit Price (USD)"),
                                   "min_charge": row.get("Minimum Charge (USD / order)")}
                            for code, row in pl["services"].items()},
            "rates": rules.rates(ctx.input_root),
            "ratios": {k: list(v) for k, v in rules.ratios(ctx.input_root).items()},
            "scrap": costing.scrap_rate(ptype, count, release.get("routing_adds", []), sources),
            "change_ch": {c["key"]: c["ch"] for c in release.get("changes", []) if c.get("ch")},
            "previous": previous, "prepared": {"name": people["name"], "title": people["title"]},
            "sources": sources}


def _amount_errors(label, row, sources):
    amount = row.get("amount")
    if amount in (PENDING, NOT_REQUIRED):
        if amount == NOT_REQUIRED and not row.get("sources"):
            return [f"{label}：寫 Not required 要引用出處"]
        return []
    if not (isinstance(amount, (int, float)) and amount >= 0):
        return [f"{label}：金額要是數字、「{PENDING}」或 Not required，現在是 {amount!r}"]
    return field_errors(f"{label} 金額", f"{amount:g}", row.get("sources", []), sources)


def check(ctx, facts, judgement):
    sources = facts["sources"]
    q = judgement.get("costing_qty") or {}
    value = q.get("value")
    if not (isinstance(value, (int, float)) and value > 0):
        return [f"costing_qty 要是大於 0 的數字，現在是 {value!r}"]
    errors = field_errors("costing_qty", f"{value:g}", q.get("sources", []), sources)
    for n, note in enumerate(judgement.get("notes", []), 1):
        errors += field_errors(f"備註 {n}", note.get("text", ""), note.get("sources", []), sources)
    if "scrap" not in facts:                       # 第 2 批以前的 facts
        return errors
    lot = judgement.get("lot_size") or {}
    if not (isinstance(lot.get("value"), (int, float)) and lot["value"] > 0):
        errors.append(f"lot_size（成本批量）要是大於 0 的數字，現在是 {lot.get('value')!r}")
    else:
        errors += value_errors("lot_size", lot["value"], lot.get("sources", []), sources)
    if facts["rev"] == "A0":
        tp = judgement.get("target_price") or {}
        if not (isinstance(tp.get("value"), (int, float)) and tp["value"] > 0):
            errors.append("target_price（客戶目標價）要是大於 0 的數字並引用客戶文件")
        else:
            errors += field_errors("target_price", f"{tp['value']:g}", tp.get("sources", []), sources)
    for s in judgement.get("services", []):
        code = s.get("code")
        if code == LOT_SERVICE:
            errors.append(f"services：{LOT_SERVICE} 由程式依產品類型自動加，不要寫")
        elif code not in facts["services_pl"]:
            errors.append(f"services：{code} 不在價格表的服務表")
        if not s.get("sources"):
            errors.append(f"services {code}：要引用出處（例如 ROUTING 64）")
        errors += [f"services {code}：引用的出處「{i}」不存在" for i in s.get("sources", []) if i not in sources]
    if facts["rev"] == "A0":
        kinds = [n.get("kind") for n in judgement.get("nre", [])]
        missing = [k for k in NRE_KINDS if k not in kinds]
        if missing:
            errors.append(f"nre 少了：{'、'.join(missing)}（治具、測試設定、首件檢驗、一次性設計驗證都要列，P75）")
        for n, row in enumerate(judgement.get("nre", []), 1):
            errors += _amount_errors(f"NRE 第 {n} 列", row, sources)
    else:
        if not judgement.get("ecr_nre"):
            errors.append("ECR NRE 至少要一列（金額可以待工程師填寫，P75）")
        for n, row in enumerate(judgement.get("ecr_nre", []), 1):
            errors += _amount_errors(f"ECR NRE 第 {n} 列", row, sources)
    errors += _scrap_errors(facts, judgement)
    return errors


def _scrap_errors(facts, judgement):
    over = judgement.get("scrap_rate_override")
    if not over:
        return []
    scrap, sources = facts["scrap"], facts["sources"]
    if scrap["value"] != PENDING:
        return [f"報廢率已經照表 J 判成 {scrap['value']:g}（{scrap['source']}），不能覆寫"]
    value, cited = over.get("value"), over.get("sources", [])
    if not (isinstance(value, (int, float)) and 0 <= value < 1):
        return [f"scrap_rate_override 要是 0～1 的比率，現在是 {value!r}"]
    if any(c.startswith("ENG-") for c in cited):
        return field_errors("scrap_rate_override", f"{value:g}", cited, sources)
    for key in cited:
        if key in scrap["candidates"] and costing.rate_of(sources, key) == value:
            return []
    return [f"scrap_rate_override：要引用候選列之一（{'、'.join(scrap['candidates'])}）而且值相同，"
            "或引用工程師給的 ENG-n"]


def file_name(facts):
    return f"LPC-UC-{facts['npi_digits']}_Rev{facts['rev']}_Unit_Cost.xlsx"


def _basis(cited, sources):
    return "；".join(f"{i}：{sources[i]}" if i in sources else i for i in cited)


def _book(facts, judgement):
    """把 facts、判讀整理成成本表的輸入（xlsx 和 costing.model 用同一份）。"""
    sources, prev = facts["sources"], facts["previous"]
    ratios = {k: v[0] for k, v in facts["ratios"].items()}
    lines, rows = [], []
    for b in facts["bom"]:
        if b["make_buy"] != "Buy":
            continue
        qty = b.get("ext_qty", b["qty_per"])
        price = facts["prices"].get(b["part_no"])
        basis, ok = f"{PL_DOC} {b['part_no']}", True
        if price is None:
            basis, ok = f"Not in {PL_DOC}", False
        elif price["uom"] != b["uom"]:
            basis, ok = f"UoM differs: BOM {b['uom']} / {PL_DOC} {price['uom']}", False
        p = {"base": price["base"], "breaks": [tuple(x) for x in price["breaks"]]} if ok else None
        lines.append({"item": b["item"], "part_no": b["part_no"], "description": b["description"],
                      "category": b.get("category"), "qty": qty, "uom": b["uom"], "price": p, "price_doc": basis})
        (b1q, b1p), (b2q, b2p) = p["breaks"] if p else ((None, None), (None, None))
        rows.append({"item": b["item"], "part_no": b["part_no"], "description": b["description"],
                     "category": b.get("category"), "qty": qty, "uom": b["uom"], "base": p and p["base"],
                     "b1q": b1q, "b1p": b1p, "b2q": b2q, "b2p": b2p, "basis": basis,
                     "status": PENDING_TEXT if qty is None or not ok else ""})
    codes = ([LOT_SERVICE] if facts["product_type"] == "Fiber_Array" else []) + \
            [s["code"] for s in judgement.get("services", [])]
    services = [{"code": c, **facts["services_pl"][c]} for c in codes]
    svc_basis = {LOT_SERVICE: "RULES §3 每批驗證（光纖陣列每批一次）"}
    svc_basis.update({s["code"]: ", ".join(s.get("sources", [])) for s in judgement.get("services", [])})
    conversion = [{"op": o["op"], "description": o.get("description"), "work_centre": o["work_centre"],
                   "setup": o.get("setup_min"), "run": o.get("run_min"), "rate": facts["rates"][o["work_centre"]]}
                  for o in facts["routing"] if o["work_centre"] != "SUB"]
    scrap = facts["scrap"]
    over = judgement.get("scrap_rate_override")
    if over:
        scrap_value, scrap_basis = over["value"], _basis(over["sources"], sources)
    elif scrap["value"] != PENDING:
        scrap_value, scrap_basis = scrap["value"], _basis([scrap["source"]], sources)
    else:
        scrap_value, scrap_basis = None, "候選：" + "、".join(scrap["candidates"]) + "（表 J：符合的列不是剛好一列）"  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
    lot, cq = judgement["lot_size"], judgement["costing_qty"]
    minor = facts["revision_kind"] == "minor"
    prev_quote = prev.get("quote") if prev else None
    if facts["rev"] == "A0":
        target, target_basis = judgement["target_price"]["value"], _basis(judgement["target_price"]["sources"], sources)
    else:
        target, target_basis = prev_quote, "PREV quote（上一版報價；ECR 沒有客戶目標價，P76）"  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
    params = [("Costing order qty", cq["value"], "pcs", _basis(cq.get("sources", []), sources), ""),
              ("Cost lot size", lot["value"], "pcs", _basis(lot.get("sources", []), sources), ""),
              ("Scrap rate", scrap_value, "ratio", scrap_basis, "" if scrap_value is not None else PENDING_TEXT)]
    names = {"handling": "Material handling rate", "overhead": "Manufacturing overhead rate", "sga": "SG&A rate",
             "margin": "Target margin", "rounding": "Quote rounding (USD)"}
    params += [(names[k], ratios[k], "USD" if k == "rounding" else "ratio", _basis([facts["ratios"][k][1]], sources), "")
               for k in names]
    params.append(("Target / comparison price", target, "USD", target_basis, "" if target is not None else PENDING_TEXT))
    quote_basis = (f"沿用 {prev['rev']} 報價（作業規則 §5 小改不重新報價）" if minor and prev
                   else "Total cost / (1 - target margin), rounded up")
    if minor:
        params.append(("Quote kept from previous revision", prev_quote, "USD", quote_basis,
                       "" if prev_quote is not None else PENDING_TEXT))
    inputs = {"lines": lines, "services": [{"code": s["code"], "per": s["per"], "price": s["price"],
                                            "min_charge": s["min_charge"]} for s in services],
              "conversion": [{k: c[k] for k in ("op", "work_centre", "setup", "run", "rate")} for c in conversion],
              "params": {"costing_qty": cq["value"], "lot_size": lot["value"], "scrap_rate": scrap_value, **ratios}}
    if minor:
        inputs["quote_kept"] = prev_quote

    def nre_rows(items):
        return [(n.get("kind"), n.get("name"), n["amount"] if isinstance(n.get("amount"), (int, float)) else None,
                 _basis(n.get("sources", []), sources),
                 PENDING_TEXT if n.get("amount") == PENDING else n.get("amount") if n.get("amount") == NOT_REQUIRED else "")
                for n in items]
    book = {"params": params, "lines": rows,
            "services": [{**s, "basis": svc_basis.get(s["code"], ""), "status": ""} for s in services],
            "conversion": [{**c, "status": PENDING_TEXT if c["run"] is None else ""} for c in conversion],
            "rates": [(wc, rate, f"RULES §3 工作站費率 {wc}") for wc, rate in facts["rates"].items()],
            "nre": nre_rows(judgement.get("nre", [])) + nre_rows(judgement.get("ecr_nre", [])),
            "approval": [("Prepared", facts["prepared"]["name"], facts["prepared"]["title"], facts["date"], "Prepared"),
                         ("Reviewed", None, None, None, "待確認"), ("Finance confirmed", None, None, None, "待確認")],
            "minor_quote": minor, "quote_basis": quote_basis, "target_basis": target_basis, "delta": None}
    return book, inputs


ELEMENT_KEYS = {"Total cost": "total", "Quote price": "quote", "Gross margin": "margin"}


def _delta(facts, judgement, inputs):
    prev = facts["previous"]
    if not prev:
        return None
    ch_of = dict(facts["change_ch"])
    for s in judgement.get("services", []):              # 服務照它引用的工序對到 CH（例如 ROUTING 64 → Op 64）
        for src in s.get("sources", []):
            op = src.replace("ROUTING ", "Op ", 1)
            if op in ch_of:
                ch_of[s["code"]] = ch_of[op]
    values = {**prev.get("elements", {}), **{name: prev.get(key) for name, key in ELEMENT_KEYS.items()}}
    names = {"costing_qty": "計價數量", "lot_size": "成本批量", "scrap_rate": "報廢率", "handling": "物料管理費率",
             "overhead": "製造費用率", "sga": "管銷率"}
    old_p, new_p = prev["inputs"]["params"], inputs["params"]
    changed = [f"{label} {old_p.get(k)} → {new_p.get(k)}" for k, label in names.items() if old_p.get(k) != new_p.get(k)]
    basis = {costing.PARAM_ROW: "、".join(changed) or "參數沒有變",
             costing.OTHER_ROW: "差額沒有對到任何 CH"}
    drivers = [(label, round(value, 6), basis.get(label, facts["sources"].get(label, "")))
               for label, value in costing.delta(prev["inputs"], inputs, ch_of)]
    return {"prev": prev["rev"], "prev_values": values, "drivers": drivers}


def render(ctx, facts, judgement):
    book, inputs = _book(facts, judgement)
    book["delta"] = _delta(facts, judgement, inputs)
    path = ctx.station_dir / file_name(facts)
    write_cost(path, {"doc_no": f"LPC-UC-{facts['npi_digits']}", "rev": facts["rev"],
                      "product": f"{facts['lpc_pn']} / {facts['description']}", "npi_no": ctx.npi_no,
                      "date": facts["date"], "basis": f"BOM {facts['bom_file']}; {PL_DOC}; LPC作業規則 §3"}, book)
    return [path]


def read_back(ctx, facts, judgement):
    cost = read_cost(ctx.station_dir / file_name(facts))
    book, _ = _book(facts, judgement)
    return {"rev": facts["rev"], "lpc_pn": facts["lpc_pn"], "costing_qty": cost["params"]["costing_qty"],
            "lot_size": cost["params"]["lot_size"], "scrap_rate": cost["params"]["scrap_rate"],
            "quote_basis": book["quote_basis"], "file": file_name(facts), **cost}

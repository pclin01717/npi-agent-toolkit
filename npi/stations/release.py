"""工程發行站：正式 spec（docx）、BOM（xlsx）、圖面（PDF）、STEP（基座、組件）。"""
import json
import re

from .. import params as P
from .. import registry as reg
from ..errors import NpiError
from ..intake import REVS
from ..readers import one_file
from ..readers.ecr import read_ecr
from ..readers import rules
from ..readers.master import read_mm002, source_texts
from ..readers.ours import read_bom, read_routing, read_spec_doc
from ..readers.spec import read_spec
from ..render.docx_out import write_spec_doc
from ..render.drawing_pdf import write_drawing, write_fanout_drawing
from ..render.step_cad import write_fanout_steps, write_steps
from ..render.xlsx_out import CHANNEL_CHECK, FANOUT_MAP_HEADS, write_bom
from ..sources import PENDING, field_errors, value_errors

PN = re.compile(r"^LPC-[A-Z0-9][A-Z0-9-]*$")
MAKE_BUY = {"Make", "Buy"}
NOT_IN_MM = "NOT IN LPC-MM-002"
CHANNEL_CHECK_CELL = f"Channel Map!{CHANNEL_CHECK}"
CATEGORIES = {"MFG", "RM", "BUY", "PKG", "CON"}
KINDS = {"base", "pm", "prebake", "coating", "incoming"}
ADDS = {"PM": "pm", "coating": None}
SETUP_RULE, SETUP_DEFAULT = "RULES §4 整備時間", 20


def level_of(item):
    """PLANS P61：項次決定階。0 → 0 階；沒有點 → 1 階；一個點 → 2 階；再多點不收。"""
    parts = str(item).split(".")
    if parts == ["0"]:
        return 0
    if len(parts) > 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"項次「{item}」只能是 10 或 10.10 這種寫法（最多 2 階）")
    return len(parts)


def parent_of(item):
    level = level_of(item)
    return None if level == 0 else "0" if level == 1 else str(item).split(".")[0]


def category_of(make_buy, mm_category, children=()):
    """PLANS 表 H。回傳 None 表示要 agent 判讀（第 8 列）。"""
    if make_buy == "Make":
        kids = set(children)
        return kids.pop() if len(kids) == 1 and kids <= {"PKG", "CON"} else "MFG"
    cat = mm_category or ""
    if cat == "Consumable - Optical Epoxy":
        return "RM"
    if cat == "Purchased Part - Protection":
        return "PKG"
    for prefix, code in (("Raw Material", "RM"), ("Purchased Part", "BUY"), ("Packaging", "PKG"), ("Consumable", "CON")):
        if cat.startswith(prefix):
            return code
    return None


def fibres_per_mpo(connector):
    m = re.search(r"MPO-(\d+)", connector or "")
    return int(m.group(1)) if m else None


def mpo_position(channel, per_mpo):
    return (channel - 1) // per_mpo + 1, (channel - 1) % per_mpo + 1


def _upstream(ctx, station, rev=None):
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    if not path.exists():
        raise NpiError(f"找不到審過的結果：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(ctx):
    decisions = ctx.station_dir.parent / "decisions.json"
    if not decisions.exists():
        raise NpiError(f"{ctx.rev} 還沒有客戶決定")
    sources = source_texts(ctx.input_root)
    dfm = _upstream(ctx, "dfm")
    sources["DFM email"] = dfm["email"]["body"]
    decision_text = json.loads(decisions.read_text(encoding="utf-8"))["text"]
    sources["DECISIONS"] = decision_text
    mm = read_mm002(ctx.input_root)
    people = rules.people(ctx.input_root)
    facts = {"rev": ctx.rev, "date": ctx.date, "npi_digits": ctx.npi_no.replace("NPI-", "").replace("-", ""),
             "decisions": decision_text, "mm002_codes": sorted(mm),
             "mm002_categories": {code: row.get("Category") for code, row in mm.items()},
             "rules": {"base_routing": rules.base_routings(ctx.input_root),
                       "work_centres": sorted(rules.rates(ctx.input_root))},
             "people": {"prepared": people["NPI 負責人"]["name"], "approved": people["工程主管"]["name"]}}
    if ctx.rev == "A0":
        spec_path = one_file(ctx.rev_input_dir / "01_Customer_Draft_Spec", "*.docx")
        spec = read_spec(spec_path)
        sources.update({r["id"]: r["text"] for r in spec["requirements"]})
        sources.update({f"SPEC {k}": v for k, v in spec["params"].items()})
        facts.update(kind="a0", cust_pn=spec["meta"]["part_no"], customer_doc=spec["meta"], previous=None)
    else:
        ecr = read_ecr(one_file(ctx.rev_input_dir / "01_Customer_ECR", "*.docx"))
        for c in ecr["changes"]:
            sources[c["id"]] = f"{c['change']} | From: {c['from']} | To: {c['to']} | Reason: {c['reason']}"
        previous = _upstream(ctx, "release", REVS[REVS.index(ctx.rev) - 1])
        sources.update(P.prev_sources(previous))
        sources["PREV product_type"] = previous.get("product_type", "Fiber_Array")   # PLANS P36
        sources.update({f"PREV routing_adds {a}": a for a in previous.get("routing_adds", [])})
        facts.update(kind="ecr", cust_pn=ecr["meta"]["part_no"], customer_doc=ecr["meta"],
                     change_ids=[c["id"] for c in ecr["changes"]], previous=previous)
    facts["sources"] = sources
    timeline = ctx.station_dir.parent / "timeline.json"           # P56：只看日期不晚於這版收件日的號碼
    as_of = json.loads(timeline.read_text(encoding="utf-8"))["events"][0]["date"] if timeline.exists() else ctx.date
    facts["registry"] = {"used": sorted(reg.used(reg.load(ctx.out_root), as_of, f"{ctx.npi_no} {ctx.rev}")),
                         "prev_pn": facts["previous"]["lpc_pn"] if facts["previous"] else None}
    return facts


def _type_errors(facts, judgement):
    """PLANS P36：產品類型要引用出處；ECR 版不能換類型。"""
    ptype, cited = judgement["product_type"], judgement.get("product_type_sources", [])
    errors = [] if cited else ["product_type 要有 product_type_sources（引用客戶文件，ECR 版引用 PREV product_type）"]
    errors += [f"product_type 引用的出處「{i}」不存在" for i in cited if i not in facts["sources"]]
    if facts["kind"] == "ecr":
        prev = facts["previous"].get("product_type", "Fiber_Array")
        if ptype != prev:
            errors.append(f"產品類型不能在 ECR 改（上一版 {prev} → {ptype}）")
    return errors


def _param_errors(facts, judgement):
    errors, sources = [], facts["sources"]
    spec = P.TYPES[judgement["product_type"]]
    params = judgement.get("params", {})
    missing = [k for k in P.required(judgement["product_type"]) if k not in params]
    if missing:
        return [f"缺少關鍵參數：{'、'.join(missing)}"]
    for k in P.required(judgement["product_type"]):
        p = params[k]
        value, cited = p.get("value"), p.get("sources", [])
        zero_ok = k in spec["zero_ok"]   # 0° 平面端面、0 mm 公差是合法的
        if k in spec["numeric"] and not (isinstance(value, (int, float)) and (value >= 0 if zero_ok else value > 0)):
            errors.append(f"參數 {k}：要是{'不小於' if zero_ok else '大於'} 0 的數字（圖面和 STEP 要用），現在是 {value!r}")
            continue
        errors += field_errors(f"參數 {k}", P.fmt(value), cited, sources)
    if judgement["product_type"] == "Fanout":
        errors += P.fanout_errors(P.values(params))
    return errors


def _change_errors(facts, judgement):
    if facts["kind"] != "ecr":
        return []
    errors = []
    changes = judgement.get("changes", {})
    for k, ch in changes.items():
        if ch not in facts["change_ids"]:
            errors.append(f"參數「{k}」對應的 {ch} 不在 ECR 裡")
    prev, new = facts["previous"]["params"], P.values(judgement.get("params", {}))
    for k in P.required(judgement["product_type"]):
        if k in new and new[k] != prev.get(k) and k not in changes:
            errors.append(f"參數「{k}」跟上一版不同（{P.fmt(prev.get(k))} → {P.fmt(new[k])}），但沒有對應的 CH")
    return errors


def _consistency_errors(judgement):
    if judgement["product_type"] != "Fiber_Array":   # PLANS P43：fan-out 不檢查文字裡的芯數
        return []
    ch = P.values(judgement.get("params", {})).get("channels")
    texts = [(f"spec 第 {n} 節", s.get("text", "")) for n, s in enumerate(judgement.get("spec_sections", []), 1)]
    texts += [(f"BOM {b.get('item')}", b.get("description", "")) for b in judgement.get("bom", [])]
    return [f"{label}：寫了 {m} 通道，跟關鍵參數 channels = {P.fmt(ch)} 不一致"
            for label, text in texts for m in P.channel_mentions(text) if m != ch]


def _bom_errors(facts, judgement):
    errors, sources = [], facts["sources"]
    for b in judgement.get("bom", []):
        label = f"BOM {b.get('item')}（{b.get('part_no')}）"
        if not b.get("part_no"):
            errors.append(f"{label}：沒有料號")
        if b.get("make_buy") not in MAKE_BUY:
            errors.append(f"{label}：Make/Buy 要是 {'／'.join(sorted(MAKE_BUY))}")
        cited = list(b.get("sources", []))
        if f"MM-002 {b.get('part_no')}" in sources:
            cited.append(f"MM-002 {b['part_no']}")
        qty = b.get("qty_per")
        group = b.get("make_buy") == "Make" and any(str(k.get("item", "")).startswith(f"{b.get('item')}.")
                                                    for k in judgement.get("bom", []))
        if group and qty != 1:
            errors.append(f"{label}：分組列（底下有 2 階料）用量要是 1（PLANS P82）")
        elif group:
            pass                                       # 分組列用量固定 1，不查出處（P82）
        elif qty != PENDING:
            if not (isinstance(qty, (int, float)) and qty > 0):
                errors.append(f"{label}：用量要是大於 0 的數字或「{PENDING}」")
            else:
                errors += field_errors(f"{label} 用量", P.fmt(qty), cited, sources)
        errors += field_errors(f"{label} 品名", b.get("description", ""), cited, sources)
        for field in ("uom", "remark"):
            errors += field_errors(f"{label} {field}", str(b.get(field) or ""), cited, sources)
    return errors


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _op_ids(op):
    """「30」或「30-70」→ ["30"] 或 ["30", "70"]。"""
    return [s.strip() for s in str(op).split("-")]


def _routing_errors(facts, judgement):
    """PLANS P63。"""
    ops, sources = judgement.get("routing") or [], facts["sources"]
    if not ops:
        return ["routing 是空的：要照作業規則 §4 排工序"]
    errors, seen = [], set()
    centres = set(facts["rules"]["work_centres"])
    for o in ops:
        label = f"Routing Op {o.get('op')}"
        if o.get("op") in seen:
            errors.append(f"{label}：工序號重複")
        seen.add(o.get("op"))
        wc, kinds = o.get("work_centre"), o.get("kinds") or []
        if wc == "REL":
            errors.append(f"{label}：批次驗證（REL）另計，算在成本的 Services，不放進 Routing（作業規則 §4）")
        elif wc != "SUB" and wc not in centres:
            errors.append(f"{label}：工作站 {wc} 不在作業規則 §3 的費率表裡（外包寫 SUB）")
        if not kinds or set(kinds) - KINDS:
            errors.append(f"{label}：kinds 要是 {'、'.join(sorted(KINDS))} 其中幾個，現在是 {kinds}")
        if wc == "SUB":
            continue
        setup = o.get("setup_min") or {}
        value, cited = setup.get("value"), setup.get("sources", [])
        if not _number(value):
            errors.append(f"{label}：整備時間要是數字")
        elif any(c.startswith("ENG-") for c in cited):
            errors += value_errors(f"{label} 整備時間", value, [SETUP_RULE] + cited, sources)
        elif value != SETUP_DEFAULT or SETUP_RULE not in cited:
            errors.append(f"{label}：整備時間要是 {SETUP_DEFAULT} 分鐘並引用「{SETUP_RULE}」（BRIEF 3-2）；"
                          "工程師給別的值要用 tell 並引用 ENG-n")
        run = o.get("run_min") or {}
        if run.get("value") != PENDING:
            if not (_number(run.get("value")) and run["value"] > 0):
                errors.append(f"{label}：單件時間要是大於 0 的數字或「{PENDING}」")
            else:
                errors += field_errors(f"{label} 單件時間", P.fmt(run["value"]), run.get("sources", []), sources)
    template = facts["rules"]["base_routing"][judgement["product_type"]]
    base = [o.get("work_centre") for o in ops if "base" in (o.get("kinds") or [])]
    if len(base) != len(template) or any(wc not in alts for wc, alts in zip(base, template)):
        errors.append(f"基本工序要依序是 {' → '.join('/'.join(a) for a in template)}（作業規則 §4），"
                      f"現在是 {' → '.join(map(str, base)) or '（沒有）'}")
    adds = judgement.get("routing_adds") or []
    for a in adds:
        if a.get("add") not in ADDS:
            errors.append(f"routing_adds：不認得「{a.get('add')}」（只有 {'、'.join(ADDS)}）")
        if not a.get("sources"):
            errors.append(f"routing_adds {a.get('add')}：要引用出處")
        errors += [f"routing_adds {a.get('add')}：引用的出處「{i}」不存在" for i in a.get("sources", []) if i not in sources]
    names = {a.get("add") for a in adds}
    if "PM" in names and sum(1 for o in ops if "pm" in (o.get("kinds") or []) and o.get("work_centre") == "PMA") < 2:
        errors.append("有 PM 光纖要有兩道 pm 工序（工作站 PMA：慢軸對位、接頭鍵位對位，作業規則 §4）")
    if "coating" in names:
        for kind in ("prebake", "coating", "incoming"):
            if not any(kind in (o.get("kinds") or []) for o in ops):
                errors.append(f"有鍍膜要有 {kind} 工序（預烤、外包鍍膜、進料檢驗，作業規則 §4）")
    return errors


def _structure_errors(facts, judgement):
    """PLANS P61、P62、P64：階、上一階、工序、類別。"""
    errors, sources = [], facts["sources"]
    rows = judgement.get("bom", [])
    items = {"0", "10"} | {str(b.get("item")) for b in rows}
    ops = {str(o.get("op")) for o in judgement.get("routing") or []}
    for b in rows:
        label = f"BOM {b.get('item')}（{b.get('part_no')}）"
        try:
            parent = parent_of(b.get("item"))
        except ValueError as e:
            errors.append(f"{label}：{e}")
            continue
        if parent not in items:
            errors.append(f"{label}：上一階 {parent} 不在 BOM 裡")
        missing = [o for o in _op_ids(b.get("op") or "") if o not in ops]
        if not b.get("op") or missing:
            errors.append(f"{label}：工序 {b.get('op')!r} 不在 Routing 裡（每列要寫 op）")
        if b.get("make_buy") == "Buy" and category_of("Buy", facts["mm002_categories"].get(b.get("part_no"))) is None:
            cat = b.get("category")
            if cat == PENDING:
                continue
            if cat not in CATEGORIES:
                errors.append(f"{label}：MM-002 沒有可用的分類，類別要寫 {'、'.join(sorted(CATEGORIES))} 或「{PENDING}」")
            elif not b.get("category_sources"):
                errors.append(f"{label}：類別 {cat} 要引用出處（category_sources）")
            else:
                errors += [f"{label}：類別引用的出處「{i}」不存在" for i in b["category_sources"] if i not in sources]
    return errors


def _channel_errors(facts, judgement):
    if judgement["product_type"] != "Fiber_Array":
        return []
    errors = []
    for n, c in enumerate(judgement.get("channel_map") or [], 1):
        label = f"Channel Map 第 {n} 列（通道 {c.get('channel')}）"
        if not (isinstance(c.get("channel"), int) and c["channel"] > 0):
            errors.append(f"{label}：通道號要是正整數")
        for field in ("function", "fibre"):
            errors += field_errors(f"{label} {field}", str(c.get(field) or ""), c.get("sources", []), facts["sources"])
    return errors


def bom_rows(facts, judgement):
    """BOM 每一列（含程式加的 item 0、10）：階、類別、工序、不在 MM-002 的標示。"""
    spec = P.TYPES[judgement["product_type"]]
    v = P.values(judgement["params"])
    mm, cats = set(facts["mm002_codes"]), facts["mm002_categories"]
    rows = []
    for b in judgement.get("bom", []):
        remark = b.get("remark", "")
        if b["make_buy"] == "Buy" and b["part_no"] not in mm:
            remark = f"{NOT_IN_MM}; {remark}".strip("; ")
        cat = category_of("Buy", cats.get(b["part_no"])) if b["make_buy"] == "Buy" else None
        rows.append({**{k: b.get(k) for k in ("item", "part_no", "description", "make_buy", "qty_per", "uom")},
                     "op": b.get("op"), "category": cat or b.get("category", PENDING) if b["make_buy"] == "Buy" else None,
                     "remark": f"Op {b.get('op')}" + (f"; {remark}" if remark else "")})
    block_ops = sorted({o for r in rows if str(r["item"]).startswith("10.") for o in _op_ids(r["op"])}, key=float)
    block_op = "-".join(dict.fromkeys([block_ops[0], block_ops[-1]])) if block_ops else ""
    rows = [{"item": "0", "part_no": judgement["lpc_pn"], "description": spec["description"](v), "make_buy": "Make",
             "qty_per": 1, "uom": "pcs", "op": None, "category": None, "remark": ""},
            {"item": "10", "part_no": judgement["block_pn"], "description": spec["block_description"], "make_buy": "Make",
             "qty_per": 1, "uom": "pcs", "op": block_op, "category": None, "remark": f"Op {block_op}" if block_op else ""}] + rows
    for r in rows:
        r["level"] = level_of(r["item"])
        if r["make_buy"] == "Make":
            kids = [k["category"] for k in rows if parent_of(k["item"]) == r["item"] and r["item"] != "0"]
            r["category"] = category_of("Make", None, kids)
    return rows                                      # 展開用量在 xlsx 寫公式、讀回時重算（P61），這裡不算


def bom_diff(prev_bom, rows):
    """PLANS P66：比所有列（含 Make 列），成品料號（item 0）換版不算；料號待填的不比。"""
    def keyed(bom):
        return {b["part_no"]: b for b in bom if str(b["item"]) != "0" and b["part_no"] not in (None, PENDING)}
    old, new = keyed(prev_bom), keyed(rows)
    out = [("BOM", "Removed", old[p]["item"], p, old[p]["qty_per"], "") for p in old if p not in new]
    out += [("BOM", "Added", new[p]["item"], p, "", new[p]["qty_per"]) for p in new if p not in old]
    out += [("BOM", "Qty changed", new[p]["item"], p, old[p]["qty_per"], new[p]["qty_per"])
            for p in new if p in old and _number(old[p]["qty_per"]) and _number(new[p]["qty_per"])
            and old[p]["qty_per"] != new[p]["qty_per"]]                  # 待填和數字之間不算變更（issue #39）
    return out


def _times(o):
    def value(x):
        v = (x or {}).get("value") if isinstance(x, dict) else x
        return v if _number(v) else None
    return o.get("work_centre"), value(o.get("setup_min")), value(o.get("run_min"))


def _changed(a, b):
    """工作站不同就算；時間只在兩邊都是數字時才比（待填和數字之間不算，issue #39）。"""
    return a[0] != b[0] or any(x is not None and y is not None and x != y for x, y in zip(a[1:], b[1:]))


def routing_diff(prev_routing, routing):
    old = {str(o["op"]): o for o in prev_routing}
    new = {str(o["op"]): o for o in routing}
    out = [("Routing", "Removed", op, f"Op {op}", old[op]["work_centre"], "") for op in old if op not in new]
    out += [("Routing", "Added", op, f"Op {op}", "", new[op]["work_centre"]) for op in new if op not in old]
    out += [("Routing", "Changed", op, f"Op {op}", " / ".join(map(str, _times(old[op]))), " / ".join(map(str, _times(new[op]))))
            for op in new if op in old and _changed(_times(old[op]), _times(new[op]))]
    return out


def changes(facts, judgement, rows):
    if facts["kind"] != "ecr":
        return None
    prev = facts["previous"]
    return bom_diff(prev["bom"], rows) + routing_diff(prev.get("routing", []), judgement.get("routing") or [])


def _change_map_errors(facts, judgement, rows):
    if facts["kind"] != "ecr":
        return []
    cmap = judgement.get("change_map") or {}
    errors = [f"Change Summary：{key} 沒有對到 CH（change_map）" for _, _, _, key, _, _ in changes(facts, judgement, rows)
              if key not in cmap]
    errors += [f"change_map：{key} 對到的 {ch} 不在 ECR 裡" for key, ch in cmap.items() if ch not in facts["change_ids"]]
    return errors


def revisions(facts):
    prev = facts["previous"].get("revisions", []) if facts["previous"] else []
    if facts["kind"] == "a0":
        zone, text = "—", "Initial release"
    else:
        zone = ", ".join(facts["change_ids"])
        text = f"{facts['customer_doc'].get('ecr_no', 'ECR')}: {zone}"
    return prev + [{"rev": facts["rev"], "date": facts["date"], "zone": zone, "description": text,
                    "prepared": facts["people"]["prepared"], "approved": facts["people"]["approved"]}]


def channel_sheet(judgement):
    v = P.values(judgement["params"])
    if judgement["product_type"] == "Fanout":
        return {"heads": FANOUT_MAP_HEADS, "rows": [list(r) for r in P.port_map(v)], "expected": v["fibres"]}
    per = fibres_per_mpo(v["connector"])
    rows = []
    for c in judgement.get("channel_map") or []:
        mpo, pos = mpo_position(c["channel"], per) if per else (PENDING, PENDING)
        rows.append([c["channel"], c["channel"], mpo, pos, c.get("function"), c.get("fibre"),
                     round((c["channel"] - 1) * v["pitch_um"], 3)])
    return {"heads": None, "rows": rows, "expected": v["channels"]}


def routing_sheet(judgement):
    out = []
    for o in judgement.get("routing") or []:
        setup, run = o.get("setup_min") or {}, o.get("run_min") or {}
        out.append([o["op"], o.get("description"), o.get("work_centre"), setup.get("value"), run.get("value"),
                    ", ".join(o.get("kinds") or []), ", ".join(setup.get("sources", [])), ", ".join(run.get("sources", []))])
    return out


def check(ctx, facts, judgement):
    errors = []
    for key in ("lpc_pn", "block_pn"):
        if not PN.match(str(judgement.get(key, ""))):
            errors.append(f"{key} 要是 LPC- 開頭的料號，現在是 {judgement.get(key)!r}")
    if judgement.get("lpc_pn") == judgement.get("block_pn"):
        errors.append("lpc_pn 和 block_pn 不能一樣")
    if "registry" in facts and PN.match(str(judgement.get("lpc_pn", ""))):   # P55
        errors += reg.product_pn_errors(judgement["lpc_pn"], facts["registry"]["prev_pn"],
                                        set(facts["registry"]["used"]))
    if judgement.get("product_type") not in P.TYPES:
        return errors + [f"不支援的產品類型「{judgement.get('product_type')}」，目前只支援 {'、'.join(P.TYPES)}；"
                         "認不出來就停下回報，不要硬套"]
    errors += _type_errors(facts, judgement)
    errors += _param_errors(facts, judgement)
    for n, s in enumerate(judgement.get("spec_sections", []), 1):
        for field in ("title", "text"):
            errors += field_errors(f"spec 第 {n} 節 {field}", s.get(field, ""), s.get("sources", []), facts["sources"])
    errors += _bom_errors(facts, judgement)
    if "params" in judgement:
        errors += _consistency_errors(judgement) + _change_errors(facts, judgement)
    if "rules" in facts:                                     # 第 3 批（STEP 10）
        errors += _routing_errors(facts, judgement) + _structure_errors(facts, judgement) + _channel_errors(facts, judgement)
        if not errors:
            errors += _change_map_errors(facts, judgement, bom_rows(facts, judgement))
    return errors


def file_names(facts, judgement):
    n, rev = facts["npi_digits"], facts["rev"]
    return {"spec": f"LPC-PS-{n}_Rev{rev}_Product_Specification.docx",
            "bom": f"LPC-BOM-{n}_Rev{rev}_BOM.xlsx",
            "drawing": f"LPC-DWG-{n}_Rev{rev}_{judgement['product_type']}_Drawing.pdf",
            "block_step": f"{judgement['block_pn']}_Rev{rev}.step",
            "step": f"{judgement['lpc_pn']}_Rev{rev}.step"}


def render(ctx, facts, judgement):
    v = P.values(judgement["params"])
    spec = P.TYPES[judgement["product_type"]]
    names = {k: ctx.station_dir / name for k, name in file_names(facts, judgement).items()}
    n, rev = facts["npi_digits"], facts["rev"]
    desc = spec["description"](v)
    common = {"rev": rev, "date": facts["date"], "lpc_pn": judgement["lpc_pn"], "npi_no": ctx.npi_no}
    write_spec_doc(names["spec"], {**common, "doc_no": f"LPC-PS-{n}", "cust_pn": facts["cust_pn"],
                                   "description": desc}, v, judgement.get("spec_sections", []), spec)
    rows = bom_rows(facts, judgement)
    change_rows = changes(facts, judgement, rows)
    cmap = judgement.get("change_map") or {}
    write_bom(names["bom"], {**common, "doc_no": f"LPC-BOM-{n}", "product": f"{judgement['lpc_pn']} / {desc}"}, rows,
              {"channel_map": channel_sheet(judgement), "routing": routing_sheet(judgement),
               "revisions": [list(r.values()) for r in revisions(facts)],
               "changes": None if change_rows is None else [list(c) + [cmap.get(c[3], "")] for c in change_rows]})
    if judgement["product_type"] == "Fanout":
        write_fanout_drawing(names["drawing"], {**common, "doc_no": f"LPC-DWG-{n}"}, v)
        write_fanout_steps(names["block_step"], names["step"], v, facts["date"])
    else:
        write_drawing(names["drawing"], {**common, "doc_no": f"LPC-DWG-{n}"}, v)
        write_steps(names["block_step"], names["step"], v, facts["date"])
    return [names[k] for k in ("spec", "bom", "drawing", "block_step", "step")]


def cust_rev(facts):
    """客戶版次：A0 取客戶圖號後的 Rev（例如 KVP-DWG-2408 Rev A）；ECR 取改版後的客戶版次。找不到回傳 None。"""
    if facts["kind"] == "ecr":
        return facts["customer_doc"].get("proposed_cust_rev")
    m = re.search(r"\bRev\s+([A-Z])\b", facts["customer_doc"].get("drawing") or "")
    return m.group(1) if m else None


def read_back(ctx, facts, judgement):
    names = {k: ctx.station_dir / name for k, name in file_names(facts, judgement).items()}
    spec = read_spec_doc(names["spec"])
    planned = P.values(judgement["params"])
    edited = [f"{k} {P.fmt(planned[k])} → {P.fmt(spec['params'].get(k))}" for k in P.required(judgement["product_type"])
              if spec["params"].get(k) != planned[k]]
    if edited:
        raise NpiError(f"{names['spec'].name} 的關鍵參數被改了：{'；'.join(edited)}。BOM、圖面、STEP 不會跟著改，"
                       "請把 spec 改回來，或 reopen 工程發行、改判讀檔後重跑")
    return {"rev": facts["rev"], "lpc_pn": judgement["lpc_pn"], "block_pn": judgement["block_pn"],
            "product_type": judgement["product_type"], "cust_pn": facts["cust_pn"], "cust_rev": cust_rev(facts),
            "params": spec["params"], "description": P.TYPES[judgement["product_type"]]["description"](spec["params"]),
            "sections": spec["sections"], "bom": read_bom(names["bom"]), "routing": read_routing(names["bom"]),
            "routing_adds": [a["add"] for a in judgement.get("routing_adds") or []], "revisions": revisions(facts),
            "changes": [{"key": c[3], "change": c[1], "ch": (judgement.get("change_map") or {}).get(c[3])}
                        for c in changes(facts, judgement, bom_rows(facts, judgement)) or []],
            "files": {k: p.name for k, p in names.items()}}

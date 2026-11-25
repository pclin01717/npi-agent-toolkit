"""PLANS 表 I、表 J、P73、P74、P76、P81：單位成本的純函式。成本站 render、approve 讀回、測試共用。"""
import math
import re

from .sources import PENDING

PARAM_ROW = "參數變動"
OTHER_ROW = "其他（未對應 CH）"
SCRAP_ROWS = {"一般光纖陣列（≤ 16 通道）": lambda ch, pm, coat: ch <= 16 and not pm,
              "32–48 通道陣列": lambda ch, pm, coat: 32 <= ch <= 48,
              "PM 陣列": lambda ch, pm, coat: pm,
              "PM 陣列，端面在空氣中或有鍍膜": lambda ch, pm, coat: pm}  # 程式內文字：工廠報廢率規則表的列名，要跟原始資料一致


def _percent(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return round(float(m.group(1)) / 100, 6) if m else None


def scrap_rate(product_type, channels, adds, sources):
    """表 J。回傳 {"value": 比率或待填, "source": 出處或 None, "candidates": [出處…]}。
    端面在不在空氣中程式看不出，所以有 PM 就兩個 PM 列都算符合。"""
    if product_type == "Fanout":
        key = "RULES §3 報廢率 扇出線"
        return {"value": _percent(sources[key]), "source": key, "candidates": [key]}
    pm, coat = "PM" in adds, "coating" in adds
    hits = [] if channels is None else [f"RULES §3 報廢率 {name}" for name, ok in SCRAP_ROWS.items() if ok(channels, pm, coat)]
    if len(hits) == 1:
        return {"value": _percent(sources[hits[0]]), "source": hits[0], "candidates": hits}
    return {"value": PENDING, "source": None,
            "candidates": hits or [f"RULES §3 報廢率 {name}" for name in SCRAP_ROWS]}


def rate_of(sources, key):
    return _percent(sources[key])


def _pick(price, qty, costing_qty):
    chosen, name = price["base"], "Base"
    for i, (brk_qty, brk_price) in enumerate(price.get("breaks", []), 1):
        if brk_qty is not None and brk_price is not None and qty * costing_qty >= brk_qty:
            chosen, name = brk_price, f"Break {i}"
    return chosen, name


def unit_price(price, qty, costing_qty):
    """P13：購買數量（用量 × 計價數量）落在哪一段就用哪一段。"""
    return _pick(price, qty, costing_qty)[0]


def break_name(price, qty, costing_qty):
    return _pick(price, qty, costing_qty)[1]


def service_per_pc(service, lot_size):
    """P73：每批收費 ÷ 成本批量；按顆計價的 max(單價 × 批量, 最低收費) ÷ 批量。"""
    if not lot_size:
        return None
    if service["per"] == "lot":
        return service["price"] / lot_size
    return max(service["price"] * lot_size, service.get("min_charge") or 0) / lot_size


def conversion_cost(setup, lot_size, run, rate):
    """P74：（整備 ÷ 成本批量 + 單件）÷ 60 × 費率。有一個待填就回傳 None。"""
    if setup is None or run is None or not lot_size or rate is None:
        return None
    return (setup / lot_size + run) / 60 * rate


def quote(total, margin, step):
    """報價 = 總成本 ÷（1 − 目標毛利），無條件進位到 step。"""
    raw = total / (1 - margin)
    return round(math.ceil(round(raw / step, 9)) * step, 6)


def _line_cost(line, costing_qty):
    if line.get("qty") is None or not line.get("price"):
        return None, None
    unit = unit_price(line["price"], line["qty"], costing_qty)
    return unit, line["qty"] * unit


def model(inputs):
    """表 I。inputs：{"lines", "services", "conversion", "params"（, "quote_kept"）}。"""
    p = inputs["params"]
    lines, pending = [], 0
    for line in inputs["lines"]:
        unit, cost = _line_cost(line, p["costing_qty"])
        pending += cost is None
        lines.append({**{k: line.get(k) for k in ("item", "part_no", "description", "category", "qty", "uom")},
                      "unit_price": unit, "line_cost": cost})
    material = sum(l["line_cost"] or 0 for l in lines)
    packaging = sum(l["line_cost"] or 0 for l in lines if l["category"] == "PKG")
    services = [service_per_pc(s, p["lot_size"]) for s in inputs["services"]]
    convs = [conversion_cost(c["setup"], p["lot_size"], c["run"], c["rate"]) for c in inputs["conversion"]]
    pending += sum(v is None for v in services + convs) + (p.get("scrap_rate") is None) + (not p.get("lot_size"))
    s, c = sum(v or 0 for v in services), sum(v or 0 for v in convs)
    h = (material + s) * p["handling"]
    o = c * p["overhead"]
    x = (material - packaging + s + c + (material - packaging + s) * p["handling"] + o) * (p.get("scrap_rate") or 0)   # 表 I 第 6 列
    mc = material + s + c + h + o + x
    g = mc * p["sga"]
    complete = pending == 0
    total = mc + g if complete else None
    kept = inputs.get("quote_kept")
    q = kept if "quote_kept" in inputs else (quote(total, p["margin"], p["rounding"]) if complete else None)
    margin = (q - total) / q if q is not None and total is not None else None
    return {"Material": material, "Packaging": packaging, "Services": s, "Conversion": c, "Material handling": h,
            "Manufacturing overhead": o, "Scrap": x, "Manufacturing cost": mc, "SG&A": g,
            "total": total, "quote": q, "margin": margin, "complete": complete, "pending": pending,
            "lines": lines, "service_per_pc": services, "conversion_per_pc": convs}


def _linear(d_m, d_pkg, d_s, d_c, p):
    """參數固定時，材料、包材、服務、加工的直接差額 → 總成本差額（表 I 第 4～9 列）。"""
    h = (d_m + d_s) * p["handling"]
    o = d_c * p["overhead"]
    x = (d_m - d_pkg + d_s + d_c + (d_m - d_pkg + d_s) * p["handling"] + o) * p["scrap_rate"]
    return (d_m + d_s + d_c + h + o + x) * (1 + p["sga"])


def delta(old, new, ch_of):
    """P81：先算參數變動（上一版的料、服務、工序套這一版的參數），再把每列的差額歸到 CH。
    ch_of：{料號、服務碼或「Op n」: CH}。兩版都完整才算，回傳 [(列名, USD)]；不完整回傳 []。"""
    m_old, m_new = model(old), model(new)
    if not (m_old["complete"] and m_new["complete"]):
        return []
    p = new["params"]
    mixed = {**old, "params": p}
    m_mix = model(mixed)
    rows = {PARAM_ROW: m_mix["total"] - m_old["total"]}
    parts = {}

    def add(key, d_m=0, d_pkg=0, d_s=0, d_c=0):
        label = ch_of.get(key, OTHER_ROW)
        acc = parts.setdefault(label, [0, 0, 0, 0])
        for i, v in enumerate((d_m, d_pkg, d_s, d_c)):
            acc[i] += v

    def by(items, key):
        return {key(i): i for i in items}
    old_l = by(m_mix["lines"], lambda l: l["part_no"])
    new_l = by(m_new["lines"], lambda l: l["part_no"])
    for pn in list(old_l) + [k for k in new_l if k not in old_l]:
        a, b = old_l.get(pn), new_l.get(pn)
        ca, cb = (a or {}).get("line_cost") or 0, (b or {}).get("line_cost") or 0
        pa = ca if a and a["category"] == "PKG" else 0
        pb = cb if b and b["category"] == "PKG" else 0
        if abs(cb - ca) > 1e-12 or abs(pb - pa) > 1e-12:
            add(pn, d_m=cb - ca, d_pkg=pb - pa)
    old_s = {s["code"]: v for s, v in zip(old["services"], m_mix["service_per_pc"])}
    new_s = {s["code"]: v for s, v in zip(new["services"], m_new["service_per_pc"])}
    for code in list(old_s) + [k for k in new_s if k not in old_s]:
        d = (new_s.get(code) or 0) - (old_s.get(code) or 0)
        if abs(d) > 1e-12:
            add(code, d_s=d)
    old_c = {f"Op {c['op']}": v for c, v in zip(old["conversion"], m_mix["conversion_per_pc"])}
    new_c = {f"Op {c['op']}": v for c, v in zip(new["conversion"], m_new["conversion_per_pc"])}
    for op in list(old_c) + [k for k in new_c if k not in old_c]:
        d = (new_c.get(op) or 0) - (old_c.get(op) or 0)
        if abs(d) > 1e-12:
            add(op, d_c=d)
    for label in sorted(parts, key=lambda k: (k == OTHER_ROW, int(re.sub(r"\D", "", k) or 0), k)):
        rows[label] = _linear(*parts[label], p)
    return list(rows.items())

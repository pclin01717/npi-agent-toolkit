"""approve 時把我方文件（工程師可能改過）讀回成結構化資料。入口檢查在這裡。"""
from pathlib import Path

import docx
import openpyxl

from ..errors import NpiError
from ..params import TYPES
from ..render.docx_out import HEADER
from ..sources import PENDING

BOM_HEADS = {"Level": "level", "Item No.": "item", "Part No.": "part_no", "Description": "description",
             "Type": "category", "Make/Buy": "make_buy", "Qty per Parent": "qty_per", "UoM": "uom",
             "Supplier": "supplier", "Lead Time (days)": "lead_time_days", "Remark": "remark"}
ROUTING_HEADS = {"Op.": "op", "Operation Description": "description", "Work Centre": "work_centre",
                 "Setup (min / lot)": "setup_min", "Run (min / pc)": "run_min", "Kinds": "kinds"}


def _find_header_row(ws, first_head, path):
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == first_head:
                return cell.row
    raise NpiError(f"{path.name}：找不到表頭「{first_head}」")


def _columns(ws, head_row, heads, path):
    cols = {heads[c.value]: c.column for c in ws[head_row] if c.value in heads}
    missing = [h for h, k in heads.items() if k not in cols]
    if missing:
        raise NpiError(f"{path.name}「{ws.title}」：表頭缺少「{'、'.join(missing)}」")
    return cols


def read_bom(path):
    """BOM 工作表 → 每列；展開用量不讀公式（openpyxl 讀不到結果），照階重算（PLANS P61）。"""
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["BOM"] if "BOM" in wb.sheetnames else wb.active
    head_row = _find_header_row(ws, "Part No.", path)
    cols = _columns(ws, head_row, BOM_HEADS, path)
    rows = []
    for r in range(head_row + 1, ws.max_row + 1):
        values = {k: ws.cell(r, c).value for k, c in cols.items()}
        if not values["part_no"]:
            continue
        qty = values["qty_per"]
        if qty == PENDING:
            values["qty_per"] = None
        elif not isinstance(qty, (int, float)):
            raise NpiError(f"{path.name} 第 {r} 列（{values['part_no']}）：「Qty per Parent」不是數字：{qty!r}")
        values["item"] = None if values["item"] is None else str(values["item"])
        rows.append(values)
    by_item = {b["item"]: b for b in rows}
    for b in rows:
        parts = (b["item"] or "").split(".")
        parent = None if parts == ["0"] else by_item.get("0" if len(parts) == 1 else parts[0])
        qty = b["qty_per"]
        b["ext_qty"] = qty if parent is None or qty is None else (
            None if parent.get("ext_qty") is None else round(qty * parent["ext_qty"], 6))
    return rows


def read_routing(path):
    """BOM 的 Routing 工作表 → 每道工序；時間待填讀成 None。"""
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Routing"]
    head_row = _find_header_row(ws, "Op.", path)
    cols = _columns(ws, head_row, ROUTING_HEADS, path)
    out = []
    for r in range(head_row + 1, ws.max_row + 1):
        o = {k: ws.cell(r, c).value for k, c in cols.items()}
        if o["op"] is None:
            continue
        where = f"{path.name}「Routing」第 {r} 列（Op {o['op']}）"
        o["op"] = str(o["op"])
        for key in ("setup_min", "run_min"):
            o[key] = _number_or_pending(o[key], f"{where}「{key}」")
        o["kinds"] = [k.strip() for k in (o["kinds"] or "").split(",") if k.strip()]
        out.append(o)
    return out


def read_spec_doc(path):
    """正式 spec docx → 基本資料、關鍵參數（數字）、各節內文。"""
    path = Path(path)
    d = docx.Document(path)
    if len(d.tables) < 2:
        raise NpiError(f"{path.name}：找不到基本資料表和關鍵參數表")
    out = {}
    for row in d.tables[0].rows:
        key = HEADER.get(row.cells[0].text.strip())
        if key:
            out[key] = row.cells[1].text.strip()
    rows = d.tables[1].rows[1:]
    first = rows[0].cells[0].text.strip() if rows else ""
    spec = next((s for s in TYPES.values() if first in dict(s["rows"])), None)
    if spec is None:
        raise NpiError(f"{path.name}：關鍵參數表第一列「{first}」認不出是哪種產品（{'、'.join(TYPES)}）")
    labels = dict(spec["rows"])
    params = {}
    for row in rows:
        label, text = row.cells[0].text.strip(), row.cells[1].text.strip()
        if label not in labels:
            raise NpiError(f"{path.name}：關鍵參數表有不認得的列「{label}」")
        try:
            params.update(spec["parse_row"](labels[label], text))
        except ValueError as e:
            raise NpiError(f"{path.name}：關鍵參數「{label}」{e}") from e
    missing = [label for label, _ in spec["rows"] if not all(k in params for k in labels[label])]
    if missing:
        raise NpiError(f"{path.name}：關鍵參數表缺少「{'、'.join(missing)}」")
    sections, current, started = [], None, False
    for p in d.paragraphs:
        if p.style.name == "Heading 1":
            started = p.text.strip() == "Specification"
            continue
        if not started:
            continue
        if p.style.name == "Heading 2":
            current = {"title": p.text.strip(), "text": ""}
            sections.append(current)
        elif current is not None and p.text.strip():
            current["text"] = (current["text"] + "\n" + p.text.strip()).strip()
    out["params"] = params
    out["sections"] = sections
    return out


PARAM_KEYS = {"Costing order qty": "costing_qty", "Cost lot size": "lot_size", "Scrap rate": "scrap_rate",
              "Material handling rate": "handling", "Manufacturing overhead rate": "overhead", "SG&A rate": "sga",
              "Target margin": "margin", "Quote rounding (USD)": "rounding", "Target / comparison price": "target",
              "Quote kept from previous revision": "quote_kept"}
ELEMENTS = ["Material", "Packaging", "Services", "Conversion", "Material handling", "Manufacturing overhead", "Scrap",
            "Manufacturing cost", "SG&A"]


def _number_or_pending(value, where):
    if value is None or value == PENDING:
        return None
    if isinstance(value, (int, float)):
        return value
    raise NpiError(f"{where}：要是數字或「{PENDING}」，現在是 {value!r}")


def _sheet_table(ws, path, first_head):
    """表頭列之後到第一個空列為止的每一列（{表頭: 值}）。"""
    head_row = _find_header_row(ws, first_head, path)
    heads = [c.value for c in ws[head_row]]
    rows = []
    for r in range(head_row + 1, ws.max_row + 1):
        values = [ws.cell(r, c + 1).value for c in range(len(heads))]
        if all(v is None for v in values):
            break
        rows.append((r, {h: v for h, v in zip(heads, values) if h}))
    return rows


def read_cost(path):
    """PLANS P78：單位成本 xlsx 有公式，openpyxl 讀不到計算結果，所以只讀輸入格，用 costing.model 重算。"""
    from .. import costing
    path = Path(path)
    wb = openpyxl.load_workbook(path)
    params = {}
    for _r, row in _sheet_table(wb["Parameters"], path, "Parameter"):
        key = PARAM_KEYS.get(row["Parameter"])
        if key:
            params[key] = _number_or_pending(row["Value"], f"{path.name}「Parameters」{row['Parameter']}")
    lines = []
    for r, row in _sheet_table(wb["Material"], path, "Material Code"):
        where = f"{path.name}「Material」第 {r} 列（{row['Material Code']}）"
        base = _number_or_pending(row["Base Price (USD)"], where + "「Base Price」")
        breaks = [(_number_or_pending(row[f"Break {i} Qty ≥"], where), _number_or_pending(row[f"Break {i} Price (USD)"], where))
                  for i in (1, 2)]
        lines.append({"item": str(row["BOM Item"]), "part_no": row["Material Code"], "description": row["Description"],
                      "category": row["Category"], "uom": row["UoM"],
                      "qty": _number_or_pending(row["Ext. Qty / pc"], where + "「Ext. Qty / pc」"),
                      "price": {"base": base, "breaks": breaks} if base is not None else None,
                      "price_doc": row["Price Basis"] or ""})
    services = []
    for r, row in _sheet_table(wb["Services"], path, "Service Code"):
        where = f"{path.name}「Services」第 {r} 列（{row['Service Code']}）"
        services.append({"code": row["Service Code"], "per": str(row["Charge Basis"]).replace("per ", ""),
                         "price": _number_or_pending(row["Unit Price (USD)"], where),
                         "min_charge": _number_or_pending(row["Min. Charge (USD / order)"], where)})
    rates = {row["Work Centre"]: row["Rate (USD / hr)"] for _, row in _sheet_table(wb["Rates"], path, "Work Centre")}
    conversion = []
    for r, row in _sheet_table(wb["Conversion"], path, "Op."):
        where = f"{path.name}「Conversion」第 {r} 列（Op {row['Op.']}）"
        conversion.append({"op": str(row["Op."]), "work_centre": row["Work Centre"],
                           "setup": _number_or_pending(row["Setup (min / lot)"], where + "「Setup」"),
                           "run": _number_or_pending(row["Run (min / pc)"], where + "「Run」"),
                           "rate": rates.get(row["Work Centre"])})
    inputs = {"lines": lines, "services": services, "conversion": conversion,
              "params": {k: v for k, v in params.items() if k not in ("target", "quote_kept")}}
    if "quote_kept" in params:
        inputs["quote_kept"] = params["quote_kept"]
    m = costing.model(inputs)
    for s, per_pc in zip(services, m["service_per_pc"]):
        s["per_pc"] = per_pc
    out_lines = []
    for line, src in zip(m["lines"], lines):
        priced = line["unit_price"] is not None
        name = costing.break_name(src["price"], src["qty"], params["costing_qty"]) if priced else ""
        out_lines.append({**line, "price_source": f"{src['price_doc']} {name}".strip() if priced else src["price_doc"],
                          "price_text": None if priced else PENDING})
    return {"inputs": inputs, "params": params, "elements": {k: m[k] for k in ELEMENTS},
            "lines": out_lines, "material_total": round(m["Material"], 4), "complete": m["complete"],
            "total": m["total"], "quote": m["quote"], "margin": m["margin"], "target": params.get("target"),
            "total_note": "" if m["complete"] else f"不完整：{m['pending']} 個輸入待工程師填寫"}  # 程式內文字：成本完整度狀態，跟計算一起產生

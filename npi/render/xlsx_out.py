"""把資料填進 templates/ 的 xlsx 範本。版面在範本裡，這裡只填值。"""
from copy import copy

import openpyxl
from openpyxl.utils import get_column_letter

from . import TEMPLATES

BOM_COLUMNS = ["level", "item", "part_no", "description", "category", "make_buy", "qty_per", "uom",
               "ext_qty", "supplier", "lead_time_days", "remark"]
BOM_HEADER = {"Doc. No.": "doc_no", "Revision": "rev", "Product": "product",
              "NPI No.": "npi_no", "Date": "date"}
TABLE_ROW = 8
BOM_FIRST_ROW = TABLE_ROW + 1
CHANNEL_EXPECTED, CHANNEL_CHECK = "E2", "E3"
FANOUT_MAP_HEADS = ["Fibre", "MPO", "MPO Position", "Leg"]


def _fill_header(ws, header, labels):
    for row in ws.iter_rows(min_col=1, max_col=1):
        cell = row[0]
        if cell.value in labels:
            ws.cell(cell.row, 2, header.get(labels[cell.value]))


def _fill_rows(ws, rows, first=BOM_FIRST_ROW):
    for r, values in enumerate(rows, start=first):
        for c, value in enumerate(values, start=1):
            ws.cell(r, c, value)


def _parent_of(item):
    parts = str(item).split(".")
    return None if parts == ["0"] else "0" if len(parts) == 1 else parts[0]


def write_bom(path, header, rows, sheets=None):
    """rows：BOM 列（含 level、category）；展開用量寫公式（PLANS P61）。
    sheets：{"channel_map": {"heads", "rows", "expected"}, "routing": [列], "revisions": [列], "changes": [列] 或 None}。"""
    wb = openpyxl.load_workbook(TEMPLATES / "bom.xlsx")
    sheets = sheets or {}
    if sheets.get("changes") is None:
        del wb["Change Summary"]
    for ws in wb.worksheets:
        _fill_header(ws, header, BOM_HEADER)
    ws = wb["BOM"]
    col = {k: i for i, k in enumerate(BOM_COLUMNS, start=1)}
    row_of = {str(row["item"]): r for r, row in enumerate(rows, start=BOM_FIRST_ROW)}
    q, e = get_column_letter(col["qty_per"]), get_column_letter(col["ext_qty"])
    for r, row in enumerate(rows, start=BOM_FIRST_ROW):
        for key, c in col.items():
            if key != "ext_qty":
                ws.cell(r, c, row.get(key))
        parent = row_of.get(_parent_of(row["item"]))
        times = f"*{e}{parent}" if parent else ""
        ws.cell(r, col["ext_qty"], f'=IF(ISNUMBER({q}{r}),{q}{r}{times},"")')
    cm = wb["Channel Map"]
    channel = sheets.get("channel_map")
    if channel:
        if channel.get("heads"):
            for c in range(1, cm.max_column + 1):
                cm.cell(TABLE_ROW, c, channel["heads"][c - 1] if c <= len(channel["heads"]) else None)
        _fill_rows(cm, channel["rows"])
        cm[CHANNEL_EXPECTED] = channel["expected"]
        last = BOM_FIRST_ROW + max(len(channel["rows"]), channel["expected"]) + 50
        cm[CHANNEL_CHECK] = f'=IF(COUNTIF(A{BOM_FIRST_ROW}:A{last},"<>")={CHANNEL_EXPECTED},"OK","CHECK")'
    _fill_rows(wb["Routing"], sheets.get("routing", []))
    _fill_rows(wb["Revision"], sheets.get("revisions", []))
    if sheets.get("changes") is not None:
        _fill_rows(wb["Change Summary"], sheets["changes"])
    wb.active = wb.sheetnames.index("BOM")
    wb.save(path)
    return path


INCOMPLETE = "不完整"
PENDING_TEXT = "待工程師填寫"
SUMMARY_TABLE_ROW, NRE_TABLE_ROW = 9, 27
SUMMARY_ELEMENTS = ["Material", "Services", "Conversion", "Material handling", "Manufacturing overhead", "Scrap",
                    "Manufacturing cost", "SG&A", "Total cost", "Quote price", "Gross margin"]
_ROW = {name: SUMMARY_TABLE_ROW + 1 + i for i, name in enumerate(SUMMARY_ELEMENTS)}
PENDING_ROW, TARGET_ROW, VS_TARGET_ROW = _ROW["Gross margin"] + 1, _ROW["Gross margin"] + 3, _ROW["Gross margin"] + 4
SUMMARY_REF = {"total": f"Summary!E{_ROW['Total cost']}", "quote": f"Summary!E{_ROW['Quote price']}",
               "target": f"Summary!E{TARGET_ROW}", "vs_target": f"Summary!E{VS_TARGET_ROW}"}
DELTA_FIRST = TABLE_ROW + 1
DELTA_CHECK_REF = "Delta vs {prev}!E2"
DELTA_MARGIN_REF = "Delta vs {prev}!{col}" + str(DELTA_FIRST + SUMMARY_ELEMENTS.index("Gross margin"))
COST_HEADER = {"Doc. No.": "doc_no", "Revision": "rev", "Product": "product", "NPI No.": "npi_no",
               "Date": "date", "Basis": "basis"}
CATEGORY_ORDER = ["RM", "BUY", "PKG", "CON", "MFG"]



def material_subtotal_ref(path, category):
    ws = openpyxl.load_workbook(path)["Material"]
    for row in ws.iter_rows(min_col=1, max_col=2):
        if row[0].value == "Subtotal" and row[1].value == category:
            return f"Material!O{row[0].row}"
    raise KeyError(category)


def write_cost(path, header, book):
    """book：cost.render 整理好的輸入（params、lines、services、conversion、rates、nre、approval、delta、minor_quote）。
    輸入格待填就留空、Status 寫待工程師填寫；其他格都是公式（PLANS P69、P70）。"""
    wb = openpyxl.load_workbook(TEMPLATES / "unit_cost.xlsx")
    for ws in wb.worksheets:
        _fill_header(ws, header, COST_HEADER)
    first = TABLE_ROW + 1
    # Parameters
    pws, ref = wb["Parameters"], {}
    for r, (name, value, unit, basis, status) in enumerate(book["params"], start=first):
        _fill_rows(pws, [[name, value, unit, basis, status]], r)
        ref[name] = f"Parameters!$B${r}"
    # Material
    mws, lines = wb["Material"], book["lines"]
    for r, l in enumerate(lines, start=first):
        _fill_rows(mws, [[l["item"], l["part_no"], l["description"], l["category"], l["qty"], l["uom"],
                          f"={ref['Costing order qty']}", l["base"], l["b1q"], l["b1p"], l["b2q"], l["b2p"],
                          f'=IF(OR(ISBLANK(E{r}),ISBLANK(H{r})),"",IF(AND(ISNUMBER(K{r}),ISNUMBER(L{r}),E{r}*G{r}>=K{r}),'
                          f'L{r},IF(AND(ISNUMBER(I{r}),ISNUMBER(J{r}),E{r}*G{r}>=I{r}),J{r},H{r})))',
                          l["basis"], f'=IF(M{r}="","",E{r}*M{r})', l["status"]]], r)
    last = first + len(lines) - 1
    sub = {}
    r = last + 2
    for cat in CATEGORY_ORDER:
        _fill_rows(mws, [["Subtotal", cat]], r)
        mws.cell(r, 15, f'=SUMIF(D{first}:D{max(last, first)},"{cat}",O{first}:O{max(last, first)})')
        sub[cat] = f"Material!O{r}"
        r += 1
    mws.cell(r, 1, "Total material")
    mws.cell(r, 15, f"=SUM(O{first}:O{max(last, first)})")
    material_total = f"Material!O{r}"
    # Services
    sws, svcs = wb["Services"], book["services"]
    for r, s in enumerate(svcs, start=first):
        per = f"E{r}/G{r}" if s["per"] == "lot" else f"MAX(E{r}*G{r},F{r})/G{r}"
        _fill_rows(sws, [[s["code"], s["supplier"], s["description"], f"per {s['per']}", s["price"], s["min_charge"],
                          f"={ref['Cost lot size']}", f'=IF(ISNUMBER(G{r}),{per},"")', s["basis"], s["status"]]], r)
    r = first + len(svcs) + 1
    sws.cell(r, 1, "Total services")
    sws.cell(r, 8, f"=SUM(H{first}:H{r - 2})" if svcs else 0)
    services_total = f"Services!H{r}"
    # Rates
    rws, rate_ref = wb["Rates"], {}
    for r, (wc, rate, basis) in enumerate(book["rates"], start=first):
        _fill_rows(rws, [[wc, rate, basis]], r)
        rate_ref[wc] = f"Rates!B{r}"
    # Conversion
    cws, convs = wb["Conversion"], book["conversion"]
    for r, c in enumerate(convs, start=first):
        _fill_rows(cws, [[c["op"], c["description"], c["work_centre"], c["setup"], f"={ref['Cost lot size']}", c["run"],
                          f'=IF(OR(ISBLANK(D{r}),NOT(ISNUMBER(E{r})),ISBLANK(F{r})),"",D{r}/E{r}+F{r})',
                          f"={rate_ref[c['work_centre']]}", f'=IF(G{r}="","",G{r}/60*H{r})', c["status"]]], r)
    r = first + len(convs) + 1
    cws.cell(r, 1, "Total conversion")
    cws.cell(r, 9, f"=SUM(I{first}:I{r - 2})" if convs else 0)
    conversion_total = f"Conversion!I{r}"
    # Summary
    ws, E = wb["Summary"], {k: f"E{v}" for k, v in _ROW.items()}
    rate = {k: ref[k] for k in ("Material handling rate", "Manufacturing overhead rate", "SG&A rate", "Scrap rate")}
    rows = {
        "Material": ("Material sheet", None, f"={material_total}"),
        "Services": ("Services sheet", None, f"={services_total}"),
        "Conversion": ("Conversion sheet", None, f"={conversion_total}"),
        "Material handling": ("(Material + Services) x rate", rate["Material handling rate"],
                              f"=({E['Material']}+{E['Services']})*D{_ROW['Material handling']}"),
        "Manufacturing overhead": ("Conversion x rate", rate["Manufacturing overhead rate"],
                                   f"={E['Conversion']}*D{_ROW['Manufacturing overhead']}"),
        "Scrap": ("(Above, packaging and its handling excluded) x rate", rate["Scrap rate"],
                  f'=IF(ISNUMBER(D{_ROW["Scrap"]}),({E["Material"]}-{sub["PKG"]}+{E["Services"]}+{E["Conversion"]}'
                  f'+({E["Material"]}-{sub["PKG"]}+{E["Services"]})*D{_ROW["Material handling"]}'
                  f'+{E["Manufacturing overhead"]})*D{_ROW["Scrap"]},"")'),
        "Manufacturing cost": ("Sum of the above", None, f"=SUM({E['Material']}:{E['Scrap']})"),
        "SG&A": ("Manufacturing cost x rate", rate["SG&A rate"], f"={E['Manufacturing cost']}*D{_ROW['SG&A']}"),
        "Total cost": ("Manufacturing cost + SG&A", None,
                       f'=IF(E{PENDING_ROW}>0,"{INCOMPLETE}",{E["Manufacturing cost"]}+{E["SG&A"]})'),
        "Quote price": (book["quote_basis"], None,
                        f'=IF(ISNUMBER({ref["Quote kept from previous revision"]}),{ref["Quote kept from previous revision"]},"{INCOMPLETE}")'
                        if book["minor_quote"] else
                        f'=IF(ISNUMBER({E["Total cost"]}),CEILING({E["Total cost"]}/(1-{ref["Target margin"]}),'
                        f'{ref["Quote rounding (USD)"]}),"{INCOMPLETE}")'),
        "Gross margin": ("(Quote - Total cost) / Quote", None,
                         f'=IF(AND(ISNUMBER({E["Total cost"]}),ISNUMBER({E["Quote price"]})),'
                         f'({E["Quote price"]}-{E["Total cost"]})/{E["Quote price"]},"{INCOMPLETE}")'),
    }
    for n, name in enumerate(SUMMARY_ELEMENTS, 1):
        basis, rate_cell, formula = rows[name]
        rate_formula = f'=IF(ISBLANK({rate_cell}),"",{rate_cell})' if rate_cell else None
        _fill_rows(ws, [[n, name, basis, rate_formula, formula]], _ROW[name])
    blanks = [f'COUNTIF({ref[name].replace("$", "")},"")' for name, *_ in book["params"]
              if name != "Target / comparison price"]                 # 目標價不進總成本
    for sheet, cols, n in (("Material", "EH", len(lines)), ("Services", "E", len(svcs)), ("Conversion", "DF", len(convs))):
        if n:
            blanks += [f'COUNTIF({sheet}!{c}{first}:{c}{first + n - 1},"")' for c in cols]
    counts = "+".join(blanks)                                         # P70：數空的輸入格（issue #33）
    _fill_rows(ws, [[None, "Pending inputs", "Count of blank input cells", None, f"={counts}"]], PENDING_ROW)
    target = ref["Target / comparison price"]
    _fill_rows(ws, [[None, "Target / comparison price", book["target_basis"], None,
                     f'=IF(ISNUMBER({target}),{target},"{INCOMPLETE}")']], TARGET_ROW)
    _fill_rows(ws, [[None, "Quote - target", None, None,
                     f'=IF(AND(ISNUMBER({E["Quote price"]}),ISNUMBER(E{TARGET_ROW})),{E["Quote price"]}-E{TARGET_ROW},"{INCOMPLETE}")']],
               VS_TARGET_ROW)
    nre_first = NRE_TABLE_ROW + 1
    _fill_rows(ws, [list(n) for n in book["nre"]], nre_first)
    r = nre_first + len(book["nre"]) + 1
    ws.cell(r, 2, "NRE total")
    ws.cell(r, 3, f"=SUM(C{nre_first}:C{r - 2})" if book["nre"] else 0)
    # Delta
    d = book.get("delta")
    if d is None:
        del wb["Delta"]
    else:
        dws = wb["Delta"]
        dws.title = f"Delta vs {d['prev']}"
        dws.cell(TABLE_ROW, 2, f"Rev. {d['prev']} (USD)")
        dws.cell(TABLE_ROW, 3, f"Rev. {header['rev']} (USD)")
        for i, name in enumerate(SUMMARY_ELEMENTS):
            r = DELTA_FIRST + i
            prev = d["prev_values"].get(name)
            _fill_rows(dws, [[name, prev if prev is not None else INCOMPLETE, f"=Summary!E{_ROW[name]}",
                              f'=IF(AND(ISNUMBER(B{r}),ISNUMBER(C{r})),C{r}-B{r},"{INCOMPLETE}")']], r)
        total_delta = f"D{DELTA_FIRST + SUMMARY_ELEMENTS.index('Total cost')}"
        r = DELTA_FIRST + len(SUMMARY_ELEMENTS) + 1
        _fill_rows(dws, [["Driver", "Delta (USD)", "Basis"]], r)
        for c in range(1, 4):
            dws.cell(r, c).font = copy(dws.cell(TABLE_ROW, 1).font)
        drivers_first = r + 1
        _fill_rows(dws, [[label, value, basis] for label, value, basis in d["drivers"]], drivers_first)
        drivers_last = drivers_first + max(len(d["drivers"]), 1) - 1
        dws["E3"] = f"=SUM(B{drivers_first}:B{drivers_last})"
        dws["E2"] = (f'=IF(ISNUMBER({total_delta}),IF(ABS(E3-{total_delta})<0.005,"OK","CHECK"),"{INCOMPLETE}")')
    # Approval
    _fill_rows(wb["Approval"], [list(a) for a in book["approval"]])
    wb.save(path)
    return path

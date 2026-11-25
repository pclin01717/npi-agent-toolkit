"""工程發行的關鍵參數：只存一份，spec、BOM、圖面、STEP 都從這裡來。依產品類型分組（PLANS P36、P37）。純函式。"""
import re

from .sources import PENDING

NUMERIC = ["channels", "pitch_um", "end_face_angle_deg", "pigtail_mm", "pigtail_tol_mm",
           "substrate_w_mm", "substrate_l_mm", "substrate_t_mm",
           "lid_w_mm", "lid_l_mm", "lid_t_mm", "boot_w_mm", "boot_h_mm", "boot_l_mm"]
TEXT = ["connector"]
REQUIRED = NUMERIC + TEXT

# 正式 spec「Key Parameters」表的列：(欄名, 參數鍵)
ROWS = [
    ("Channels", ["channels"]),
    ("Fibre pitch (µm)", ["pitch_um"]),
    ("End-face angle (°)", ["end_face_angle_deg"]),
    ("Pigtail length (mm)", ["pigtail_mm", "pigtail_tol_mm"]),
    ("Connectors", ["connector"]),
    ("Substrate W x L x T (mm)", ["substrate_w_mm", "substrate_l_mm", "substrate_t_mm"]),
    ("Lid W x L x T (mm)", ["lid_w_mm", "lid_l_mm", "lid_t_mm"]),
    ("Boot W x H x L (mm)", ["boot_w_mm", "boot_h_mm", "boot_l_mm"]),
]
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def fmt(v):
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def num(text):
    f = float(text)
    return int(f) if f.is_integer() else f


def values(params):
    """判讀檔的 {鍵: {"value": v, "sources": [...]}} → {鍵: v}。"""
    return {k: (p["value"] if isinstance(p, dict) else p) for k, p in params.items()}


def row_text(keys, v):
    if keys == ["pigtail_mm", "pigtail_tol_mm"]:
        return f"{fmt(v['pigtail_mm'])} ± {fmt(v['pigtail_tol_mm'])}"
    return " x ".join(fmt(v[k]) for k in keys)


def parse_row(keys, text):
    if keys == ["connector"]:
        return {"connector": text.strip()}
    nums = [num(n) for n in _NUM.findall(text)]
    if len(nums) != len(keys):
        raise ValueError(f"要 {len(keys)} 個數字，讀到 {len(nums)} 個：{text!r}")
    return dict(zip(keys, nums))


def description(v):
    return (f"Fibre array unit {fmt(v['channels'])} ch, {fmt(v['pitch_um'])} µm pitch, "
            f"{fmt(v['end_face_angle_deg'])}° end face, {v['connector']}, "
            f"pigtail {fmt(v['pigtail_mm'])} ± {fmt(v['pigtail_tol_mm'])} mm")


# ---- fan-out（第 2 批）----
FO_TEXT = ["trunk_connector", "leg_connector", "end_face", "polarity"]
FO_NUMERIC = ["fibres", "trunk_conn_qty", "leg_conn_qty", "trunk_m", "trunk_tol_plus_mm", "trunk_tol_minus_mm",
              "leg_mm", "leg_tol_plus_mm", "leg_tol_minus_mm", "trunk_od_mm", "leg_od_mm",
              "box_l_mm", "box_w_mm", "box_h_mm"]
FO_ROWS = [
    ("Fibre count", ["fibres"]),
    ("Trunk connectors", ["trunk_conn_qty", "trunk_connector"]),
    ("Leg connectors", ["leg_conn_qty", "leg_connector"]),
    ("End face", ["end_face"]),
    ("Polarity", ["polarity"]),
    ("Trunk length", ["trunk_m", "trunk_tol_plus_mm", "trunk_tol_minus_mm"]),
    ("Leg length (mm)", ["leg_mm", "leg_tol_plus_mm", "leg_tol_minus_mm"]),
    ("Trunk / leg cable OD (mm)", ["trunk_od_mm", "leg_od_mm"]),
    ("Fan-out box L x W x H (mm)", ["box_l_mm", "box_w_mm", "box_h_mm"]),
]
POLARITIES = ["Method A", "Method B"]
_QTY_X = re.compile(r"^\s*(\d+)\s*x\s*(.+?)\s*$")
_LEN_TOL = re.compile(r"^\s*(\d+(?:\.\d+)?)(?:\s*m)?\s*(?:±\s*(\d+(?:\.\d+)?)|\+\s*(\d+(?:\.\d+)?)\s*/\s*-?\s*(\d+(?:\.\d+)?))"
                      r"(?:\s*mm)?\s*$")


def tol_text(plus, minus):
    """公差寫法（PLANS P38）：相同寫「± 10」，不同寫「+50 / 0」或「+50 / -10」。"""
    if plus == minus:
        return f"± {fmt(plus)}"
    return f"+{fmt(plus)} / {fmt(minus) if minus == 0 else '-' + fmt(minus)}"


def metres(v):
    s = fmt(v)
    return s if "." in s else s + ".0"


def fo_row_text(keys, v):
    if len(keys) == 1:
        return fmt(v[keys[0]])
    if keys[1] in FO_TEXT:
        return f"{fmt(v[keys[0]])} x {v[keys[1]]}"
    if keys[0] == "trunk_m":
        return f"{metres(v['trunk_m'])} m {tol_text(v[keys[1]], v[keys[2]])} mm"
    if keys[0] == "leg_mm":
        return f"{fmt(v['leg_mm'])} {tol_text(v[keys[1]], v[keys[2]])}"
    if keys[0] == "trunk_od_mm":
        return " / ".join(fmt(v[k]) for k in keys)
    return " x ".join(fmt(v[k]) for k in keys)


def fo_parse_row(keys, text):
    if len(keys) == 1 and keys[0] in FO_TEXT:
        return {keys[0]: text.strip()}
    if len(keys) == 2 and keys[1] in FO_TEXT:
        m = _QTY_X.match(text)
        if not m:
            raise ValueError(f"要寫成「數量 x 種類」：{text!r}")
        return {keys[0]: num(m.group(1)), keys[1]: m.group(2)}
    if keys[0] in ("trunk_m", "leg_mm"):
        m = _LEN_TOL.match(text)
        if not m:
            raise ValueError(f"要寫成「長度 ± 公差」或「長度 +正 / 負」：{text!r}")
        length, sym, plus, minus = m.groups()
        return dict(zip(keys, [num(length), num(sym or plus), num(sym or minus)]))
    return parse_row(keys, text)


def fo_description(v):
    return (f"Fan-out assembly {fmt(v['fibres'])}F, {fmt(v['trunk_conn_qty'])} x {v['trunk_connector']} to "
            f"{fmt(v['leg_conn_qty'])} x {v['leg_connector']}, {v['end_face']}, "
            f"trunk {metres(v['trunk_m'])} m {tol_text(v['trunk_tol_plus_mm'], v['trunk_tol_minus_mm'])} mm, "
            f"legs {fmt(v['leg_mm'])} {tol_text(v['leg_tol_plus_mm'], v['leg_tol_minus_mm'])} mm")


def port_map(v):
    """PLANS P39：每芯一列 (芯號, MPO 號, MPO 上的位置, 支線號)。每個 MPO 一組支線；Method B 位置 1 接到組內最後一條。"""
    per_mpo = v["fibres"] // v["trunk_conn_qty"]
    per_leg = v["fibres"] // v["leg_conn_qty"]
    legs_per_group = per_mpo // per_leg
    rows = []
    for i in range(1, v["fibres"] + 1):
        mpo, pos = (i - 1) // per_mpo + 1, (i - 1) % per_mpo + 1
        k = (pos - 1) // per_leg
        leg_in_group = legs_per_group - k if v["polarity"] == "Method B" else k + 1
        rows.append((i, mpo, pos, (mpo - 1) * legs_per_group + leg_in_group))
    return rows


def fanout_errors(v):
    """port map 算得出來的前提：芯數能被主幹接頭數、支線數整除；極性只收 Method A／B。"""
    errors = []
    if v.get("polarity") not in POLARITIES:
        errors.append(f"參數 polarity：只能是 {'／'.join(POLARITIES)}，現在是 {v.get('polarity')!r}")
    f, t, legs = v.get("fibres"), v.get("trunk_conn_qty"), v.get("leg_conn_qty")
    if all(isinstance(x, int) and x > 0 for x in (f, t, legs)):
        if f % t or f % legs or (f // t) % (f // legs):
            errors.append(f"芯數 {f} 要能被主幹接頭數 {t}、支線數 {legs} 整除，且每個 MPO 的芯數要能分給整數條支線")
    else:
        errors.append("fibres、trunk_conn_qty、leg_conn_qty 要是正整數")
    return errors


TYPES = {
    "Fiber_Array": {"numeric": NUMERIC, "text": TEXT, "zero_ok": {"end_face_angle_deg"}, "rows": ROWS,
                    "row_text": row_text, "parse_row": parse_row, "description": description,
                    "block_description": "Fibre array block, assembled & polished"},
    "Fanout": {"numeric": FO_NUMERIC, "text": FO_TEXT,
               "zero_ok": {"trunk_tol_plus_mm", "trunk_tol_minus_mm", "leg_tol_plus_mm", "leg_tol_minus_mm"},
               "rows": FO_ROWS, "row_text": fo_row_text, "parse_row": fo_parse_row, "description": fo_description,
               "block_description": "Fan-out box sub-assembly"},
}


def required(product_type):
    t = TYPES[product_type]
    return t["numeric"] + t["text"]


_CH = re.compile(r"\b(\d+)\s*-?\s*(?:ch|channels?)\b", re.IGNORECASE)


def channel_mentions(text):
    return [int(n) for n in _CH.findall(text)]


def prev_sources(previous):
    """上一版審過的工程發行 → 一個參數、一列 BOM 各一個出處（不能引用整份 JSON）。"""
    out = {f"PREV {k}": fmt(v) for k, v in previous["params"].items()}
    out.update({f"PREV BOM {b['part_no']}": f"{b['description']} | qty {fmt(b['qty_per'])} {b['uom']}"
                for b in previous["bom"] if b["part_no"] != PENDING})   # issue #21：料號待填的列不當成料號
    return out

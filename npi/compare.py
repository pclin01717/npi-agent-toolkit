"""VERIFY STEP6-4：把各站 reviewed.json 跟 _ground_truth.json 比，只列出不同，不判失敗。"""
import json
from pathlib import Path

from .errors import NpiError
from .state import load

PARAM_MAP = {"channels": ("n_ch", 1), "pitch_um": ("pitch", 1000), "end_face_angle_deg": ("polish_angle", 1),
             "pigtail_mm": ("pigtail_len", 1), "pigtail_tol_mm": ("pigtail_tol", 1),
             "substrate_w_mm": ("sub_w", 1), "substrate_l_mm": ("sub_l", 1), "substrate_t_mm": ("sub_t", 1),
             "lid_w_mm": ("lid_w", 1), "lid_l_mm": ("lid_l", 1), "lid_t_mm": ("lid_t", 1),
             "boot_w_mm": ("boot_w", 1), "boot_h_mm": ("boot_h", 1), "boot_l_mm": ("boot_l", 1)}


def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-6
    return a == b


def _diff(out, label, ours, truth):
    if not _same(ours, truth):
        out.append(f"{label}：我方 {ours}，答案 {truth}")


def diff_release(r, gt):
    out = []
    _diff(out, "工程發行／lpc_pn", r["lpc_pn"], gt["project"]["lpc_pn"])
    _diff(out, "工程發行／block_pn", r["block_pn"], gt["project"]["block_pn"])
    params = PARAM_MAP if r.get("product_type", "Fiber_Array") == "Fiber_Array" else {}   # P44：fan-out 不比關鍵參數
    for key, (gkey, scale) in params.items():
        truth = gt["geometry"].get(gkey)
        _diff(out, f"工程發行／{key}", r["params"].get(key), None if truth is None else round(truth * scale, 6))
    ours = {b["part_no"]: b["qty_per"] for b in r["bom"]}
    truth = {b["pn"]: b["qty"] for b in gt["bom"]}
    for pn in sorted(set(ours) | set(truth)):
        _diff(out, f"工程發行／BOM {pn} 用量", ours.get(pn, "（沒有這個料）"), truth.get(pn, "（沒有這個料）"))
    return out


def diff_cost(c, gt):
    out = []
    _diff(out, "成本／直接材料 USD", c["material_total"], gt["unit_cost_usd"]["material_total"])
    _diff(out, "成本／總計 USD", c["total"] if c["complete"] else "（不完整）", gt["unit_cost_usd"]["total"])
    if "quote" in c:                                   # 第 3 批（VERIFY STEP12-1）
        _diff(out, "成本／報價 USD", c["quote"] if c["quote"] is not None else "（不完整）", gt.get("quote_price_usd"))
        _diff(out, "成本／報廢 USD", round(c["elements"]["Scrap"], 4) if c["complete"] else "（不完整）",
              gt["unit_cost_usd"].get("scrap"))
    return out


def diff_po(p, gt):
    out = []
    if gt.get("po"):
        _diff(out, "PO 核對／成品總數", p["po"]["total_qty"], gt["po"]["qty"])
        _diff(out, "PO 核對／PO 版次", p["po"]["rev"], gt["po"]["rev"])
    return out


def diff_supply(s, gt):
    out = []
    ours = {r["part_no"]: r["gross_qty"] for r in s["requirements"]}
    truth = {r["code"]: r["gross"] for r in gt.get("material_requirements", [])}
    for pn in sorted(set(ours) | set(truth)):
        _diff(out, f"供應鏈／{pn} 毛需求", ours.get(pn, "（沒有這個料）"), truth.get(pn, "（沒有這個料）"))
    return out


def diff_dfm(d, gt):
    """A0 比 DFM 項目（R 編號、風險）；ECR 比有判斷到的 CH。"""
    out = []
    ours = {i["ref"]: i.get("risk") or i.get("feasibility") for i in d.get("items", [])}
    if d.get("kind") == "dfm":
        truth = {i["ref"]: i.get("risk") for i in gt.get("dfm_items") or []}
    else:
        truth = {c["no"]: None for c in gt.get("changes") or []}
    for ref in sorted(set(ours) | set(truth)):
        if ref not in ours:
            out.append(f"DFM／{ref}：我方沒列，答案有（{truth[ref] or '-'}）")
        elif ref not in truth:
            out.append(f"DFM／{ref}：我方有列（{ours[ref] or '-'}），答案沒有")  # 程式內文字：對答案的差異訊息
        elif d.get("kind") == "dfm":
            _diff(out, f"DFM／{ref} 風險", ours[ref], truth[ref])
    return out


DIFFS = {"dfm": diff_dfm, "release": diff_release, "cost": diff_cost, "po": diff_po, "supply": diff_supply}


TIMELINE_MAP = {"DFM 回覆日": "dfm_feedback", "客戶同意": "customer_agreement", "規格發行日": "formal_spec_release",
                "客戶接受": "spec_acceptance", "成本送財務日": "unit_cost_to_finance", "財務確認": "finance_confirmed",
                "報價": "quotation", "收到 PO": "po_received", "備料通知日": "scm_notice",
                "收到 ECR": "ecr_received", "影響評估日": "impact_assessment", "客戶核准": "ecr_approval"}


def diff_timeline(events, gt):
    """VERIFY STEP9-6：時程表跟答案檔 timeline 不同的日期（答案沒有的事件不比）。"""
    out, truth = [], gt.get("timeline", {})
    for e in events:
        key = TIMELINE_MAP.get(e["event"])
        if key in truth:
            _diff(out, f"時程／{e['event']}", e["date"], truth[key])
    return out


def compare(out_root, input_root, npi_no, rev):
    state = load(out_root, npi_no)
    if not state["case_dir"]:
        raise NpiError(f"{npi_no} 還沒有跑過")
    gt_path = Path(input_root) / state["case_dir"] / rev / "_ground_truth.json"
    if not gt_path.exists():
        raise NpiError(f"找不到答案檔：{gt_path}")
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    out = []
    timeline = Path(out_root) / npi_no / rev / "timeline.json"
    if timeline.exists():
        out += diff_timeline(json.loads(timeline.read_text(encoding="utf-8"))["events"], gt)
    for station, fn in DIFFS.items():
        path = Path(out_root) / npi_no / rev / station / "reviewed.json"
        if path.exists():
            out += fn(json.loads(path.read_text(encoding="utf-8")), gt)
    return out

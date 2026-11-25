import email
import json
from email import policy

from npi import pipeline
from npi.pipeline import Ctx
from npi.stations import supply

from conftest import (A0_PO, A0_SPEC, B0_ECR, B0_PO, INPUT_ROOT, fixture_of, run_real)

NPI = "NPI-26-097"
CASE = "NPI-26-097_CPO_Fiber_Array"


def body_of(path):
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    return msg, msg.get_body(preferencelist=("plain",)).get_content()


def a0_supply(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "A0", st)
    pipeline.intake(A0_PO, INPUT_ROOT, out_root)
    run_real(out_root, "A0", "po")
    [path] = run_real(out_root, "A0", "supply")
    facts = json.loads((out_root / NPI / "A0" / "supply" / "facts.json").read_text(encoding="utf-8"))
    return path, facts


# STEP5-1
def test_STEP5_1_material_preparation_eml_subject(out_root):
    path, _ = a0_supply(out_root)
    msg, _ = body_of(path)
    assert path.name == "2026-11-02_Material_Preparation_NPI-26-097.eml"
    assert "NPI-26-097" in msg["Subject"] and "KVP-PO-7700-2614" in msg["Subject"]
    assert "nina.ho@lumora-photonics.com.tw" in msg["To"]


# STEP5-2
def test_STEP5_2_every_buy_item_listed(out_root):
    path, _ = a0_supply(out_root)
    _, body = body_of(path)
    buys = [b["part_no"] for b in fixture_of("A0", "release")["bom"] if b["make_buy"] == "Buy"]
    for part in buys:
        assert part in body, part


def test_STEP5_2_requirement_equals_qty_per_unit_times_po_qty(out_root):
    _, facts = a0_supply(out_root)
    req = {r["part_no"]: r for r in facts["requirements"]}
    assert req["RM-VG-Q24-127"]["gross_qty"] == 1 * 2000
    assert req["PP-MPO12-APC-F"]["gross_qty"] == 2 * 2000
    assert req["CM-EP-UV365"]["gross_qty"] is None          # 用量待填 → 需求量也待填


def test_STEP5_2_email_says_no_scrap_allowance(out_root):
    path, _ = a0_supply(out_root)
    _, body = body_of(path)
    assert "without scrap allowance" in body


# STEP5-3
def test_STEP5_3_change_notice_lists_added_removed_changed(out_root):
    pipeline.intake(A0_SPEC, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "A0", st)
    pipeline.intake(B0_ECR, INPUT_ROOT, out_root)
    for st in ("dfm", "release", "cost"):
        run_real(out_root, "B0", st)
    pipeline.intake(B0_PO, INPUT_ROOT, out_root)
    run_real(out_root, "B0", "po")
    [path] = run_real(out_root, "B0", "supply")
    assert path.name == "2026-11-02_Material_Change_Notice_NPI-26-097.eml"
    msg, body = body_of(path)
    assert "KVP-ECR-2408-01" in msg["Subject"]
    assert "Added" in body and "RM-VG-Q32-127" in body.split("Added")[1].split("Removed")[0]
    assert "Removed" in body and "RM-VG-Q24-127" in body.split("Removed")[1].split("Changed")[0]
    assert "Changed" in body
    changes = supply.bom_changes(
        [{"part_no": "A", "qty_per": 1, "make_buy": "Buy"}, {"part_no": "B", "qty_per": 2, "make_buy": "Buy"}],
        [{"part_no": "B", "qty_per": 3, "make_buy": "Buy"}, {"part_no": "C", "qty_per": 1, "make_buy": "Buy"}])
    assert changes == {"added": ["C"], "removed": ["A"], "changed": [{"part_no": "B", "from": 2, "to": 3}]}


# STEP5-4
def test_STEP5_4_c1_uses_previous_po_qty_and_names_revision(out_root):
    root = out_root / NPI
    bom = [{"item": "10.10", "part_no": "RM-VG-Q32-127", "description": "substrate", "make_buy": "Buy",
            "qty_per": 1, "uom": "pcs", "supplier": None, "lead_time_days": None, "remark": ""}]
    for rev in ("C0", "C1"):
        (root / rev / "release").mkdir(parents=True)
        (root / rev / "release" / "reviewed.json").write_text(json.dumps({"rev": rev, "bom": bom, "lpc_pn": "LPC-X"}))
    (root / "C0" / "po").mkdir(parents=True)
    (root / "C0" / "po" / "reviewed.json").write_text(json.dumps(
        {"rev": "C0", "po": {"po_no": "KVP-PO-7700-2614", "rev": 2, "total_qty": 6000, "schedule": []}}))
    ctx = Ctx(INPUT_ROOT, out_root, NPI, CASE, "C1", "supply", "2026-11-02")
    ctx.station_dir.mkdir(parents=True)
    facts = supply.prepare(ctx)
    assert facts["po"]["total_qty"] == 6000 and facts["po_from_rev"] == "C0"
    assert facts["requirements"][0]["gross_qty"] == 6000
    assert supply.check(ctx, facts, {"notes": []}) == []
    [path] = supply.render(ctx, facts, {"notes": []})
    _, body = body_of(path)
    assert "KVP-PO-7700-2614 Rev 2" in body and "C0" in body

import email
import json
from email import policy


from npi.pipeline import Ctx
from npi.readers.ecr import read_ecr
from npi.readers.spec import read_spec
from npi.sources import number_errors
from npi.stations import dfm

from conftest import (A0_SPEC, B0_ECR, C1_ECR, INPUT_ROOT, KALVARA_FIXTURES)

NPI = "NPI-26-097"
CASE = "NPI-26-097_CPO_Fiber_Array"


def ctx_for(out_root, rev):
    c = Ctx(INPUT_ROOT, out_root, NPI, CASE, rev, "dfm", "2026-11-02")
    c.station_dir.mkdir(parents=True, exist_ok=True)
    return c


def fixture(rev):
    return json.loads((KALVARA_FIXTURES / rev / "dfm.json").read_text(encoding="utf-8"))


def rendered_eml(out_root, rev):
    ctx = ctx_for(out_root, rev)
    facts = dfm.prepare(ctx)
    judgement = fixture(rev)
    assert dfm.check(ctx, facts, judgement) == []
    [path] = dfm.render(ctx, facts, judgement)
    return path, email.message_from_bytes(path.read_bytes(), policy=policy.default)


# STEP1-1
def test_STEP1_1_dfm_eml_written_under_output(out_root):
    path, _ = rendered_eml(out_root, "A0")
    assert path == out_root / NPI / "A0" / "dfm" / "2026-11-02_DFM_Feedback_KVP-SPC-2408.eml"


def test_STEP1_1_dfm_eml_recipient_and_subject(out_root):
    _, msg = rendered_eml(out_root, "A0")
    assert "priya.raman@kalvara-photonics.com" in msg["To"]
    assert "Priya Raman" in msg["To"]
    assert "KVP-RFQ-26-0311" in msg["Subject"]
    assert "KVP-SPC-2408 Rev X1" in msg["Subject"]


def test_STEP1_1_eml_is_unsent_draft(out_root):
    _, msg = rendered_eml(out_root, "A0")
    assert msg["X-Unsent"] == "1"


# STEP1-2
def test_STEP1_2_spec_reader_reads_r01_to_r15():
    spec = read_spec(A0_SPEC)
    assert [r["id"] for r in spec["requirements"]] == [f"R-{i:02d}" for i in range(1, 16)]
    assert spec["meta"]["spec_no"] == "KVP-SPC-2408"
    assert spec["meta"]["rev"] == "X1"
    assert spec["meta"]["rfq"] == "KVP-RFQ-26-0311"


def _a0(out_root):
    ctx = ctx_for(out_root, "A0")
    return ctx, dfm.prepare(ctx), fixture("A0")


def test_STEP1_2_item_without_r_id_rejected(out_root):
    ctx, facts, j = _a0(out_root)
    j["items"][0]["ref"] = "R-99"
    assert any("R-99" in e for e in dfm.check(ctx, facts, j))


def test_STEP1_2_capability_without_source_rejected(out_root):
    ctx, facts, j = _a0(out_root)
    j["items"][0]["capability_sources"] = []
    assert any("能力" in e and "來源" in e for e in dfm.check(ctx, facts, j))


def test_STEP1_2_unknown_qm_section_rejected(out_root):
    ctx, facts, j = _a0(out_root)
    j["items"][0]["capability_sources"] = ["QM-021 §13"]
    assert any("QM-021 §13" in e for e in dfm.check(ctx, facts, j))


def test_STEP1_2_unknown_ll_id_rejected(out_root):
    ctx, facts, j = _a0(out_root)
    j["items"][0]["capability_sources"] = ["LL-003 LL-99"]
    assert any("LL-003 LL-99" in e for e in dfm.check(ctx, facts, j))


# STEP1-3
def test_STEP1_3_number_not_in_cited_source_rejected():
    errs = number_errors("Lid approx. + USD 1.4 per pc", ["Fused-silica lid 5.0 x 5.0 x 0.7 mm, USD 3.10"])
    assert errs == ["1.4"]


def test_STEP1_3_pending_text_passes():
    assert number_errors("待工程師填寫", []) == []


def test_STEP1_3_codes_not_treated_as_numbers():
    text = "See LPC-QM-021 §4.1, MPO-12 kit, G.657.A2 fibre, DR-13 and R-03."
    assert number_errors(text, []) == []


def test_STEP1_3_both_ends_of_range_checked():
    assert number_errors("First samples in 3-9 weeks.", ["first samples 3-4 weeks"]) == ["9"]


def test_STEP1_3_thousand_separator_matches():
    assert number_errors("2,000 pcs by 2026-10-16", ["first PO 2000 pcs; complete by 2026-10-16"]) == []


def test_STEP1_3_number_without_any_citation_rejected(out_root):
    ctx, facts, j = _a0(out_root)
    j["notes"] = [{"text": "Unit price expected above USD 105.00.", "sources": []}]
    assert any("沒有引用" in e for e in dfm.check(ctx, facts, j))


# STEP1-4
def test_STEP1_4_ecr_reader_reads_b0_ch1_to_ch4():
    ecr = read_ecr(B0_ECR)
    assert [c["id"] for c in ecr["changes"]] == ["CH1", "CH2", "CH3", "CH4"]
    assert ecr["meta"]["ecr_no"] == "KVP-ECR-2408-01"
    assert ecr["po_revision"] is True


def test_STEP1_4_missing_ch_rejected(out_root):
    ctx = ctx_for(out_root, "B0")
    facts = dfm.prepare(ctx)
    j = fixture("B0")
    j["items"] = [i for i in j["items"] if i["ref"] != "CH3"]
    assert any("CH3" in e for e in dfm.check(ctx, facts, j))


def test_STEP1_4_impact_eml_subject_has_ecr_no(out_root):
    path, msg = rendered_eml(out_root, "B0")
    assert path.name == "2026-11-02_ECR-01_Impact_Assessment_NPI-26-097.eml"
    assert "KVP-ECR-2408-01" in msg["Subject"]
    body = msg.get_body(preferencelist=("plain",)).get_content()
    for ch in ("CH1", "CH2", "CH3", "CH4"):
        assert ch in body


# STEP1-5
def test_STEP1_5_ecr_reader_reads_c1_ch1_to_ch3_no_po_revision():
    ecr = read_ecr(C1_ECR)
    assert [c["id"] for c in ecr["changes"]] == ["CH1", "CH2", "CH3"]
    assert ecr["po_revision"] is False


def test_STEP1_5_po_change_rejected_when_ecr_says_no_po_revision(out_root):
    ctx = ctx_for(out_root, "C1")
    facts = dfm.prepare(ctx)
    j = fixture("C1")
    assert dfm.check(ctx, facts, j) == []
    j["po_change"] = "PO quantity to be revised."
    assert any("PO" in e for e in dfm.check(ctx, facts, j))

import json
from pathlib import Path

import pytest

from npi import stations

PROJECT = Path(__file__).resolve().parents[1]
INPUT_ROOT = PROJECT / "input"
KALVARA = INPUT_ROOT / "NPI-26-097_CPO_Fiber_Array"
KALVARA_FIXTURES = Path(__file__).parent / "fixtures" / "kalvara"
CORVANE = INPUT_ROOT / "NPI-26-104_FO36_Fanout"
CORVANE_FIXTURES = Path(__file__).parent / "fixtures" / "corvane"
FIXTURES = {"NPI-26-097": KALVARA_FIXTURES, "NPI-26-104": CORVANE_FIXTURES}

A0_SPEC = KALVARA / "A0/01_Customer_Draft_Spec/KVP-SPC-2408_RevX1_Fiber_Array_Draft_Spec.docx"
B0_ECR = KALVARA / "B0/01_Customer_ECR/KVP-ECR-2408-01_Engineering_Change_Request.docx"
C0_ECR = KALVARA / "C0/01_Customer_ECR/KVP-ECR-2408-02_Engineering_Change_Request.docx"
C1_ECR = KALVARA / "C1/01_Customer_ECR/KVP-ECR-2408-03_Engineering_Change_Request.docx"
A0_PO = KALVARA / "A0/05_Customer_PO/KVP-PO-7700-2614_Rev0.pdf"
B0_PO = KALVARA / "B0/05_Customer_PO/KVP-PO-7700-2614_Rev1.pdf"
CVN_A0_SPEC = CORVANE / "A0/01_Customer_Draft_Spec/CVN-SPC-3612_RevX1_Fanout_Draft_Spec.docx"
CVN_B0_ECR = CORVANE / "B0/01_Customer_ECR/CVN-ECR-3612-01_Engineering_Change_Request.docx"


@pytest.fixture
def out_root(tmp_path):
    return tmp_path / "output"


class FakeStation:
    """站的替身：只用來測總管的狀態機，產出一個文字檔。"""

    @staticmethod
    def prepare(ctx):
        return {"station": ctx.station}

    @staticmethod
    def check(ctx, facts, judgement):
        return []

    @staticmethod
    def render(ctx, facts, judgement):
        path = ctx.station_dir / f"{ctx.station}.txt"
        path.write_text("draft", encoding="utf-8")
        return [path]

    @staticmethod
    def read_back(ctx, facts, judgement):
        return {"text": (ctx.station_dir / f"{ctx.station}.txt").read_text(encoding="utf-8")}


@pytest.fixture
def fake_stations(monkeypatch):
    for name in stations.STATION_ORDER:
        monkeypatch.setitem(stations.REGISTRY, name, FakeStation)
    return FakeStation


def write_judgement(out_root, npi_no, rev, station, data):
    path = Path(out_root) / npi_no / rev / station / "judgement.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fixture_of(rev, station, npi="NPI-26-097"):
    return json.loads((FIXTURES[npi] / rev / f"{station}.json").read_text(encoding="utf-8"))


def run_real(out_root, rev, station, decisions="全部接受", npi="NPI-26-097", date="2026-11-02"):
    """用 fixture 判讀檔把一站真的跑完（prepare → render → approve）。date=None 時用時程表的日期。"""
    from npi import pipeline
    if station == "release":
        pipeline.decide(npi, rev, decisions, out_root)
    pipeline.prepare(npi, rev, station, INPUT_ROOT, out_root, date=date)
    write_judgement(out_root, npi, rev, station, fixture_of(rev, station, npi))
    files = pipeline.render(npi, rev, station, INPUT_ROOT, out_root)
    pipeline.approve(npi, rev, station, INPUT_ROOT, out_root)
    return files

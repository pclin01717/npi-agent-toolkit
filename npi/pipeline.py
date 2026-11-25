"""總管用的動作：intake、prepare、render、approve、reopen、decide、status。檔案讀寫集中在這裡。"""
import json
from dataclasses import dataclass
from pathlib import Path

from . import registry as reg
from . import state as st
from . import timeline as tl
from .errors import NpiError
from .intake import identify, schedule
from .readers import rules
from .readers.ecr import read_ecr, read_text
from .readers.master import read_ll003_products, read_mm002, read_pl
from .readers.po import quote_refs, read_po
from .readers.spec import read_spec
from .stations import REGISTRY, STATION_ORDER


@dataclass
class Ctx:
    input_root: Path
    out_root: Path
    npi_no: str
    case_dir: str
    rev: str
    station: str
    date: str

    @property
    def station_dir(self):
        return Path(self.out_root) / self.npi_no / self.rev / self.station

    @property
    def rev_input_dir(self):
        return Path(self.input_root) / self.case_dir / self.rev

    def station_dir_of(self, station, rev=None):
        return Path(self.out_root) / self.npi_no / (rev or self.rev) / station


def load_state(npi_no, out_root):
    return st.load(out_root, npi_no)


def schedule_for(doc):
    return schedule(doc)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def intake(path, input_root, out_root):
    doc = identify(path, input_root)
    state = st.load(out_root, doc.npi_no)
    if doc.kind == "ecr":
        blocker = st.ecr_blocker(state, doc.previous_rev)
        if blocker:
            raise NpiError(f"{Path(path).name}：{blocker}")
    state["case_dir"] = doc.case_dir
    rev = state["revs"].setdefault(doc.rev, {"docs": [], "stations": []})
    rel = str(Path(path).resolve().relative_to(Path(input_root).resolve()))
    if not any(d["path"] == rel for d in rev["docs"]):
        rev["docs"].append({"kind": doc.kind, "path": rel})
    for name in schedule(doc):
        if not st.find(state, doc.rev, name):
            rev["stations"].append({"name": name, "status": st.NOT_RUN, "date": None})
    rev["stations"].sort(key=lambda s: STATION_ORDER.index(s["name"]))   # 不管收件順序，站的先後固定
    st.save(out_root, state)
    _update_registry(doc, input_root, out_root)
    if _doc_of(state, doc.rev, "draft_spec" if doc.rev == "A0" else "ecr", input_root):
        timeline(doc.npi_no, doc.rev, input_root, out_root)
    nxt = next((s["name"] for s in rev["stations"] if s["status"] != st.REVIEWED), None)
    return {"npi_no": doc.npi_no, "rev": doc.rev, "kind": doc.kind,
            "previous_rev": doc.previous_rev, "stations": [s["name"] for s in rev["stations"]],
            "next": nxt}


def _update_registry(doc, input_root, out_root):
    """PLANS P55、表 G：第一次先收主資料的號碼；每份交進來的 ECR 收它提到的報價單號。"""
    entries = reg.load(out_root)
    if not any(e["source"] == "MM-002" for e in entries):
        entries = reg.merge(entries, reg.master_entries(read_pl(input_root)["materials"],
                                                        read_ll003_products(input_root), read_mm002(input_root)))
    if doc.kind == "ecr":
        entries = reg.merge(entries, reg.quote_entries(read_text(doc.path), f"{doc.npi_no} {doc.rev} ECR"))
    if doc.kind == "po":                          # P95：客戶 PO 上的報價單號也登記
        entries = reg.merge(entries, [reg.quote_entry(no, f"{doc.npi_no} {doc.rev} PO", date)
                                      for no, date in quote_refs(read_po(doc.path)["text"])])
    reg.save(out_root, entries)


def _doc_of(state, rev, kind, input_root):
    d = next((d for d in state["revs"].get(rev, {}).get("docs", []) if d["kind"] == kind), None)
    return Path(input_root) / d["path"] if d else None


def timeline_path(out_root, npi_no, rev):
    return Path(out_root) / npi_no / rev / "timeline.json"


def _minor(state, rev, input_root, out_root):
    """版次種類：變更影響審過就用判讀（P54），還沒審就看 ECR 有沒有寫 No PO revision。"""
    reviewed = Path(out_root) / state["npi_no"] / rev / "dfm" / "reviewed.json"
    if reviewed.exists():
        return _read_json(reviewed).get("revision_kind") == "minor"
    return read_ecr(_doc_of(state, rev, "ecr", input_root))["po_revision"] is False


def timeline(npi_no, rev, input_root, out_root):
    """PLANS 表 F：算這個版次的時程表，寫進 timeline.json，回傳事件清單。"""
    state = st.load(out_root, npi_no)
    initial = rev == "A0"
    doc = _doc_of(state, rev, "draft_spec" if initial else "ecr", input_root)
    if doc is None:
        raise NpiError(f"{rev} 還沒有收到客戶{'草稿 spec' if initial else ' ECR'}，排不出時程")
    received = (read_spec(doc) if initial else read_ecr(doc))["meta"]["date"]
    po = _doc_of(state, rev, "po", input_root)
    path = timeline_path(out_root, npi_no, rev)
    overrides = _read_json(path)["overrides"] if path.exists() else {}
    fixed = {tl.station_event(s["name"], rev): s["date"] for s in state["revs"][rev]["stations"] if s["date"]}
    events = tl.compute(tl.INITIAL if initial else tl.ECR, received, rules.timeline_days(input_root),
                        po_date=read_po(po)["date"] if po else None,
                        minor=False if initial else _minor(state, rev, input_root, out_root),
                        overrides=overrides, fixed=fixed)
    _write_json(path, {"overrides": overrides, "events": events})
    return events


def _override(npi_no, rev, event, date, input_root, out_root):
    """P52：工程師指定某個事件的日期（寫進時程表）。"""
    if tl.is_weekend(date):
        raise NpiError(f"{event} 指定的 {date} 是週六或週日，請換一個工作天")
    path = timeline_path(out_root, npi_no, rev)
    before = path.read_text(encoding="utf-8") if path.exists() else None
    saved = _read_json(path) if path.exists() else {"overrides": {}}
    saved["overrides"][event] = date
    _write_json(path, saved)
    try:                                          # 順序不對（issue #32）就退回原本的時程表
        timeline(npi_no, rev, input_root, out_root)
    except NpiError:
        path.write_text(before, encoding="utf-8") if before is not None else path.unlink()
        raise


def _ctx(state, rev, station, input_root, out_root, date=None):
    if not state["case_dir"]:
        raise NpiError(f"{state['npi_no']} 還沒有收過客戶文件，先 intake")
    return Ctx(Path(input_root), Path(out_root), state["npi_no"], state["case_dir"], rev, station, date)


def decisions_path(out_root, npi_no, rev):
    return Path(out_root) / npi_no / rev / "decisions.json"


def decide(npi_no, rev, text, out_root):
    """記下工程師轉述的客戶決定（原文照存）。"""
    if not text.strip():
        raise NpiError("客戶決定是空的")
    return _write_json(decisions_path(out_root, npi_no, rev), {"rev": rev, "text": text.strip()})


def prepare(npi_no, rev, station, input_root, out_root, date=None):
    state = st.load(out_root, npi_no)
    has_decisions = decisions_path(out_root, npi_no, rev).exists()
    blocker = st.prepare_blocker(state, rev, station, has_decisions)
    if blocker:
        raise NpiError(blocker)
    entry = st.find(state, rev, station)
    event = tl.station_event(station, rev)
    if date:                                      # P52：--date 是工程師指定這站的事件日
        _override(npi_no, rev, event, date, input_root, out_root)
        entry["date"] = date
    elif not entry["date"]:                       # 第一次 prepare 才從時程表取，之後重跑不變
        entry["date"] = {e["event"]: e["date"] for e in timeline(npi_no, rev, input_root, out_root)}[event]
    ctx = _ctx(state, rev, station, input_root, out_root, entry["date"])
    ctx.station_dir.mkdir(parents=True, exist_ok=True)
    facts = REGISTRY[station].prepare(ctx)
    st.save(out_root, state)
    return _write_json(ctx.station_dir / "facts.json", facts)


def _loaded(npi_no, rev, station, input_root, out_root):
    state = st.load(out_root, npi_no)
    entry = st.find(state, rev, station)
    if not entry:
        raise NpiError(f"{rev} 的排程裡沒有「{station}」")
    ctx = _ctx(state, rev, station, input_root, out_root, entry["date"])
    for name in ("facts.json", "judgement.json"):
        if not (ctx.station_dir / name).exists():
            raise NpiError(f"{ctx.station_dir / name} 不存在")
    return state, entry, ctx, _read_json(ctx.station_dir / "facts.json"), _read_json(ctx.station_dir / "judgement.json")


def render(npi_no, rev, station, input_root, out_root):
    blocker = st.prepare_blocker(st.load(out_root, npi_no), rev, station,
                                 decisions_path(out_root, npi_no, rev).exists())
    if blocker:                                   # 上游被 reopen 時，不能拿舊檔案直接 render
        raise NpiError(blocker)
    state, entry, ctx, facts, judgement = _loaded(npi_no, rev, station, input_root, out_root)
    if "sources" in facts:                        # P60：工程師在對話裡給的值（ENG-n）也是出處
        facts["sources"].update({e["id"]: e["text"] for e in _engineer(ctx)})
    errors = REGISTRY[station].check(ctx, facts, judgement)
    if errors:
        raise NpiError("判讀檔沒通過檢查：\n- " + "\n- ".join(errors))
    files = REGISTRY[station].render(ctx, facts, judgement)
    if station == "release" and "lpc_pn" in judgement:   # P55：render 成功才登記；同一版次重跑是覆蓋
        reg.save(out_root, reg.register(reg.load(out_root), judgement["lpc_pn"], reg.PRODUCT_PN,
                                        f"{npi_no} {rev}", entry["date"]))
    entry["status"] = st.PENDING
    st.save(out_root, state)
    return files


def _engineer(ctx):
    path = ctx.station_dir / "engineer.json"
    return _read_json(path) if path.exists() else []


def tell(npi_no, rev, station, text, out_root):
    """P60：工程師在對話裡給的值，原話存成 ENG-n。只能在這站未跑或待審時用。"""
    if not text.strip():
        raise NpiError("工程師的話是空的")
    state = st.load(out_root, npi_no)
    entry = st.find(state, rev, station)
    if not entry:
        raise NpiError(f"{rev} 的排程裡沒有「{station}」")
    if entry["status"] == st.REVIEWED:
        raise NpiError(f"{rev} 的「{st.display_name(station, rev)}」已審；要改請先 reopen")
    ctx = _ctx(state, rev, station, "", out_root)
    items = _engineer(ctx)
    item = {"id": f"ENG-{len(items) + 1}", "text": text.strip()}
    _write_json(ctx.station_dir / "engineer.json", items + [item])
    return item["id"]


def approve(npi_no, rev, station, input_root, out_root):
    state, entry, ctx, facts, judgement = _loaded(npi_no, rev, station, input_root, out_root)
    if entry["status"] != st.PENDING:
        raise NpiError(f"{rev} 的「{st.display_name(station, rev)}」目前是{entry['status']}，不是待審")
    reviewed = REGISTRY[station].read_back(ctx, facts, judgement)
    path = _write_json(ctx.station_dir / "reviewed.json", reviewed)
    entry["status"] = st.REVIEWED
    st.save(out_root, state)
    return path


def reopen(npi_no, rev, station, out_root):
    state = st.load(out_root, npi_no)
    if not st.find(state, rev, station):
        raise NpiError(f"{rev} 的排程裡沒有「{station}」")
    for r, name in st.reset_downstream(state, rev, station):
        folder = Path(out_root) / npi_no / r / name
        old = sorted(f for f in folder.iterdir() if f.name != "engineer.json") if folder.is_dir() else []   # 子資料夾也搬（#66）
        if old:                                            # 搬出站資料夾、不刪除（P100）：站代理看不到，每次 reopen 各一個編號；工程師的話留著
            n = 1
            while (folder.parent / "_reopened" / f"{name}_{n}").exists():
                n += 1
            dest = folder.parent / "_reopened" / f"{name}_{n}"
            dest.mkdir(parents=True)
            for f in old:
                f.replace(dest / f.name)
    st.save(out_root, state)


def upstream(ctx, station, rev=None):
    """讀上一站（或上一版某站）審過的結果。"""
    path = ctx.station_dir_of(station, rev) / "reviewed.json"
    if not path.exists():
        raise NpiError(f"找不到審過的結果：{path}")
    return _read_json(path)


def format_status(state):
    lines = [f"{state['npi_no']}"]
    for rev, data in state["revs"].items():
        parts = [f"{st.display_name(s['name'], rev)}：{s['status']}" for s in data["stations"]]
        lines.append(f"  {rev}　" + "　".join(parts))
    lines.append(f"下一步：{st.next_step(state)}")
    return "\n".join(lines)

"""每個案子的 state.json 與 PLANS 表 C。判定是純函式；讀寫只在 load／save。"""
import json
from pathlib import Path

from .intake import REVS

NOT_RUN, PENDING, REVIEWED = "未跑", "待審", "已審"


def display_name(station, rev):
    if station == "dfm":
        return "DFM" if rev == "A0" else "變更影響"
    return {"release": "工程發行", "cost": "成本", "po": "PO 核對", "supply": "供應鏈"}[station]


def state_path(out_root, npi_no):
    return Path(out_root) / npi_no / "state.json"


def load(out_root, npi_no):
    path = state_path(out_root, npi_no)
    if not path.exists():
        return {"npi_no": npi_no, "case_dir": None, "revs": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save(out_root, state):
    path = state_path(out_root, state["npi_no"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def find(state, rev, station):
    for s in state["revs"].get(rev, {}).get("stations", []):
        if s["name"] == station:
            return s
    return None


def unreviewed(state, rev):
    return [s for s in state["revs"].get(rev, {}).get("stations", []) if s["status"] != REVIEWED]


def ecr_blocker(state, previous_rev):
    """表 C 第 1 列：收到 ECR 時，上一版每一站都要已審。回傳錯誤訊息或 None。"""
    if previous_rev not in state["revs"]:
        return f"上一版 {previous_rev} 還沒有跑過"
    pending = unreviewed(state, previous_rev)
    if pending:
        s = pending[0]
        return f"上一版 {previous_rev} 的「{display_name(s['name'], previous_rev)}」還沒審（目前：{s['status']}）"  # 程式內文字：給 /npi 總管的狀態訊息
    return None


def prepare_blocker(state, rev, station, has_decisions):
    """表 C 第 2～5 列。回傳錯誤訊息或 None。"""
    entries = state["revs"].get(rev, {}).get("stations", [])
    names = [s["name"] for s in entries]
    if station not in names:
        return f"{rev} 的排程裡沒有「{display_name(station, rev)}」"
    for s in entries[:names.index(station)]:
        if s["status"] != REVIEWED:
            return f"{rev} 的「{display_name(s['name'], rev)}」還沒審（目前：{s['status']}）"
    if station == "release" and not has_decisions:
        return f"{rev} 還沒有客戶決定：請工程師提供每個 R／CH 接受或不接受（用 decide 記下）"  # 程式內文字：給 /npi 總管的狀態訊息
    if station == "po":
        cost = find(state, rev, "cost")
        if not cost or cost["status"] != REVIEWED:
            return f"{rev} 的「成本」還沒審，不能核對 PO"  # 程式內文字：給 /npi 總管的狀態訊息
    if find(state, rev, station)["status"] == REVIEWED:
        return f"{rev} 的「{display_name(station, rev)}」已審；要重跑請先 reopen"  # 程式內文字：給 /npi 總管的狀態訊息
    return None


def reset_downstream(state, rev, station):
    """P5：reopen 一站時，這站和之後的站（含之後的版次）都退回未跑。"""
    hit, reset = False, []
    for r in REVS:
        for s in state["revs"].get(r, {}).get("stations", []):
            if r == rev and s["name"] == station:
                hit = True
            if hit:
                s["status"] = NOT_RUN
                reset.append((r, s["name"]))
    return reset


def next_step(state):
    for rev in REVS:
        for s in state["revs"].get(rev, {}).get("stations", []):
            name = display_name(s["name"], rev)
            if s["status"] == PENDING:
                return f"審「{name}」（{rev}）"
            if s["status"] == NOT_RUN:
                return f"跑「{name}」（{rev}）"
    return "沒有待辦；等下一份客戶文件"  # 程式內文字：給 /npi 總管的狀態訊息

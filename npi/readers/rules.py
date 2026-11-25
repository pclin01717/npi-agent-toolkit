"""讀 input/00_Factory_Master_Data/LPC作業規則.md（PLANS P57）。入口檢查在這裡。

出處名稱：`RULES §<節> <表或條目名> <列名>`，每個出處只放一個值：
- 表格一列放兩組（工作站 | 費率 | 工作站 | 費率）就拆成兩個。
- 條列用「。」「，」「；」分開的子項各一個，名稱取子項裡第一個數字前面的字。
"""
import re
from pathlib import Path

from ..errors import NpiError

FILE = "00_Factory_Master_Data/LPC作業規則.md"
_SECTION = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$")
_BOLD_ITEM = re.compile(r"^\s*-\s+\*\*(.+?)\*\*\s*(.*)$")
_NUMBERED = re.compile(r"^\s+\d+\.\s+(.+?)：(.*)$")
_BULLET = re.compile(r"^\s*-\s+(.*)$")
_SPLIT = re.compile(r"[。，；、]")
_FIRST_DIGIT = re.compile(r"\d")
_NAME_TAIL = re.compile(r"(通常|約|限|為|是|一般為)$")
_CLEAN_NAME = re.compile(r"^[\w\s\u4e00-\u9fff／/–\-]+$")


def _path(input_root):
    path = Path(input_root) / FILE
    if not path.exists():
        raise NpiError(f"找不到作業規則：{path}")
    return path


def _plain(text):
    return text.replace("**", "").strip()


def _cells(line):
    return [_plain(c) for c in line.strip().strip("|").split("|")]


def _sub_items(text):
    """「一般 500–1,500 顆，PM 陣列約 300 顆」→ [("一般", "一般 500–1,500 顆"), ("PM 陣列", …)]；沒有數字的子項不收。"""
    parts = [p.strip() for p in _SPLIT.split(_plain(text)) if p.strip()]
    parts = [p for p in parts if _FIRST_DIGIT.search(p)]
    out = []
    for i, p in enumerate(parts, 1):
        name = p[:_FIRST_DIGIT.search(p).start()].strip(" （(：")
        name = _NAME_TAIL.sub("", name).strip()
        if not name or not _CLEAN_NAME.match(name) or any(name == n for n, _ in out):
            name = str(i)
        out.append((name, p))
    return out


def _key(section, *names):
    return " ".join(["RULES", f"§{section}"] + [n for n in names if n])


def parse(text):
    """作業規則全文 → {出處名稱: 原文}。純函式。"""
    out = {}
    section = title = group = label = None
    header = None
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            section, title = m.group(1), re.sub(r"（.*?）", "", m.group(2)).strip()
            group = label = header = None
            continue
        if section is None:
            continue
        if line.strip().startswith("|"):
            cells = _cells(line)
            if header is None:
                header = cells
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            table = label or group or title
            pairs = len(header) >= 4 and len(header) % 2 == 0 and header[0::2] == [header[0]] * (len(header) // 2)
            if pairs:
                for name, value in zip(cells[0::2], cells[1::2]):
                    if name:
                        out[_key(section, table, name)] = f"{name} {value}"
            else:
                out[_key(section, table, cells[0])] = " | ".join(cells)
            continue
        header = None
        if not line.strip():
            continue
        m = _BOLD_ITEM.match(line)
        if m:
            label = _plain(m.group(1)).rstrip("：:").strip()
            rest = m.group(2).lstrip("：:").strip()
            items = _sub_items(rest)
            if not items and rest:                     # 沒有數字的規則（例如 §2 小改）整句收，給依據欄引用
                out[_key(section, group, label)] = _plain(rest)
            if len(items) == 1:
                out[_key(section, group, label)] = items[0][1]
            for name, part in items if len(items) > 1 else []:
                out[_key(section, group, label, name)] = part
            continue
        m = _NUMBERED.match(line)
        if m:
            out[_key(section, label, _plain(m.group(1)))] = _plain(m.group(2))
            continue
        m = _BULLET.match(line)
        if m and line.startswith("-"):
            label = None
            for name, part in _sub_items(m.group(1)):
                out[_key(section, group, name)] = part
            continue
        if line.rstrip().endswith("：") and not line.startswith(" "):
            group, label = _plain(line).rstrip("：").strip(), None
    return out


def rule_sources(input_root):
    return parse(_path(input_root).read_text(encoding="utf-8"))


def timeline_days(input_root):
    """§2 初版表：{列名: {"days": 常見值的第一個數字, "source": 出處名稱, "text": 原文}}。"""
    out = {}
    for key, text in rule_sources(input_root).items():
        if not key.startswith("RULES §2 初版 "):
            continue
        cells = text.split(" | ")
        nums = re.findall(r"\d+", cells[-1]) if len(cells) == 3 else []
        if not nums:
            raise NpiError(f"作業規則「{key}」的常見值讀不到天數：{text}")
        out[key[len("RULES §2 初版 "):]] = {"days": int(nums[0]), "source": key, "text": text}
    if not out:
        raise NpiError("作業規則 §2 找不到初版的時程表")
    return out


def people(input_root):
    """§1 人員表：{角色: {"name", "title"}}。"""
    out = {}
    for key, text in rule_sources(input_root).items():
        if not key.startswith("RULES §1 人員與寄件 "):
            continue
        role, who = text.split(" | ")[0], text.split(" | ")[1]
        name, _, rest = who.partition("，")
        out[role] = {"name": name.strip(), "title": re.sub(r"（.*?）", "", rest).strip()}
    return out


def rates(input_root):
    """§3 工作站費率：{"FPR": 22, …}（USD／小時）。"""
    out = {}
    for key, text in rule_sources(input_root).items():
        if key.startswith("RULES §3 工作站費率 "):
            code, value = text.split()
            out[code] = float(value) if "." in value else int(value)
    if not out:
        raise NpiError("作業規則 §3 找不到工作站費率")
    return out


ROUTING_NAMES = {"Fiber_Array": "光纖陣列", "Fanout": "扇出線"}


def base_routings(input_root):
    """§4 標準製程：{產品類型: [[這一步可以用的工作站…], …]}。標「另計」的步驟（批次驗證）不算（P63）。"""
    codes = set(rates(input_root))
    sources = rule_sources(input_root)
    out = {}
    for ptype, name in ROUTING_NAMES.items():
        text = sources.get(f"RULES §4 標準製程 {name}")
        if not text:
            raise NpiError(f"作業規則 §4 找不到「{name}」的工序")
        steps = []
        for step in text.split(" | ", 1)[1].split("→"):
            if "另計" in step:
                continue
            found = [c for c in re.findall(r"[A-Z]{3}", step) if c in codes]
            if found:
                steps.append(sorted(set(found), key=found.index))
        out[ptype] = steps
    return out


RATIO_KEYS = {"handling": "RULES §3 單位成本 物料管理費", "overhead": "RULES §3 單位成本 製造費用",
              "sga": "RULES §3 單位成本 管銷", "margin": "RULES §3 報價 1", "rounding": "RULES §3 報價 無條件進位到 USD"}


def ratios(input_root):
    """§3 的固定費率（PLANS P72）：{"handling": (0.03, 出處), …}；進位是 USD 金額，其他是比率。"""
    sources = rule_sources(input_root)
    out = {}
    for name, key in RATIO_KEYS.items():
        text = sources.get(key)
        if text is None:
            raise NpiError(f"作業規則找不到「{key}」")
        if name == "rounding":
            m = re.search(r"USD\s*(\d+(?:\.\d+)?)", text)
            value = float(m.group(1)) if m else None
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            value = round(float(m.group(1)) / 100, 6) if m else None
        if value is None:
            raise NpiError(f"作業規則「{key}」讀不到數字：{text}")
        out[name] = (value, key)
    return out

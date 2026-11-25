"""PLANS 表 D：不編數字。純函式。"""
import re

PENDING = "待工程師填寫"
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_SPLIT = re.compile(r"[\s,;:()\[\]{}\"'/=]+")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _words(text):
    return [w for w in _SPLIT.split(_THOUSANDS.sub("", text)) if w]


def _norm(num):
    f = float(num)
    return str(int(f)) if f.is_integer() else repr(f)


_SHORT_CODE = re.compile(r"^[A-Za-z]{1,3}\d{1,2}[A-Za-z]?$")        # A0、X1、CH1、P01
_SEP_CODE = re.compile(r"^[A-Z][A-Z0-9]*[-.][A-Za-z0-9.-]*\d")     # R-03、LPC-QM-021、G.657.A2、R6.3


def is_code(word):
    """表 D 第 1 列：代號不算數字。§ 開頭、大寫開頭接連字號／點、或 1～3 個字母＋1～2 位數字。"""
    return word.startswith("§") or bool(_SHORT_CODE.match(word) or _SEP_CODE.match(word))


def claimed_numbers(text):
    """文字裡要查出處的數字。代號不算；其他字母開頭的詞（USD5000、x500、交期12週）裡的數字要查。"""
    out = []
    for w in _words(text):
        w = w.lstrip("±+-~≈≤≥<>*#").rstrip(".")
        if not w or is_code(w):
            continue
        if _DATE.fullmatch(w):
            out.append(w)
            continue
        out += [n for n in _NUM.findall(w)]
    return out


def available_numbers(texts):
    pool = set()
    for t in texts:
        t = _THOUSANDS.sub("", t)
        pool.update(_DATE.findall(t))
        pool.update(_norm(n) for n in _NUM.findall(_DATE.sub(" ", t)))   # 日期整個比，不拆成年月日
    return pool


def number_errors(text, source_texts):
    """回傳 text 裡找不到出處的數字（照出現順序，不重複）。"""
    pool = available_numbers(source_texts)
    bad = []
    for n in claimed_numbers(text):
        key = n if _DATE.fullmatch(n) else _norm(n)
        if key not in pool and n not in bad:
            bad.append(n)
    return bad


_MENTIONS = [(re.compile(r"§\s?(\d+(?:\.\d+)?)"), "QM-021 §{}"),
             (re.compile(r"\b((?:LL|DR)-\d+)\b"), "LL-003 {}"),
             (re.compile(r"\b((?:R|OP)-\d{2})\b"), "{}"),
             (re.compile(r"\b(CH\d+)\b"), "{}")]


def mention_errors(label, text, sources):
    """表 D 第 1 列：文字裡提到的 QM-021 章節、LL-003 條目、R／OP／CH 編號要存在。"""
    errors = []
    for pattern, key in _MENTIONS:
        for m in pattern.findall(text or ""):
            if key.format(m) not in sources:
                errors.append(f"{label}：提到的 {m} 不存在（找不到 {key.format(m)}）")
    return errors


def field_errors(label, text, cited_ids, sources):
    """一個欄位的檢查：引用的出處要存在；提到的編號要存在；數字要出現在引用的出處原文裡。"""
    errors = [f"{label}：引用的出處「{i}」不存在" for i in cited_ids if i not in sources]
    errors += mention_errors(label, text, sources)
    if not text or text.strip() == PENDING:
        return errors
    if claimed_numbers(text) and not cited_ids:
        return errors + [f"{label}：有數字（{'、'.join(claimed_numbers(text))}）但沒有引用任何出處"]
    bad = number_errors(text, [sources[i] for i in cited_ids if i in sources])
    return errors + [f"{label}：數字 {n} 在引用的出處裡找不到" for n in bad]


_RANGE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*[–-]\s*(\d[\d,]*(?:\.\d+)?)")


def value_errors(label, value, cited_ids, sources):
    """PLANS P58：引用的出處寫成範圍（500–1,500、10–30）時，值落在範圍內（含兩端）就算有出處；否則照表 D 找同一個數字。"""
    errors = [f"{label}：引用的出處「{i}」不存在" for i in cited_ids if i not in sources]
    ranges = [m for i in cited_ids if i in sources for m in _RANGE.findall(sources[i])]
    if ranges and isinstance(value, (int, float)):
        if any(float(lo.replace(",", "")) <= value <= float(hi.replace(",", "")) for lo, hi in ranges):
            return errors
        shown = "、".join(f"{lo}–{hi}" for lo, hi in ranges)
        return errors + [f"{label}：{_norm(value)} 不在引用的範圍 {shown} 裡"]
    text = PENDING if value == PENDING else _norm(value) if isinstance(value, (int, float)) else str(value)
    return errors + field_errors(label, text, [i for i in cited_ids if i in sources], sources)

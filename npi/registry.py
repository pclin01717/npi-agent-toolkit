"""PLANS 表 G、P55、P56：已用編號的登記表。判定是純函式；檔案讀寫只在 load／save。"""
import json
import re
from pathlib import Path

PRODUCT_PN, LPC_PO, QUOTE = "product_pn", "lpc_po", "quote"
_PO = re.compile(r"\b(PO-L26-\d{4})\b(?:\s*\((\d{4}-\d{2}-\d{2})\))?")
_QUOTE = re.compile(r"\b(LPC-Q-\d{2}-\d{4}(?:-R\d+)?)\s+dated\s+(\d{4}-\d{2}-\d{2})")


def path_of(out_root):
    return Path(out_root) / "registry.json"


def load(out_root):
    path = path_of(out_root)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save(out_root, entries):
    path = path_of(out_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")


def _entry(number, kind, source, date, owner=None):
    return {"number": number, "kind": kind, "source": source, "date": date, "owner": owner}


def master_entries(pl_materials, ll_products, mm_codes):
    """表 G 第 1～3 列。pl_materials：{料號: 價格表那一列}；ll_products：LL-003 Products 的列。"""
    out = []
    for code, row in pl_materials.items():
        for number, date in _PO.findall(str(row.get("Last PO / Quote Reference") or "")):
            out.append(_entry(number, LPC_PO, f"PL {code}", date or None))
    for row in ll_products:
        if row.get("LPC P/N"):
            start = row.get("NPI Start")
            out.append(_entry(str(row["LPC P/N"]), PRODUCT_PN, f"LL-003 {row['ID']}",
                              str(start)[:10] if start else None))
    out += [_entry(code, PRODUCT_PN, "MM-002", None) for code in mm_codes]
    return out


def quote_entries(text, source):
    """表 G 第 4 列：客戶文件裡的 LPC-Q-…（含 -R1、-R2）和 dated 日期。"""
    return [_entry(number, QUOTE, source, date) for number, date in _QUOTE.findall(text)]


def quote_entry(number, source, date):
    return _entry(number, QUOTE, source, date)


def merge(entries, new):
    """加進沒有的；同一號碼、種類、來源已經有就不重複加（重跑一樣）。"""
    seen = {(e["number"], e["kind"], e["source"]) for e in entries}
    out = list(entries)
    for e in new:
        if (e["number"], e["kind"], e["source"]) not in seen:
            seen.add((e["number"], e["kind"], e["source"]))
            out.append(e)
    return out


def register(entries, number, kind, owner, date):
    """工具自己用的號碼（表 G 第 5 列）。同一個 owner、種類只有一筆：重跑是覆蓋自己那筆。"""
    out = [e for e in entries if not (e["owner"] == owner and e["kind"] == kind)]
    return out + [_entry(number, kind, "NPI 工具", date, owner)]


def used(entries, as_of, owner):
    """P56：日期不晚於 as_of（沒有日期的、工具自己登記的一律算，issue #34），不含 owner 自己登記的。"""
    return {e["number"] for e in entries
            if e["owner"] != owner and (e["date"] is None or e["source"] == "NPI 工具" or e["date"] <= as_of)}


def product_pn_errors(pn, prev_pn, used_numbers):
    """P55：成品料號字尾字母要跟上一版不同；不能是別人用過的。"""
    errors = []
    if not pn[-1:].isalpha():
        errors.append(f"成品料號 {pn} 的字尾不是字母（作業規則 §7：每一版換一個字尾字母）")
    elif prev_pn and pn[-1] == prev_pn[-1]:
        errors.append(f"成品料號 {pn} 的字尾字母跟上一版 {prev_pn} 一樣；每一版都要換，小改也換（作業規則 §7）")
    if pn in used_numbers:
        errors.append(f"成品料號 {pn} 已經用過（登記表、MM-002 或 LL-003），請換一個")
    return errors

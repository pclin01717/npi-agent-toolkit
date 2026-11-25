"""糾正紀錄檢查（PLANS S5；CLAUDE.md 規則 11）：同一類糾正第二次出現時，一定要對應到存在的檢查。

用法：`.venv/bin/python check_corrections.py`（讀 progress.md 的「## Corrections」表）。有違規就列出第幾列、回傳 1。pre-commit 會跑。
表頭固定：`| # | What was corrected | Dates | Became which check |`；Dates 一次一個 YYYY-MM-DD，用逗號分開。

一列照順序比對，先符合的決定結果：
| 順序 | 條件 | 結果 |
| --- | --- | --- |
| 1 | 找不到「## Corrections」、表頭不一樣，或表頭下一行不是分隔線 | 違規（整張表） |
| 2 | 欄數不是 4 | 違規 |
| 3 | Dates 用逗號分開的每一項，有一項不是剛好一個 YYYY-MM-DD 的真實日期；或一個日期都沒有 | 違規 |
| 4 | 檢查欄以 `文字規則：` 開頭 | 要用反引號寫出規則所在的檔案（專案裡存在），反引號外還要寫原因；否則違規 |
| 5 | 檢查欄有字 | 要有反引號名稱，而且每個都是檢查：`tests/` 裡頂層 `def test_…(` 的測試函式，或專案裡（相對路徑、不含 `..`）的 `check_*.py`、`ruff.toml`；否則違規 |
| 6 | 檢查欄是空的，日期 2 個以上 | 違規：已糾正 N 次，還沒變成檢查 |
| 7 | 其他 | 通過 |
"""
import re
import sys
from datetime import date
from pathlib import Path

HEADER = "| # | What was corrected | Dates | Became which check |"
DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
SEPARATOR = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+$")
CHECK_FILE = re.compile(r"^(?:[\w.-]+/)*(?:check_\w+\.py|ruff\.toml)$")
NAME = re.compile(r"`([^`]+)`")
TEXT_RULE = "文字規則："


def _section(text):
    m = re.search(r"^## Corrections\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def _is_check(name, root):
    if CHECK_FILE.match(name):
        return _is_file(name, root)
    if not re.fullmatch(r"test_\w+", name):
        return False
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.M)
    return any(pattern.search(p.read_text(encoding="utf-8")) for p in Path(root, "tests").rglob("*.py"))


def _is_file(name, root):
    return not Path(name).is_absolute() and ".." not in Path(name).parts and (Path(root) / name).is_file()


def _real_date(text):
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _date_errors(cell):
    items = [x.strip() for x in cell.split(",") if x.strip()]
    if not items:
        return ["Dates 沒有 YYYY-MM-DD 日期"], 0
    bad = [x for x in items if len(DATE.findall(x)) != 1 or not _real_date(DATE.findall(x)[0])]
    return ([f"Dates 這幾項不是剛好一個 YYYY-MM-DD：{'、'.join(bad)}"] if bad else []), len(items)


def check(text, root):
    """回傳違規說明的清單；空的就是通過。"""
    section = _section(text)
    lines = [ln.strip() for ln in (section or "").splitlines() if ln.strip().startswith("|")]
    if not lines or lines[0] != HEADER or len(lines) < 2 or not SEPARATOR.match(lines[1]):
        return [f"progress.md 找不到「## Corrections」、表頭不是 {HEADER}，或表頭下一行不是分隔線"]
    errors = []
    for i, line in enumerate(lines[2:], 1):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 4:
            errors.append(f"第 {i} 列：要 4 欄，這列有 {len(cells)} 欄")
            continue
        date_errors, count = _date_errors(cells[2])
        found = cells[3]
        if date_errors:
            errors += [f"第 {i} 列：{e}" for e in date_errors]
        elif found.startswith(TEXT_RULE):
            rest = found[len(TEXT_RULE):]
            files = [n for n in NAME.findall(rest) if _is_file(n, root)]
            if not files or not NAME.sub("", rest).strip(" ,;，；。"):
                errors.append(f"第 {i} 列：「{TEXT_RULE}」後面要用反引號寫出規則所在的檔案（要存在），再寫為什麼做不成檢查")
        elif found:
            names = NAME.findall(found)
            missing = [n for n in names if not _is_check(n, root)]
            if not names:
                errors.append(f"第 {i} 列：檢查欄要用反引號寫出測試函式或檢查檔的名稱")
            elif missing:
                errors.append(f"第 {i} 列：這些不是存在的測試函式或檢查檔：{'、'.join(missing)}")
        elif count >= 2:
            errors.append(f"第 {i} 列：已糾正 {count} 次，還沒變成檢查（{cells[1]}）")
    return errors


def main(args, root=Path(".")):
    errors = check((Path(root) / "progress.md").read_text(encoding="utf-8"), root)
    for e in errors:
        print(e)
    print(f"糾正紀錄檢查：{len(errors)} 處違規。", file=sys.stderr)
    if errors:
        print("第二次被糾正的事要變成測試或檢查（CLAUDE.md 規則 11）；做不成檢查才寫「文字規則：」加原因。", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

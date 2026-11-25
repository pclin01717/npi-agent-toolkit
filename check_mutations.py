"""突變測試工具（PLANS S6；CLAUDE.md 規則 5 (a)、9 (2)）：一次改一處程式，跑指定的測試，看測試有沒有抓到，再把檔案還原。

用法：`.venv/bin/python check_mutations.py [id ...]`（不給 id = `mutations.json` 全部）。有沒抓到或出錯的就回傳 1。
`mutations.json` 每筆：`id`、`file`（相對專案根目錄）、`find`（原文，要剛好出現一次）、`replace`、`tests`（要跑的測試檔）。

一筆突變照順序比對，先符合的決定結果：
| 順序 | 條件 | 結果 |
| --- | --- | --- |
| 0 | `file` 不在專案裡，或在 `input/` 底下（不分大小寫；原始資料唯讀） | 出錯，檔案不動 |
| 1 | `find` 在檔案裡出現 0 次或 2 次以上 | 出錯，檔案不動 |
| 1a | 沒改之前跑同一組測試，pytest 不是回傳 0（同一組測試只跑一次） | 出錯：沒改之前測試就沒過，抓到也不算數 |
| 2 | 跑完（不論結果）檔案沒有還原成原本的位元組 | 出錯，並印出要手動還原的檔案 |
| 3 | 改完跑測試，pytest 回傳 1（有測試失敗） | 抓到 |
| 4 | pytest 回傳 0（全部通過） | 沒抓到 |
| 5 | pytest 回傳其他值（收集失敗、參數錯誤等） | 出錯 |

跑測試時一律排除 SELF_CHECK（issue #49），並設 PYTHONDONTWRITEBYTECODE=1，不留下突變版的 .pyc（issue #56）。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

DATA = Path("mutations.json")
# 這條測試檢查 mutations.json 的原文都還在；突變正好改掉原文，跑它一定失敗，會讓每個突變都誤算成抓到（issue #49）
SELF_CHECK = "tests/test_dev_checks.py::test_S6_repo_mutations_resolve"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pytest(tests, root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                           "--deselect", SELF_CHECK, *tests], cwd=root, env=env, capture_output=True, text=True).returncode


def run_one(m, root, baseline=None):
    """回傳 (結果, 說明)，結果是 caught／survived／error。baseline：同一組測試沒改之前的結果，main 跨突變共用。"""
    root = Path(root).resolve()
    path = (root / m["file"]).resolve()
    inside = path.is_relative_to(root)
    if not inside or path.relative_to(root).parts[0].casefold() == "input" or not path.is_file():   # macOS 不分大小寫（#65）
        return "error", f"{m['file']} 不是專案裡、input/ 以外的檔案"
    original = path.read_bytes()
    count = original.decode("utf-8").count(m["find"])
    if count != 1:
        return "error", f"{m['file']} 裡「{m['find']}」出現 {count} 次，要剛好 1 次"
    baseline = {} if baseline is None else baseline
    key = tuple(m["tests"])
    if key not in baseline:
        baseline[key] = _pytest(m["tests"], root)
    if baseline[key] != 0:
        return "error", f"沒改之前測試就沒過（pytest 回傳 {baseline[key]}），抓到也不算數"
    try:
        path.write_bytes(original.decode("utf-8").replace(m["find"], m["replace"]).encode("utf-8"))
        code = _pytest(m["tests"], root)
    finally:
        path.write_bytes(original)
    if path.read_bytes() != original:
        return "error", f"{m['file']} 沒有還原成原本的內容，請手動還原"
    if code == 1:
        return "caught", "測試失敗"
    if code == 0:
        return "survived", "測試全部通過"
    return "error", f"pytest 回傳 {code}（不是測試失敗，是跑不起來）"


def main(args, root=Path("."), data=DATA):
    entries = load(Path(root) / data if not Path(data).is_absolute() else data)
    unknown = set(args) - {m["id"] for m in entries}
    if unknown:
        print(f"mutations.json 裡沒有這些 id：{'、'.join(sorted(unknown))}", file=sys.stderr)
        return 1
    chosen = [m for m in entries if not args or m["id"] in args]
    bad, baseline = 0, {}
    for m in chosen:
        result, detail = run_one(m, root, baseline)
        label = {"caught": "抓到", "survived": "沒抓到", "error": "出錯"}[result]
        print(f"{m['id']}：{label}（{m['file']}：「{m['find']}」→「{m['replace']}」；{detail}）")
        bad += result != "caught"
    print(f"突變測試：跑了 {len(chosen)} 個，{len(chosen) - bad} 個抓到，{bad} 個沒抓到或出錯。", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

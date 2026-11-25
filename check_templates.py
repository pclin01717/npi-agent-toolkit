"""範本與邏輯分離的檢查：程式碼裡不准寫死對外文案和版面，這些要放 templates/。

用法：`.venv/bin/python check_templates.py [資料夾或 .py ...]`（預設 `npi`）。有違規就列出位置、回傳 1。
只讀原始碼的語法樹，不執行被檢查的程式。

一個字串照順序比對，先符合的決定結果：
| 順序 | 條件 | 結果 |
| --- | --- | --- |
| 1 | 那一行有 `# 程式內文字：<原因>` | 放行 |
| 2 | 含 HTML 標籤或 CSS（`<div`、`style=`、`font-size`、`12px` 等） | 違規：版面 |
| 3 | 不像文案句子（中文字少於 8 個，或沒有。，、！？；：） | 放行 |
| 4 | docstring | 放行 |
| 5 | 在 `raise`、`...Error(...)`、`print`／log、argparse 說明裡 | 放行（錯誤和操作訊息） |
| 6 | 加進 errors／found／problems／warnings 清單（`.append`、`.extend`） | 放行（檢查錯誤訊息） |
| 7 | 在名字是 `check` 或結尾 `_errors`／`_findings`／`_check` 的函式裡 | 放行（檢查錯誤訊息） |
| 8 | 其他 | 違規：文案 |

f-string 把固定的部分接起來當成一個字串判斷。
"""
import ast
import re
import sys
from pathlib import Path

ALLOW = re.compile(r"#\s*程式內文字：\s*\S")
LAYOUT = re.compile(r"<\s*/?\s*(div|p|span|table|tr|td|th|br|h[1-6]|ul|ol|li|img|style|section|strong|em|b|i|a)\b"
                    r"|\bstyle\s*=|font-(size|family|weight)\s*:|\b\d+(px|pt|em)\b", re.I)
HAN = re.compile(r"[㐀-鿿]")
PUNCT = re.compile(r"[。，、！？；：]")
MESSAGE_CALLS = {"print", "debug", "info", "warning", "error", "exception", "log", "echo",
                 "add_argument", "add_parser", "ArgumentParser"}
ERROR_LISTS = {"errors", "found", "problems", "warnings"}
CHECK_FUNC = re.compile(r"^(check|.*_errors|.*_findings|.*_check)$")


def _call_name(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _allowed_context(node, parents):
    """順序 4～7。"""
    p = parents.get(node)
    if isinstance(p, ast.Expr) and isinstance(parents.get(p), (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return True
    while p is not None:
        if isinstance(p, ast.Raise):
            return True
        if isinstance(p, ast.Call):
            name = _call_name(p)
            if name in MESSAGE_CALLS or name.endswith("Error"):
                return True
            if name in {"append", "extend"} and getattr(getattr(p.func, "value", None), "id", "") in ERROR_LISTS:
                return True
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return bool(CHECK_FUNC.match(p.name))
        p = parents.get(p)
    return False


def _strings(tree):
    """回傳 (節點, 固定文字)。f-string 的固定部分接起來算一個。"""
    inside = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            parts = [v.value for v in n.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            inside.update(id(v) for v in n.values)
            yield n, "".join(parts)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in inside:
            yield n, n.value


def check_file(path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    found = []
    for node, text in _strings(tree):
        if ALLOW.search(lines[node.lineno - 1]):
            continue
        if LAYOUT.search(text):
            found.append((node.lineno, "版面", text))
        elif len(HAN.findall(text)) >= 8 and PUNCT.search(text) and not _allowed_context(node, parents):
            found.append((node.lineno, "文案", text))
    return sorted(found)


def main(args):
    paths = [Path(a) for a in (args or ["npi"])]
    files = sorted(f for p in paths for f in ([p] if p.suffix == ".py" else p.rglob("*.py")))
    total = 0
    for f in files:
        for lineno, kind, text in check_file(f):
            total += 1
            print(f"{f}:{lineno}：{kind}寫死在程式裡：{text[:60]!r}")
    print(f"範本檢查：看了 {len(files)} 個檔案，{total} 處違規。", file=sys.stderr)
    if total:
        print("文案和版面要放 templates/；確定要留在程式裡的，在那一行加「# 程式內文字：原因」。", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

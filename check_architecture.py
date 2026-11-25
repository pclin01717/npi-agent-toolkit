"""架構檢查：PLANS「檔案結構」寫的分層，用語法樹檢查 `npi/` 有沒有照做（全域規則「在入口檢查、中間寫純函式」）。

用法：`.venv/bin/python check_architecture.py`。有違規就列出位置、回傳 1。只讀原始碼的語法樹，不執行被檢查的程式。

一處 import 或呼叫照順序比對，先符合的決定結果：
| 順序 | 條件 | 結果 |
| --- | --- | --- |
| 1 | 列在 KNOWN（已知、還沒清的） | 放行；KNOWN 裡的項目在程式裡已經找不到 → 違規「請從 KNOWN 拿掉」，只能變少 |
| 2 | 純函式模組（PURE）import I/O 函式庫（IO_LIBS）或 PURE 以外的 npi 模組 | 違規 |
| 3 | 純函式模組呼叫檔案 I/O（IO_CALLS） | 違規 |
| 4 | 讀寫集中的模組（IO_AT）在指定函式以外呼叫檔案 I/O | 違規 |
| 5 | `npi/readers/` import `stations`、`render`、`pipeline`、`compare`、`pending` | 違規（讀檔器是入口，不往下游拿東西） |
| 6 | `npi/render/` import `readers`、`stations`、`pipeline` | 違規（產出工具只管寫） |
| 7 | 其他 | 放行 |
"""
import ast
import sys
from pathlib import Path

ROOT = Path("npi")
PURE = {"npi.errors", "npi.sources", "npi.params", "npi.costing", "npi.timeline", "npi.intake"}
IO_AT = {"npi.state": {"state_path", "load", "save"}, "npi.registry": {"path_of", "load", "save"}}
IO_LIBS = {"os", "shutil", "subprocess", "openpyxl", "docx", "pdfplumber", "cadquery", "matplotlib", "jinja2"}
IO_CALLS = {"open", "read_text", "write_text", "read_bytes", "write_bytes", "mkdir", "unlink", "rmdir", "touch",
            "exists", "is_dir", "is_file", "glob", "rglob", "iterdir", "stat", "load_workbook", "Document"}
NO_IMPORT = {"npi.readers": ("npi.stations", "npi.render", "npi.pipeline", "npi.compare", "npi.pending"),
             "npi.render": ("npi.readers", "npi.stations", "npi.pipeline")}
# (模組, 規則順序, 內容)：寫的時候就有、還沒清的。清掉就從這裡拿掉；不准新增，要新增先問使用者。
KNOWN = {
    ("npi.intake", 3, "is_dir"): "identify 查版次底下有沒有 05_Customer_PO 資料夾（表 B 要用）；要搬到 pipeline 得改測試的呼叫方式",
    ("npi.readers.ours", 5, "npi.render.docx_out"): "讀回正式 spec 要用寫出時同一份表頭對照 HEADER；該搬到 params 之類的共用處",
}


def module_of(path):
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_package(path):
    return path.name == "__init__.py"


def _resolve(node, mod, package):
    """回傳這個 import 碰到的模組名（`from X import y` 時 y 是模組就算 X.y）。"""
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    base = mod.split(".") if package else mod.split(".")[:-1]
    if node.level:
        base = base[:len(base) - (node.level - 1)]
        name = ".".join(base + ([node.module] if node.module else []))
    else:
        name = node.module
    out = [name]
    for a in node.names:
        sub = f"{name}.{a.name}"
        if (Path(*sub.split(".")).with_suffix(".py")).exists() or (Path(*sub.split(".")) / "__init__.py").exists():
            out.append(sub)
    return out


def _under(name, prefix):
    return name == prefix or name.startswith(prefix + ".")


def _call_name(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def check_file(path):
    """回傳 [(行號, 規則順序, 內容, 說明)]，還沒套 KNOWN。"""
    mod = module_of(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    funcs = {}
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                funcs.setdefault(id(n), f.name)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for name in _resolve(n, mod, _is_package(path)):
                if mod in PURE and (name.split(".")[0] in IO_LIBS or (_under(name, "npi") and name not in PURE and name != "npi")):
                    found.append((n.lineno, 2, name, f"純函式模組 import 了 {name}"))
                for layer, banned in NO_IMPORT.items():
                    if _under(mod, layer) and any(_under(name, b) for b in banned):
                        found.append((n.lineno, 5 if layer == "npi.readers" else 6, name, f"{layer} 不能 import {name}"))
        elif isinstance(n, ast.Call) and _call_name(n) in IO_CALLS:
            name = _call_name(n)
            if mod in PURE:
                found.append((n.lineno, 3, name, f"純函式模組做了檔案 I/O：{name}()"))
            elif mod in IO_AT and funcs.get(id(n)) not in IO_AT[mod]:
                found.append((n.lineno, 4, name, f"檔案 I/O 只能在 {'、'.join(sorted(IO_AT[mod]))}：{name}()"))
    return mod, sorted(set(found))


def main(args):
    files = sorted(ROOT.rglob("*.py"))
    total, seen = 0, set()
    for f in files:
        mod, found = check_file(f)
        for lineno, rule, what, why in found:
            if (mod, rule, what) in KNOWN:
                seen.add((mod, rule, what))
                continue
            total += 1
            print(f"{f}:{lineno}：規則 {rule}，{why}")
    for key in sorted(set(KNOWN) - seen):
        total += 1
        print(f"KNOWN {key} 在程式裡已經找不到，請從 check_architecture.py 的 KNOWN 拿掉")
    print(f"架構檢查：看了 {len(files)} 個檔案，{total} 處違規（已知待清 {len(seen)} 處）。", file=sys.stderr)
    if total:
        print("照 PLANS「檔案結構」的分層改；真的要例外，先問使用者再加進 KNOWN。", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

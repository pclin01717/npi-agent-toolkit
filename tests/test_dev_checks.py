"""開發用的檢查工具（PLANS S5 糾正紀錄、S6 突變測試）。每條測試在暫存資料夾自己造資料，只有最後一條讀 repo 本身。"""
import json

import pytest

from conftest import PROJECT

# ---------- PLANS S6：突變測試工具 ----------
import check_mutations

MOD = "def add(a, b):\n    # 加法\n    return a + b\n"
TEST = "from mod import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


@pytest.fixture
def toy(tmp_path):
    (tmp_path / "mod.py").write_text(MOD, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(TEST, encoding="utf-8")
    return tmp_path


def mutation(find, replace, tests=("tests/test_mod.py",)):
    return {"id": "M1", "file": "mod.py", "find": find, "replace": replace, "tests": list(tests)}


def test_S6_caught_when_tests_fail(toy):
    result, _ = check_mutations.run_one(mutation("a + b", "a - b"), toy)
    assert result == "caught"


def test_S6_survived_when_tests_pass(toy):
    m = mutation("# 加法", "# 減法")
    result, _ = check_mutations.run_one(m, toy)
    assert result == "survived"
    path = toy / "mutations.json"
    path.write_text(json.dumps([m]), encoding="utf-8")
    assert check_mutations.main([], root=toy, data=path) == 1


@pytest.mark.parametrize("find", ["no such text", "a"])
def test_S6_find_must_be_unique(toy, find):
    result, detail = check_mutations.run_one(mutation(find, "x"), toy)
    assert result == "error" and "mod.py" in detail
    assert (toy / "mod.py").read_text(encoding="utf-8") == MOD


def test_S6_file_restored(toy):
    for m in (mutation("a + b", "a - b"),                                  # 測試失敗
              mutation("a + b", "a - b", tests=("tests/no_such_test.py",)),  # pytest 本身出錯
              mutation("return a + b", "return (")):                       # 語法錯誤
        result, _ = check_mutations.run_one(m, toy)
        assert (toy / "mod.py").read_bytes() == MOD.encode("utf-8"), m
    assert result in {"caught", "error"}


def test_S6_repo_mutations_resolve():
    entries = check_mutations.load(PROJECT / "mutations.json")
    assert len(entries) >= 6
    for m in entries:
        text = (PROJECT / m["file"]).read_text(encoding="utf-8")
        assert text.count(m["find"]) == 1, m["id"]
        assert all((PROJECT / t).exists() for t in m["tests"]), m["id"]


# ---------- PLANS S5：糾正紀錄 ----------
import check_corrections

HEADER = "## Corrections\nintro\n| # | What was corrected | Dates | Became which check |\n| --- | --- | --- | --- |\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_known():\n    pass\n", encoding="utf-8")
    (tmp_path / "check_x.py").write_text("", encoding="utf-8")
    return tmp_path


def table(*rows):
    return HEADER + "".join(f"| {i} | {what} | {dates} | {check} |\n" for i, (what, dates, check) in enumerate(rows, 1)) \
        + "\n## Later\n"


def test_S5_two_dates_without_check_blocked(repo):
    errors = check_corrections.check(table(("a", "2026-11-01", ""), ("b", "2026-11-01, 2026-11-20", "")), repo)
    assert len(errors) == 1 and "第 2 列" in errors[0] and "2 次" in errors[0]


def test_S5_one_date_without_check_passes(repo):
    assert check_corrections.check(table(("a", "2026-11-01", "")), repo) == []


def test_S5_named_check_must_exist(repo):
    two = "2026-11-01, 2026-11-20"
    assert check_corrections.check(table(("a", two, "`test_known`"), ("b", two, "`check_x.py`")), repo) == []
    errors = check_corrections.check(table(("a", two, "`test_missing`"), ("b", "2026-11-01", "`check_x.py` and `nope.py`"),
                                           ("c", two, "will add a lint rule")), repo)
    assert [e.split("：")[0] for e in errors] == ["第 1 列", "第 2 列", "第 3 列"]


def test_S5_text_rule_needs_reason(repo):
    two = "2026-11-01, 2026-11-20"
    (repo / "CLAUDE.md").write_text("", encoding="utf-8")    # 2026-11-24 使用者同意照 #54 改：檔名用反引號、檔案要存在
    assert check_corrections.check(table(("a", two, "文字規則：`CLAUDE.md` rule 11; needs judgement")), repo) == []
    assert len(check_corrections.check(table(("a", two, "文字規則：")), repo)) == 1


def test_S5_malformed_rows_reported(repo):
    assert "第 1 列" in check_corrections.check(table(("a", "last week", "")), repo)[0]
    assert check_corrections.check(table(("a", "2026-11-01", "")).replace("| Dates |", "| When |"), repo)
    assert check_corrections.check("## Later\n", repo)
    broken = HEADER + "| 1 | a | 2026-11-01 |\n"
    assert "第 1 列" in check_corrections.check(broken, repo)[0]


def test_S5_repo_progress_passes():
    assert check_corrections.check((PROJECT / "progress.md").read_text(encoding="utf-8"), PROJECT) == []


# Fixes #49：突變工具要排除「mutations.json 的原文都還在」那條自我檢查，否則改到列出的原文一定算抓到
def test_issue49_self_check_test_excluded(toy):
    (toy / "tests" / "test_dev_checks.py").write_text(
        "from pathlib import Path\n\n\ndef test_S6_repo_mutations_resolve():\n"
        "    assert '# 加法' in (Path(__file__).parents[1] / 'mod.py').read_text(encoding='utf-8')\n", encoding="utf-8")
    m = mutation("# 加法", "# 減法", tests=("tests/test_mod.py", "tests/test_dev_checks.py"))
    assert check_mutations.run_one(m, toy)[0] == "survived"


# Fixes #50：pytest 本身跑不起來（找不到測試檔）要算出錯，不算抓到
def test_issue50_pytest_error_reported_as_error(toy):
    result, detail = check_mutations.run_one(mutation("a + b", "a - b", tests=("tests/no_such_test.py",)), toy)
    assert result == "error" and "pytest 回傳" in detail


def two(check):
    return table(("a", "2026-11-01, 2026-11-20", check))


# Fixes #51：表頭下面一定要是分隔線，否則第一列會被當分隔線跳過
def test_issue51_separator_required(repo):
    text = HEADER.replace("| --- | --- | --- | --- |\n", "") + "| 1 | a | 2026-11-01, 2026-11-20 | |\n"
    assert check_corrections.check(text, repo)


# Fixes #52：每個日期都要是 YYYY-MM-DD；貼著中文的日期也要算到
def test_issue52_every_date_item_checked(repo):
    assert check_corrections.check(table(("a", "2026-11-01, 2026/11/25", "")), repo)
    assert check_corrections.check(table(("a", "2026-11-01, 11-25", "")), repo)
    assert "2 次" in check_corrections.check(table(("a", "第一次2026-11-01, 第二次2026-11-20", "")), repo)[0]


# Fixes #53：只有測試函式（def test_…）或檢查檔（check_*.py、ruff.toml）算檢查
def test_issue53_only_tests_and_check_files_count(repo):
    (repo / "tests" / "test_x.py").write_text("def test_known():\n    pass\n\n\ndef helper():\n    pass\n", encoding="utf-8")
    (repo / "ruff.toml").write_text("", encoding="utf-8")
    (repo / "README.md").write_text("", encoding="utf-8")
    assert check_corrections.check(two("`ruff.toml`"), repo) == []
    for bad in ("`README.md`", "`tests`", "`helper`", "`/etc/hosts`"):
        assert check_corrections.check(two(bad), repo), bad


# Fixes #54：文字規則要用反引號寫出規則所在的檔案（要存在），後面再寫原因
def test_issue54_text_rule_needs_location_and_reason(repo):
    (repo / "CLAUDE.md").write_text("", encoding="utf-8")
    assert check_corrections.check(two("文字規則：`CLAUDE.md` rule 11, needs judgement of the spec"), repo) == []
    for bad in ("文字規則：x", "文字規則：`CLAUDE.md`", "文字規則：`NOPE.md` needs judgement"):
        assert check_corrections.check(two(bad), repo), bad


# Fixes #55：沒改之前測試就沒過，突變不能算抓到
def test_issue55_baseline_must_pass(toy):
    (toy / "tests" / "test_mod.py").write_text(TEST + "\n\ndef test_broken():\n    assert False\n", encoding="utf-8")
    result, detail = check_mutations.run_one(mutation("a + b", "a - b"), toy)
    assert result == "error" and "沒改之前" in detail


# Fixes #56：跑突變時不能留下突變版的 .pyc（同長度、同一秒還原時會被載入）
def test_issue56_no_bytecode_from_mutated_source(toy, monkeypatch):
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)    # 工具要自己關掉，不能靠呼叫的人的環境
    check_mutations.run_one(mutation("a + b", "a - b"), toy)
    assert not list(toy.rglob("mod.*.pyc"))


# Fixes #57：mutations.json 不能指到 input/ 或專案外面
@pytest.mark.parametrize("target", ["input/x.py", "../outside.py"])
def test_issue57_target_must_be_inside_project_not_input(toy, target):
    m = dict(mutation("a + b", "a - b"), file=target)
    assert check_mutations.run_one(m, toy)[0] == "error"


# Fixes #59：main 全部抓到回傳 0；不認得的 id 回傳 1
def test_issue59_main_exit_codes(toy):
    path = toy / "mutations.json"
    path.write_text(json.dumps([mutation("a + b", "a - b")]), encoding="utf-8")
    assert check_mutations.main([], root=toy, data=path) == 0
    assert check_mutations.main(["NOPE"], root=toy, data=path) == 1


# Fixes #61（突變 S6-caught-code 沒抓到）：沒改之前測試會過、改完 pytest 收集失敗（回傳 2）→ 出錯，不算抓到
def test_issue61_collection_error_after_mutation_is_error(toy):
    result, detail = check_mutations.run_one(mutation("return a + b", "return ("), toy)
    assert result == "error" and "pytest 回傳 2" in detail


# Fixes #62（突變 S5-check-file 沒抓到）：檢查檔的名稱對但檔案不存在 → 違規
def test_issue62_missing_check_file_reported(repo):
    assert check_corrections.check(two("`check_missing.py`"), repo)


# Fixes #63（突變 S6-inside 沒抓到）：目標檔存在也一樣，input/ 底下和專案外面都不准改
def test_issue63_existing_targets_outside_or_input_refused(toy):
    (toy / "input").mkdir()
    (toy / "input" / "x.py").write_text("a + b\n", encoding="utf-8")
    (toy.parent / "outside.py").write_text("a + b\n", encoding="utf-8")
    for target in ("input/x.py", "../outside.py"):
        assert check_mutations.run_one(dict(mutation("a + b", "a - b"), file=target), toy)[0] == "error", target
    assert (toy / "input" / "x.py").read_text(encoding="utf-8") == "a + b\n"
    assert (toy.parent / "outside.py").read_text(encoding="utf-8") == "a + b\n"


# Fixes #64：檢查檔的路徑不能用 .. 跑到專案外面
def test_issue64_check_file_outside_project_refused(repo):
    outside = repo.parent / "elsewhere"
    outside.mkdir()
    (outside / "check_x.py").write_text("", encoding="utf-8")
    assert check_corrections.check(two("`../elsewhere/check_x.py`"), repo)


# Fixes #65：macOS 檔案系統不分大小寫，Input/ 也是 input/
def test_issue65_input_any_case_refused(toy):
    (toy / "input").mkdir()
    (toy / "input" / "x.py").write_text("a + b\n", encoding="utf-8")
    assert check_mutations.run_one(dict(mutation("a + b", "a - b"), file="Input/x.py"), toy)[0] == "error"
    assert (toy / "input" / "x.py").read_text(encoding="utf-8") == "a + b\n"


# Fixes #67：日期要是真的日期
def test_issue67_impossible_date_refused(repo):
    assert check_corrections.check(table(("a", "2026-13-45", "")), repo)

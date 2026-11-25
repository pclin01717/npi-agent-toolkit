"""PLANS 表 F：每個版次的時程表（P49～P51）。純函式；timeline.json 的讀寫在 pipeline.py。"""
import datetime

from .errors import NpiError

INITIAL, ECR = "initial", "ecr"
ENGINEER, CUSTOMER, ESTIMATED = "工程師指定", "客戶文件", "推算"


def add_workdays(date, n):
    """往後推 n 個工作天，只跳過週六、週日（沒有國定假日資料，P49）。"""
    day = datetime.date.fromisoformat(date)
    while n > 0:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day.isoformat()


def is_weekend(date):
    return datetime.date.fromisoformat(date).weekday() >= 5


def _row(days, name):
    for key, row in days.items():
        if key.startswith(name):
            return row
    raise NpiError(f"作業規則 §2 初版表找不到「{name}」")


def _steps(kind, days, minor):
    """[(事件, 前一個事件, 天數, 依據)]；前一個事件是 None 表示日期來自客戶文件。"""
    def d(name):
        return _row(days, name)["days"]

    def basis(name, prefix=""):
        row = _row(days, name)
        return f"{prefix}{row['source']}：常見值 {row['days']} 天"

    quote = "財務確認 → 報價"
    if kind == INITIAL:
        return [("收到草稿 spec", None, 0, "客戶草稿 spec 上的日期（P50）"),
                ("DFM 回覆日", "收到草稿 spec", d("收到 draft spec → 回 DFM"), basis("收到 draft spec → 回 DFM")),
                ("客戶同意", "DFM 回覆日", d("DFM → 客戶同意"), basis("DFM → 客戶同意")),
                ("規格發行日", "客戶同意", d("客戶同意 → 正式規格發行"), basis("客戶同意 → 正式規格發行")),
                ("客戶接受", "規格發行日", d("規格發行 → 客戶接受"), basis("規格發行 → 客戶接受")),
                ("成本送財務日", "客戶接受", d("客戶接受 → 成本送財務"), basis("客戶接受 → 成本送財務")),
                ("財務確認", "成本送財務日", d("送財務 → 財務確認"), basis("送財務 → 財務確認")),
                ("報價", "財務確認", 1, f"{_row(days, quote)['source']}：「1–2 天」取 1（P51）"),
                ("收到 PO", "報價", d("報價 → 客戶 PO"), basis("報價 → 客戶 PO")),
                ("備料通知日", "收到 PO", d("收到 PO → 備料通知"), basis("收到 PO → 備料通知"))]
    reuse = "沿用初版："
    steps = [("收到 ECR", None, 0, "ECR 上的日期（P50）"),
             ("影響評估日", "收到 ECR", 2, "RULES §2 工程變更（ECR） 流程：影響評估「2–3 天」取 2（P51）"),  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
             ("客戶核准", "影響評估日", d("DFM → 客戶同意"), basis("DFM → 客戶同意", reuse)),
             ("規格發行日", "客戶核准", d("客戶同意 → 正式規格發行"), basis("客戶同意 → 正式規格發行", reuse))]
    if minor:
        rule = "RULES §2 工程變更（ECR） 小改：規格發行隔天（P51）"  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
        return steps + [("成本送財務日", "規格發行日", 1, rule), ("備料通知日", "規格發行日", 1, rule)]
    to_finance = d("規格發行 → 客戶接受") + d("客戶接受 → 成本送財務")
    to_po = d("送財務 → 財務確認") + 1 + d("報價 → 客戶 PO")
    return steps + [
        ("成本送財務日", "規格發行日", to_finance,
         f"{reuse}{_row(days, '規格發行 → 客戶接受')['source']} ＋ {_row(days, '客戶接受 → 成本送財務')['source']}：共 {to_finance} 天（P51）"),
        ("收到 PO", "成本送財務日", to_po, f"{reuse}財務確認、報價（取 1）、客戶 PO：共 {to_po} 天"),  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
        ("備料通知日", "收到 PO", d("收到 PO → 備料通知"), basis("收到 PO → 備料通知", reuse))]


FIXED = "已產出"


def compute(kind, received, days, po_date=None, minor=False, overrides=None, fixed=None):
    """回傳 [{"event", "date", "basis", "by"}]。工程師指定的日期優先；之後的事件從它往後推。
    fixed：已經 prepare 過的站的事件日（P52，不再變）。指定的、已產出的日期不能早於前一個確定的日期
    （客戶文件、指定、已產出；issue #32）；夾在中間的推算日期晚於後面的確定日期時往前調，保持順序。"""
    overrides, fixed = overrides or {}, fixed or {}
    for event, date in overrides.items():
        if is_weekend(date):
            raise NpiError(f"{event} 指定的 {date} 是週六或週日，請換一個工作天")
    out, dates, settled = [], {}, None
    for event, prev, n, basis in _steps(kind, days, minor):
        if event in overrides or event in fixed:
            date, by, why = (overrides[event], ENGINEER, "工程師指定") if event in overrides else \
                            (fixed[event], FIXED, "這站已經產出，日期不變（P52）")  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
            if settled and date < settled[1]:
                raise NpiError(f"{event} 的 {date} 早於前一個確定的事件 {settled[0]}（{settled[1]}），請換一個日期")
        elif prev is None:
            date, by, why = received, CUSTOMER, basis
        elif event == "收到 PO" and po_date:
            date, by, why = po_date, CUSTOMER, "客戶 PO 上的日期（P50）"
        else:
            date, by, why = add_workdays(dates[prev], n), ESTIMATED, f"{prev} + {n} 個工作天；{basis}"
        if by != ESTIMATED:
            settled = (event, date)
        dates[event] = date
        out.append({"event": event, "date": date, "basis": why, "by": by})
    for i in range(len(out) - 2, -1, -1):          # 推算的日期不能晚於後一個事件
        e, nxt = out[i], out[i + 1]
        if e["by"] == ESTIMATED and e["date"] > nxt["date"]:
            e["date"] = nxt["date"]
            e["basis"] += f"（後面的 {nxt['event']} 在 {nxt['date']}，往前調到同一天）"  # 程式內文字：推算依據，描述程式套用哪條規則，跟分支邏輯一起維護
    return out


def station_event(station, rev):
    """每站文件的日期取哪個事件（表 F 最後一欄）。"""
    if station == "dfm":
        return "DFM 回覆日" if rev == "A0" else "影響評估日"
    return {"release": "規格發行日", "cost": "成本送財務日", "po": "收到 PO", "supply": "備料通知日"}[station]

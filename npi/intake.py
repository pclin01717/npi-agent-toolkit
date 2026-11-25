"""PLANS 表 A（認文件）、表 B（排程）。純函式。"""
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import NpiError

REVS = ["A0", "B0", "C0", "C1"]
CASE_RE = re.compile(r"^(NPI-\d{2}-\d{3})_")
KIND_NAMES = {"draft_spec": "客戶草稿 spec", "ecr": "ECR", "po": "客戶 PO"}
NOT_IN_CASE = "不在案子的版次資料夾裡（input/<NPI-xx-xxx_名稱>/<A0／B0／C0／C1>/）"


@dataclass(frozen=True)
class Doc:
    path: Path
    case_dir: str
    npi_no: str
    rev: str
    kind: str            # draft_spec / ecr / po
    has_po_folder: bool

    @property
    def previous_rev(self):
        i = REVS.index(self.rev)
        return REVS[i - 1] if i > 0 else None


def identify(path, input_root) -> Doc:
    path = Path(path).resolve()
    try:
        parts = path.relative_to(Path(input_root).resolve()).parts
    except ValueError:
        raise NpiError(f"{path.name}：{NOT_IN_CASE}") from None
    m = CASE_RE.match(parts[0]) if parts else None
    if len(parts) < 3 or not m or parts[1] not in REVS:
        raise NpiError(f"{path.name}：{NOT_IN_CASE}")
    rev = parts[1]
    folder = parts[2] if len(parts) >= 4 else ""
    suffix = path.suffix.lower()
    if folder == "01_Customer_Draft_Spec" and suffix == ".docx" and rev == "A0":
        kind = "draft_spec"
    elif folder == "01_Customer_ECR" and suffix == ".docx" and rev != "A0":
        kind = "ecr"
    elif folder == "05_Customer_PO" and suffix == ".pdf":
        kind = "po"
    else:
        raise NpiError(f"{path.name}：這是我方文件或答案檔，不是客戶文件（客戶文件在 01_Customer_* 或 05_Customer_PO）")
    rev_dir = Path(input_root).resolve() / parts[0] / rev
    return Doc(path, parts[0], m.group(1), rev, kind, (rev_dir / "05_Customer_PO").is_dir())


def schedule(doc: Doc) -> list:
    if doc.kind == "po":
        return ["po", "supply"]
    if doc.kind == "ecr" and not doc.has_po_folder:
        return ["dfm", "release", "cost", "supply"]
    return ["dfm", "release", "cost"]

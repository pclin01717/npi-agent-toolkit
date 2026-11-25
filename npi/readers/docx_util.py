"""docx 共用：依文件順序走過段落和表格，表格儲存格去掉合併造成的重複。"""
from docx.table import Table
from docx.text.paragraph import Paragraph


def blocks(document):
    """依序回傳 ("p", Paragraph) 或 ("t", Table)。"""
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            yield "p", Paragraph(child, document)
        elif tag == "tbl":
            yield "t", Table(child, document)


def row_cells(row):
    """一列的儲存格文字；合併儲存格只留一次。"""
    out, seen = [], set()
    for cell in row.cells:
        if id(cell._tc) in seen:
            continue
        seen.add(id(cell._tc))
        out.append(cell.text.strip())
    return out


def table_rows(table):
    return [row_cells(r) for r in table.rows]


def label_values(table):
    """「欄名 | 值 | 欄名 | 值」排法的表 → {欄名: 值}。"""
    return label_values_rows(table_rows(table))


def label_values_rows(rows):
    out = {}
    for cells in rows:
        for i in range(0, len(cells) - 1, 2):
            if cells[i]:
                out[cells[i]] = cells[i + 1]
    return out


def pick(values, aliases):
    for a in aliases:
        if values.get(a):
            return values[a]
    return None

"""正式 spec：填 templates/product_spec.docx。"""
import datetime

import docx

from . import TEMPLATES
from ..params import TYPES

HEADER = {"Doc. No.": "doc_no", "Revision": "rev", "Date": "date", "LPC P/N": "lpc_pn",
          "Customer P/N": "cust_pn", "NPI No.": "npi_no", "Description": "description"}


def write_spec_doc(path, header, params, sections, spec=TYPES["Fiber_Array"]):
    d = docx.Document(TEMPLATES / "product_spec.docx")
    head_table, param_table = d.tables[0], d.tables[1]
    for row in head_table.rows:
        key = HEADER.get(row.cells[0].text.strip())
        if key:
            row.cells[1].text = str(header.get(key) or "")
    for label, keys in spec["rows"]:
        cells = param_table.add_row().cells
        cells[0].text, cells[1].text = label, spec["row_text"](keys, params)
    for s in sections:
        d.add_heading(s["title"], level=2)
        d.add_paragraph(s["text"])
    day = datetime.datetime.fromisoformat(header["date"])
    d.core_properties.created = d.core_properties.modified = day
    d.core_properties.title = f"{header['doc_no']} Rev {header['rev']}"
    d.save(path)
    return path

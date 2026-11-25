"""指令入口：python -m npi <指令>。總管（/npi）照這些指令一步一步做。"""
import argparse
import sys
from pathlib import Path

from . import pipeline
from .compare import compare
from . import stations  # noqa: F401  登記各站
from .errors import NpiError
from .intake import KIND_NAMES
from .pending import pending_items

PROJECT = Path(__file__).resolve().parents[1]


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m npi")
    p.add_argument("--input-root", default=str(PROJECT / "input"))
    p.add_argument("--out-root", default=str(PROJECT / "output"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("intake").add_argument("file")
    sub.add_parser("status").add_argument("npi_no")
    for name in ("prepare", "render", "approve", "reopen"):
        sp = sub.add_parser(name)
        sp.add_argument("npi_no")
        sp.add_argument("rev")
        sp.add_argument("station")
        if name == "prepare":
            sp.add_argument("--date")
    sp = sub.add_parser("compare")
    sp.add_argument("npi_no")
    sp.add_argument("rev")
    sp = sub.add_parser("decide")
    sp.add_argument("npi_no")
    sp.add_argument("rev")
    sp.add_argument("text")
    sp = sub.add_parser("timeline")
    sp.add_argument("npi_no")
    sp.add_argument("rev")
    sp = sub.add_parser("tell")
    for arg in ("npi_no", "rev", "station", "text"):
        sp.add_argument(arg)
    a = p.parse_args(argv)
    ins, outs = Path(a.input_root), Path(a.out_root)
    try:
        if a.cmd == "intake":
            s = pipeline.intake(a.file, ins, outs)
            print(f"{s['npi_no']}／{s['rev']}／{KIND_NAMES[s['kind']]}（上一版：{s['previous_rev'] or '無'}）")
            print(pipeline.format_status(pipeline.load_state(s["npi_no"], outs)))
        elif a.cmd == "status":
            print(pipeline.format_status(pipeline.load_state(a.npi_no, outs)))
        elif a.cmd == "prepare":
            print(pipeline.prepare(a.npi_no, a.rev, a.station, ins, outs, a.date))
        elif a.cmd == "render":
            files = pipeline.render(a.npi_no, a.rev, a.station, ins, outs)
            for f in files:
                print(f)
            items = pending_items(files)
            print(f"待工程師填寫：{len(items)} 處")
            for i in items:
                print(f"- {i['file']} {i['where']}")
        elif a.cmd == "approve":
            print(pipeline.approve(a.npi_no, a.rev, a.station, ins, outs))
        elif a.cmd == "reopen":
            pipeline.reopen(a.npi_no, a.rev, a.station, outs)
            print(pipeline.format_status(pipeline.load_state(a.npi_no, outs)))
        elif a.cmd == "compare":
            diffs = compare(outs, ins, a.npi_no, a.rev)
            print(f"{a.npi_no} {a.rev} 跟答案檔的差異：{len(diffs)} 項（只列出，不算失敗）")
            for d in diffs:
                print(f"- {d}")
        elif a.cmd == "decide":
            print(pipeline.decide(a.npi_no, a.rev, a.text, outs))
        elif a.cmd == "timeline":
            for e in pipeline.timeline(a.npi_no, a.rev, ins, outs):
                print(f"{e['date']}　{e['event']}（{e['by']}）：{e['basis']}")
        elif a.cmd == "tell":
            print(pipeline.tell(a.npi_no, a.rev, a.station, a.text, outs))
    except NpiError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

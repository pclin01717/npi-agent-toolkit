"""簡化 STEP：基座 = 基板＋蓋板；組件 = 基座＋boot。fan-out：分支盒；組件 = 分支盒＋主幹＋支線（PLANS P42）。
尺寸全部來自關鍵參數。"""
import math
import re
from pathlib import Path

import cadquery as cq

_STAMP = re.compile(r"'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'")


def _block(v):
    sub = cq.Workplane("XY").box(v["substrate_w_mm"], v["substrate_l_mm"], v["substrate_t_mm"], centered=(True, False, False))
    lid = (cq.Workplane("XY").workplane(offset=v["substrate_t_mm"])
           .box(v["lid_w_mm"], v["lid_l_mm"], v["lid_t_mm"], centered=(True, False, False)))
    return sub.union(lid)


def _assembly(v):
    boot = (cq.Workplane("XY").workplane(offset=(v["substrate_t_mm"] - v["boot_h_mm"]) / 2)
            .center(0, v["substrate_l_mm"])
            .box(v["boot_w_mm"], v["boot_l_mm"], v["boot_h_mm"], centered=(True, False, False)))
    return _block(v).union(boot)


def _export(shape, path, date):
    cq.exporters.export(shape, str(path), "STEP")
    text = Path(path).read_text(encoding="utf-8")
    Path(path).write_text(_STAMP.sub(f"'{date}T00:00:00'", text, count=1), encoding="utf-8")
    return Path(path)


def write_steps(block_path, assembly_path, v, date):
    return [_export(_block(v), block_path, date), _export(_assembly(v), assembly_path, date)]


def _fanout_box(v):
    return cq.Workplane("XY").box(v["box_w_mm"], v["box_l_mm"], v["box_h_mm"], centered=(True, False, False))


def _fanout_assembly(v):
    w, h = v["box_w_mm"], v["box_h_mm"]
    trunk = cq.Workplane("XZ").center(0, h / 2).circle(v["trunk_od_mm"] / 2).extrude(v["trunk_m"] * 1000)
    n, od = int(v["leg_conn_qty"]), v["leg_od_mm"]
    step = od * 1.25                                   # 支線排成格狀，彼此留空隙（簡化，不求真實排列）
    cols = max(1, int(w // step))
    rows = math.ceil(n / cols)
    pts = [((i % cols - (cols - 1) / 2) * step, h / 2 + (i // cols - (rows - 1) / 2) * step) for i in range(n)]
    legs = (cq.Workplane("XZ", origin=(0, v["box_l_mm"], 0)).pushPoints(pts)
            .circle(od / 2).extrude(-v["leg_mm"]))
    return _fanout_box(v).union(trunk).union(legs)


def write_fanout_steps(box_path, assembly_path, v, date):
    return [_export(_fanout_box(v), box_path, date), _export(_fanout_assembly(v), assembly_path, date)]

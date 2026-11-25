"""簡化圖面 PDF（A3 橫式）：正視、側視外形、主要尺寸、通道表、標題欄。尺寸全部來自關鍵參數。
fan-out：主幹、分支盒、支線的示意圖（不照比例）、port map、標題欄（PLANS P41）。"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from ..params import description, fmt, fo_description, metres, port_map, tol_text  # noqa: E402

plt.rcParams["pdf.fonttype"] = 42


def _box(ax, x, y, w, h, label):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=1.2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7)


def write_drawing(path, header, v):
    fig = plt.figure(figsize=(16.54, 11.69))  # A3 橫式（英吋）
    sub_w, sub_l, sub_t = v["substrate_w_mm"], v["substrate_l_mm"], v["substrate_t_mm"]
    lid_w, lid_l, lid_t = v["lid_w_mm"], v["lid_l_mm"], v["lid_t_mm"]
    boot_w, boot_l = v["boot_w_mm"], v["boot_l_mm"]

    top = fig.add_axes([0.05, 0.45, 0.5, 0.45])
    top.set_title("FRONT VIEW (TOP)", fontsize=10)
    _box(top, -sub_w / 2, 0, sub_w, sub_l, "SUBSTRATE")
    _box(top, -lid_w / 2, 0, lid_w, lid_l, "LID")
    _box(top, -boot_w / 2, sub_l, boot_w, boot_l, "BOOT")
    top.annotate(f"{fmt(sub_w)}", (0, -0.8), ha="center", fontsize=8)
    top.annotate(f"{fmt(sub_l)}", (sub_w / 2 + 0.6, sub_l / 2), fontsize=8)
    top.annotate(f"PIGTAIL {fmt(v['pigtail_mm'])} ± {fmt(v['pigtail_tol_mm'])} mm TO CONNECTORS",
                 (0, sub_l + boot_l + 1.5), ha="center", fontsize=8)
    top.set_xlim(-boot_w, boot_w)
    top.set_ylim(-2, sub_l + boot_l + 3)
    top.set_aspect("equal")
    top.axis("off")

    side = fig.add_axes([0.05, 0.15, 0.5, 0.25])
    side.set_title("SIDE VIEW", fontsize=10)
    _box(side, 0, 0, sub_l, sub_t, "SUBSTRATE")
    _box(side, 0, sub_t, lid_l, lid_t, "LID")
    side.annotate(f"{fmt(sub_t)} + {fmt(lid_t)}", (sub_l + 0.4, (sub_t + lid_t) / 2), fontsize=8)
    side.annotate(f"END FACE {fmt(v['end_face_angle_deg'])}°", (-0.2, -0.6), fontsize=8)
    side.set_xlim(-1, sub_l + 3)
    side.set_ylim(-1, sub_t + lid_t + 1)
    side.set_aspect("equal")
    side.axis("off")

    n, pitch = int(v["channels"]), v["pitch_um"]
    table = fig.add_axes([0.62, 0.15, 0.33, 0.75])
    table.axis("off")
    table.text(0, 1.0, "CHANNEL MAP (POSITION FROM ARRAY CENTRE, mm)", fontsize=8, weight="bold")
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch / 1000
        table.text(0, 0.97 - (i + 1) * 0.9 / n, f"CH {i + 1}    {x:+.4f}", fontsize=6.5, family="monospace")

    return _finish(fig, path, header, description(v))


def _finish(fig, path, header, desc):
    block = fig.add_axes([0.05, 0.02, 0.9, 0.09])
    block.axis("off")
    block.add_patch(Rectangle((0, 0), 1, 1, fill=False, transform=block.transAxes))
    block.text(0.01, 0.65, f"{header['doc_no']}    REV {header['rev']}    DATE {header['date']}", fontsize=10)
    block.text(0.01, 0.3, f"{header['lpc_pn']}  -  {desc}", fontsize=9)
    block.text(0.01, 0.05, "Lumora Photonics Co., Ltd.  -  simplified outline, dimensions in mm", fontsize=7)
    fig.savefig(path, format="pdf", metadata={"CreationDate": None, "Creator": None, "Producer": None})
    plt.close(fig)
    return path


def write_fanout_drawing(path, header, v):
    fig = plt.figure(figsize=(16.54, 11.69))  # A3 橫式（英吋）
    ax = fig.add_axes([0.05, 0.2, 0.55, 0.7])
    ax.set_title("FAN-OUT OUTLINE (NOT TO SCALE)", fontsize=10)
    n_mpo, n_leg = int(v["trunk_conn_qty"]), int(v["leg_conn_qty"])
    for i in range(n_mpo):                                         # 主幹端的 MPO
        _box(ax, 0, 46 + (i - (n_mpo - 1) / 2) * 5, 6, 3, "")
    ax.text(3, 46 + (n_mpo + 1) / 2 * 5, f"{n_mpo} x {v['trunk_connector']}", ha="center", fontsize=7)
    ax.plot([6, 40], [47.5, 47.5], lw=3, color="black")
    ax.text(23, 51, "TRUNK", ha="center", fontsize=9, weight="bold")
    ax.text(23, 43, f"{metres(v['trunk_m'])} m {tol_text(v['trunk_tol_plus_mm'], v['trunk_tol_minus_mm'])} mm",
            ha="center", fontsize=8)
    ax.text(23, 40, f"OD {fmt(v['trunk_od_mm'])} mm", ha="center", fontsize=7)
    _box(ax, 40, 41, 14, 13, "FAN-OUT BOX")
    ax.text(47, 38, f"{fmt(v['box_l_mm'])} x {fmt(v['box_w_mm'])} x {fmt(v['box_h_mm'])} mm (L x W x H)",
            ha="center", fontsize=7)
    shown = min(n_leg, 12)                                         # 示意：最多畫 12 條
    for i in range(shown):
        y = 47.5 + (i - (shown - 1) / 2) * 3.5
        ax.plot([54, 62, 88], [47.5, y, y], lw=0.8, color="black")
        ax.add_patch(Rectangle((88, y - 0.8), 4, 1.6, fill=False, lw=0.8))
    top = 47.5 + (shown - 1) / 2 * 3.5
    ax.text(75, top + 4, f"LEGS  {n_leg} x {v['leg_connector']}", ha="center", fontsize=9, weight="bold")
    ax.text(75, 47.5 - (shown - 1) / 2 * 3.5 - 4,
            f"{fmt(v['leg_mm'])} {tol_text(v['leg_tol_plus_mm'], v['leg_tol_minus_mm'])} mm,  OD {fmt(v['leg_od_mm'])} mm"
            f",  END FACE {v['end_face']}", ha="center", fontsize=8)
    ax.set_xlim(-2, 95)
    ax.set_ylim(15, 80)
    ax.axis("off")

    rows = port_map(v)
    table = fig.add_axes([0.66, 0.15, 0.3, 0.75])
    table.axis("off")
    table.text(0, 1.0, f"PORT MAP ({v['polarity']})", fontsize=8, weight="bold")
    for k, (fibre, mpo, pos, leg) in enumerate(rows):
        table.text(0, 0.97 - (k + 1) * 0.9 / len(rows), f"F{fibre:02d}    MPO {mpo} / {pos:02d}    LEG {leg:02d}",
                   fontsize=6.5, family="monospace")
    return _finish(fig, path, header, fo_description(v))

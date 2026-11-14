#!/usr/bin/env python3
"""Generate original SVG diagrams for the DeepInfer / V4.1-Flash inference article.

The SVGs are rendered to 2x PNG with headless Chrome by render_deepinfer_figs.sh.
All figures are hand-laid-out; no external assets are used.
"""
import html
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "images",
                   "2026-11-14-deepinfer-inference-system")
os.makedirs(OUT, exist_ok=True)

INK = "#14171F"
MUTED = "#5B6472"
SOFT = "#8A94A6"
LINE = "#DCE3EC"
CARD = "#F7F9FC"
BLUE = "#3D5AFE"
BLUE_DARK = "#1E3A8A"
BLUE_BG = "#EEF2FF"
TEAL = "#0E9F6E"
TEAL_DARK = "#065F46"
TEAL_BG = "#E8F7F1"
AMBER = "#D97706"
AMBER_BG = "#FFF7E6"
PURPLE = "#7C3AED"
PURPLE_BG = "#F3EEFF"
RED = "#DC2626"
RED_BG = "#FEF2F2"

FONT = "'PingFang SC','Microsoft YaHei','Helvetica Neue',Arial,sans-serif"

MARKERS = {
    "blue": BLUE, "ink": INK, "teal": TEAL, "amber": AMBER,
    "purple": PURPLE, "red": RED, "soft": SOFT,
}


def esc(s):
    return html.escape(str(s), quote=False)


def text(x, y, s, size=18, fill=INK, weight=400, anchor="start", opacity=1.0,
         spacing=None, style=None):
    extra = ""
    if spacing is not None:
        extra += f' letter-spacing="{spacing}"'
    if style:
        extra += f' style="{style}"'
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}"{extra}>'
            f'{esc(s)}</text>')


def rich(x, y, parts, size=18, anchor="start"):
    """parts: list of (text, color, weight) tuples, rendered as tspans."""
    out = [f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">']
    for s, color, weight in parts:
        out.append(f'<tspan fill="{color}" font-weight="{weight}">{esc(s)}</tspan>')
    out.append("</text>")
    return "".join(out)


def rect(x, y, w, h, fill=CARD, stroke=LINE, rx=12, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def line(x1, y1, x2, y2, color=LINE, sw=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{sw}"{d}/>')


def poly(points, color=BLUE, sw=2.5, dash=None):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linejoin="round"{d}/>')


def arrow(x1, y1, x2, y2, color="blue", sw=2.5, dash=None):
    c = MARKERS[color]
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" '
            f'stroke-width="{sw}" marker-end="url(#ar-{color})"{d}/>')


def circle(cx, cy, r, fill, stroke="none", sw=0):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def pill(x, y, w, h, label, color=BLUE, bg=BLUE_BG, size=15, weight=700):
    return rect(x, y, w, h, bg, color, h / 2, 1.2) + \
        text(x + w / 2, y + h / 2 + size * 0.36, label, size, color, weight, "middle")


def badge(x, y, label, color=BLUE, bg=BLUE_BG, size=13):
    w = max(54, len(label) * size * 0.72 + 22)
    return pill(x, y, w, 26, label, color, bg, size) + (w,)


def fig_open(w, h, bg="#FFFFFF"):
    defs = ['<defs>']
    for name, color in MARKERS.items():
        defs.append(
            f'<marker id="ar-{name}" viewBox="0 0 10 10" refX="8.5" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 Z" fill="{color}"/></marker>')
    defs.append("</defs>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="{FONT}">'
            f'{"".join(defs)}<rect width="{w}" height="{h}" fill="{bg}"/>')


def fig_title(title, subtitle=None, w=1200):
    s = text(56, 50, title, 30, INK, 800)
    if subtitle:
        s += text(56, 82, subtitle, 17, MUTED, 400)
    s += line(56, 100, w - 56, 100, LINE, 1.5)
    return s


def footer(w, h, note="tanjunchen · AI Infra  |  配图为作者自绘，仅用于原理示意"):
    return text(w - 40, h - 18, note, 12, SOFT, 400, "end")


# ---------------------------------------------------------------------------
# 00 cover
# ---------------------------------------------------------------------------
def fig_cover():
    w, h = 1200, 630
    s = fig_open(w, h, "#FBFCFF")
    # decorative
    s += circle(1080, 90, 190, "#EEF2FF")
    s += circle(1140, 560, 240, "#F3EEFF")
    s += circle(660, 620, 150, "#E8F7F1")
    s += "<g opacity='0.55'>"
    for i in range(6):
        s += line(700 + i * 80, 0, 620 + i * 80, 630, "#E6ECF8", 1)
    s += "</g>"

    s += pill(56, 56, 190, 36, "AI INFRA · 深度拆解", BLUE, "#FFFFFF", 14)
    s += text(56, 168, "155 万亿 Tokens/天", 58, INK, 800)
    s += text(56, 238, "是怎么跑出来的？", 58, INK, 800)
    s += text(58, 296, "拆解 DeepSeek V4.1 Flash 推理系统", 28, BLUE, 700)
    s += text(58, 342, "从 EPD 分离、Wide-EP、72 小时 KVCache", 19, MUTED)
    s += text(58, 370, "到「按时间切分」的 Prefill 调度", 19, MUTED)
    s += text(58, 398, "一篇写给工程师的实现原理笔记", 19, MUTED)

    # metric chips
    metrics = [("155T", "tokens / day"), ("$38", "每卡每小时"), ("72h+", "KVCache 保留")]
    x = 58
    for big, small in metrics:
        s += rect(x, 440, 176, 74, "#FFFFFF", LINE, 14, 1.5)
        s += text(x + 18, 478, big, 27, INK, 800)
        s += text(x + 18, 501, small, 13, MUTED)
        x += 190

    s += text(58, 574, "tanjunchen  ·  2026.11", 15, MUTED, 600)
    s += text(58, 598, "所有数字均标注口径；第三方推算与官方披露分开表述", 12, SOFT)

    # right: pipeline illustration
    bx, by, bw = 706, 92, 438
    s += rect(bx, by, bw, 446, "#FFFFFF", "#E3E9F5", 22, 1.5)
    s += text(bx + 24, by + 34, "SYSTEM AT A GLANCE", 13, SOFT, 700, spacing=2)

    # prefill
    s += rect(bx + 24, by + 56, bw - 48, 92, BLUE_BG, "#C7D2FE", 14, 1.5)
    s += text(bx + 42, by + 86, "PREFILL", 12, BLUE, 800, spacing=1.5)
    s += text(bx + 42, by + 114, "常见 8 卡机 · EP2~8", 20, INK, 700)
    for i in range(8):
        s += rect(bx + 292 + (i % 4) * 26, by + 72 + (i // 4) * 26, 18, 18,
                  "#FFFFFF", BLUE, 4, 1.2)
    # arrow
    s += arrow(bx + bw / 2, by + 150, bx + bw / 2, by + 178, "blue", 2.5)
    s += text(bx + bw / 2 + 12, by + 170, "KV 读写", 12, BLUE, 600)

    # 3fs
    s += rect(bx + 24, by + 180, bw - 48, 92, TEAL_BG, "#A7E3CB", 14, 1.5)
    s += text(bx + 42, by + 210, "KVCACHE / 3FS", 12, TEAL, 800, spacing=1.5)
    s += text(bx + 42, by + 238, "100 PiB · 10 TiB/s 读", 20, INK, 700)
    # cylinder
    cy = by + 216
    s += f'<ellipse cx="{bx + 354}" cy="{cy}" rx="30" ry="11" fill="#FFFFFF" stroke="{TEAL}" stroke-width="1.5"/>'
    s += f'<path d="M{bx + 324},{cy} v34 a30,11 0 0 0 60,0 v-34" fill="#FFFFFF" stroke="{TEAL}" stroke-width="1.5"/>'
    s += f'<ellipse cx="{bx + 354}" cy="{cy + 34}" rx="30" ry="11" fill="none" stroke="{TEAL}" stroke-width="1.5" opacity="0.5"/>'

    s += arrow(bx + bw / 2, by + 274, bx + bw / 2, by + 302, "teal", 2.5)
    s += text(bx + bw / 2 + 12, by + 294, "400G / GDR", 12, TEAL, 600)

    # decode
    s += rect(bx + 24, by + 304, bw - 48, 112, PURPLE_BG, "#DDD6FE", 14, 1.5)
    s += text(bx + 42, by + 334, "DECODE", 12, PURPLE, 800, spacing=1.5)
    s += text(bx + 42, by + 362, "64~128 卡超节点", 20, INK, 700)
    s += text(bx + 42, by + 390, "EP64~128 · Wide-EP", 14, MUTED)
    # 8x8 grid
    for r in range(8):
        for c in range(8):
            s += rect(bx + 282 + c * 18, by + 322 + r * 11, 13, 8,
                      "#FFFFFF", PURPLE, 2, 0.8)
    s += text(bx + 24, by + 438, "P : D ≈ 1 : 1   ·   最小高效单元 64P + 64D", 13, MUTED, 600)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 01 overview
# ---------------------------------------------------------------------------
def fig_overview():
    w, h = 1200, 700
    s = fig_open(w, h)
    s += fig_title("一页看懂 V4.1 Flash 推理系统：E/P/D 分离 + 独立 KVCache 存储",
                   "请求从 Entrypoint 进入，Vision Encoder / Prefill / Decode 各自独立扩缩容；所有 Prefill 共享同一份 3FS 前缀缓存")

    # goal chips
    goals = [("多厂商芯片", "NVIDIA / 昇腾，同一套框架", BLUE, BLUE_BG),
             ("阶段解耦", "8 卡 Prefill / 64~128 卡 Decode", PURPLE, PURPLE_BG),
             ("超长缓存", "KVCache 保留 72 小时以上", TEAL, TEAL_BG)]
    x = 56
    for title, sub, color, bg in goals:
        s += rect(x, 120, 352, 64, bg, color, 12, 1.2)
        s += text(x + 18, 146, title, 17, color, 800)
        s += text(x + 18, 169, sub, 13, MUTED)
        x += 368

    # entrypoint
    s += rect(56, 220, 150, 72, "#FFFFFF", LINE, 12, 1.5)
    s += text(131, 250, "Entrypoint", 17, INK, 700, "middle")
    s += text(131, 273, "鉴权 / 路由 / 前缀匹配", 11, MUTED, 400, "middle")

    # VE
    s += rect(56, 330, 150, 96, AMBER_BG, "#F5D0A9", 12, 1.5)
    s += text(131, 360, "Vision Encoder", 15, AMBER, 800, "middle")
    s += text(131, 384, "单卡部署", 13, MUTED, 400, "middle")
    s += text(131, 406, "按 patch 数选卡", 12, MUTED, 400, "middle")

    # P pool
    s += rect(250, 210, 310, 236, BLUE_BG, "#C7D2FE", 16, 1.5)
    s += text(270, 242, "PREFILL POOL", 13, BLUE, 800, spacing=1.5)
    s += text(270, 268, "常见 8 卡机 · EP2~8 / DP2~8", 15, INK, 700)
    for r in range(2):
        for c in range(4):
            s += rect(270 + c * 68, 288 + r * 58, 56, 44, "#FFFFFF", BLUE, 8, 1.2)
            s += text(298 + c * 68, 315 + r * 58, "GPU", 11, BLUE, 700, "middle")
    s += text(270, 420, "小 EP：喂饱矩阵乘，少通信", 12, BLUE, 600)

    # 3FS
    s += rect(596, 210, 250, 236, TEAL_BG, "#A7E3CB", 16, 1.5)
    s += text(616, 242, "KVCACHE STORE / 3FS", 13, TEAL, 800, spacing=1.2)
    s += text(616, 270, "Block KV · 100 PiB", 16, INK, 700)
    s += text(616, 294, "10 TiB/s 读 · 850 GiB/s 写", 12, MUTED)
    # cylinder
    s += f'<ellipse cx="721" cy="334" rx="58" ry="18" fill="#FFFFFF" stroke="{TEAL}" stroke-width="1.8"/>'
    s += f'<path d="M663,334 v56 a58,18 0 0 0 116,0 v-56" fill="#FFFFFF" stroke="{TEAL}" stroke-width="1.8"/>'
    s += f'<ellipse cx="721" cy="390" rx="58" ry="18" fill="none" stroke="{TEAL}" stroke-width="1.8" opacity="0.45"/>'
    s += text(721, 430, "任意 P 命中任意前缀", 12, TEAL, 700, "middle")

    # D pool
    s += rect(882, 190, 262, 276, PURPLE_BG, "#DDD6FE", 16, 1.5)
    s += text(902, 222, "DECODE POOL", 13, PURPLE, 800, spacing=1.5)
    s += text(902, 248, "64~128 卡超节点", 15, INK, 700)
    s += text(902, 270, "EP64~128 / DP64~128", 12, MUTED)
    for r in range(6):
        for c in range(6):
            s += rect(902 + c * 38, 286 + r * 26, 30, 18, "#FFFFFF", PURPLE, 4, 1)
    s += text(902, 452, "Wide-EP：摊薄每步专家权重", 12, PURPLE, 700)

    # arrows
    s += arrow(206, 256, 248, 256, "ink", 2)
    s += arrow(206, 378, 248, 330, "amber", 2)
    s += arrow(560, 300, 594, 300, "blue", 2.4)
    s += text(577, 288, "写", 11, BLUE, 700, "middle")
    s += arrow(594, 360, 560, 360, "teal", 2.4)
    s += text(577, 348, "读", 11, TEAL, 700, "middle")
    s += arrow(846, 300, 880, 300, "teal", 2.4)
    s += text(863, 288, "KV", 11, TEAL, 700, "middle")
    s += arrow(882, 380, 846, 380, "purple", 2.4)
    s += text(864, 368, "写回", 10, PURPLE, 700, "middle")

    # LB bar
    s += rect(56, 492, 1088, 70, "#FFFFFF", LINE, 12, 1.5)
    s += text(76, 518, "LOAD BALANCING", 12, SOFT, 800, spacing=1.5)
    lbs = [("Prefill LB", BLUE, BLUE_BG), ("Decode LB", PURPLE, PURPLE_BG),
           ("VE LB", AMBER, AMBER_BG), ("EPLB", TEAL, TEAL_BG)]
    x = 76
    for label, color, bg in lbs:
        ww = 120 if label != "EPLB" else 90
        s += pill(x, 528, ww, 24, label, color, bg, 12)
        x += ww + 12
    s += text(620, 536, "四层均衡：跨 tier / 跨 DP 组 / 组内 / 单卡内；在线效率 ≈ 离线完全均衡的 80%", 13, MUTED)
    s += text(620, 556, "原则：不做前缀亲和路由 —— 因为任意 P 都能命中任意前缀", 12, SOFT)

    # bottom metrics
    s += rect(56, 586, 1088, 72, "#F7F9FC", "#E6EBF3", 12, 1)
    metrics = [("155 万亿", "tokens / day（单集群）"), ("$38", "每卡每小时（谷价）"),
               ("≈ 7300", "卡（第三方反推）"), ("P : D ≈ 1 : 1", "卡数配比")]
    x = 82
    for big, small in metrics:
        s += text(x, 618, big, 22, INK, 800)
        s += text(x, 640, small, 11, MUTED)
        x += 268
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 02 roofline
# ---------------------------------------------------------------------------
def fig_roofline():
    w, h = 1200, 640
    s = fig_open(w, h)
    s += fig_title("Prefill 计算密集、Decode 访存密集：一条 roofline，解释两种相反的 EP 策略",
                   "横轴是算术强度（每读 1 字节做多少次运算），纵轴是可达性能；两个阶段的落点根本不在同一个位置")

    # roofline chart
    cx0, cy0, cx1, cy1 = 86, 150, 650, 520
    s += rect(cx0, cy0, cx1 - cx0, cy1 - cy0, "#FFFFFF", LINE, 10, 1)
    # grid
    for i in range(1, 5):
        y = cy0 + i * (cy1 - cy0) / 5
        s += line(cx0, y, cx1, y, "#EEF1F6", 1)
    for i in range(1, 5):
        x = cx0 + i * (cx1 - cx0) / 5
        s += line(x, cy0, x, cy1, "#EEF1F6", 1)
    # axes labels
    s += text((cx0 + cx1) / 2, cy1 + 28, "算术强度  AI = FLOPs / Byte  →", 13, MUTED, 600, "middle")
    s += f'<text x="{cx0 - 14}" y="{(cy0 + cy1) / 2}" font-size="13" fill="{MUTED}" text-anchor="middle" transform="rotate(-90 {cx0 - 14} {(cy0 + cy1) / 2})">可达性能 →</text>'
    # roofs
    s += f'<path d="M{cx0 + 18},{cy1 - 24} L{cx0 + 330},{cy0 + 58} L{cx1 - 18},{cy0 + 58}" fill="none" stroke="{BLUE}" stroke-width="3"/>'
    s += line(cx0 + 330, cy0 + 58, cx1 - 18, cy0 + 58, "#93A5FF", 2, "5 5")
    s += text(cx0 + 120, cy0 + 38, "算力屋顶（Compute roof）", 11, BLUE, 700)
    s += text(cx0 + 130, cy0 + 120, "带宽屋顶", 12, TEAL, 700)
    s += text(cx0 + 130, cy0 + 138, "AI × BW", 11, TEAL)
    # points
    # prefill: high AI, on compute roof
    px, py = cx0 + 440, cy0 + 58
    s += circle(px, py, 8, PURPLE, "#FFFFFF", 3)
    s += text(px, py - 28, "Prefill", 15, PURPLE, 800, "middle")
    s += text(px, py - 10, "大 batch · 算力 bound", 10, MUTED, 400, "middle")
    # decode: low AI, on bandwidth roof
    dx, dy = cx0 + 175, cy0 + 292
    s += circle(dx, dy, 8, AMBER, "#FFFFFF", 3)
    s += text(dx + 16, dy - 8, "Decode", 15, AMBER, 800)
    s += text(dx + 16, dy + 14, "小 batch · 带宽 bound", 11, MUTED)
    # strategy regions
    s += rect(cx0 + 382, cy0 + 96, 136, 38, BLUE_BG, "#C7D2FE", 8, 1)
    s += text(cx0 + 450, cy0 + 120, "小 EP 更优", 12, BLUE, 800, "middle")
    s += rect(cx0 + 92, cy0 + 318, 150, 42, AMBER_BG, "#F5D0A9", 8, 1)
    s += text(cx0 + 167, cy0 + 344, "大 EP 更优", 12, AMBER, 800, "middle")

    # right panels
    rx = 684
    s += text(rx, 160, "Prefill：权重读一次，服务很多 token", 16, INK, 800)
    s += rect(rx, 176, 460, 150, BLUE_BG, "#C7D2FE", 12, 1.2)
    # tokens
    for r in range(4):
        for c in range(6):
            s += circle(rx + 28 + c * 18, 208 + r * 18, 4, BLUE)
    s += text(rx + 148, 216, "一批很多 token", 11, BLUE, 700)
    s += arrow(rx + 148, 248, rx + 196, 248, "blue", 2)
    # few expert cards
    for i in range(3):
        s += rect(rx + 206 + i * 52, 218, 44, 44, "#FFFFFF", BLUE, 6, 1.2)
        s += text(rx + 228 + i * 52, 245, "E", 12, BLUE, 800, "middle")
    s += text(rx + 206, 300, "每次权重加载被大量 token 摊薄 → 通信成为主要矛盾", 11, MUTED)

    s += text(rx, 372, "Decode：每步只来几个 token，却要读一遍本地专家", 16, INK, 800)
    s += rect(rx, 388, 460, 150, AMBER_BG, "#F5D0A9", 12, 1.2)
    for r in range(2):
        for c in range(2):
            s += circle(rx + 28 + c * 18, 420 + r * 18, 4, AMBER)
    s += text(rx + 66, 428, "每步少量新 token", 11, AMBER, 700)
    s += arrow(rx + 148, 460, rx + 196, 460, "amber", 2)
    for i in range(7):
        s += rect(rx + 206 + i * 34, 438, 28, 44, "#FFFFFF", AMBER, 5, 1.1)
        s += text(rx + 220 + i * 34, 465, "E", 9, AMBER, 800, "middle")
    s += text(rx + 206, 510, "本地专家越多，每步 HBM 读得越多 → Wide-EP 摊薄", 11, MUTED)

    # bottom formula
    s += rect(86, 556, 1028, 48, "#FFFFFF", LINE, 10, 1.2)
    s += rich(106, 586, [("一句话：", BLUE, 800),
                          ("Prefill 的瓶颈是「算」，Decode 的瓶颈是「搬」；EP 大小的选择，本质是在选你要优化哪一边。", INK, 500)], 15)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 03 wide EP
# ---------------------------------------------------------------------------
def fig_wide_ep():
    w, h = 1200, 660
    s = fig_open(w, h)
    s += fig_title("384 个路由专家：EP8 每卡 52 个，EP64 每卡 7 个",
                   "每卡每步要读的专家权重，正比于「本地专家数」；Wide-EP 直接把这一项除以 7.4")

    # EP8 row
    s += text(56, 140, "EP8（Prefill 典型）", 18, BLUE, 800)
    s += text(56, 164, "384 / 8 = 48 个本卡专家 + 4 个冗余 = 52", 13, MUTED)
    for i in range(8):
        x = 56 + i * 110
        s += rect(x, 180, 100, 72, BLUE_BG, "#C7D2FE", 10, 1.2)
        s += text(x + 50, 208, f"卡 {i}", 11, BLUE, 700, "middle")
        s += text(x + 50, 234, "48 + 4", 17, INK, 800, "middle")
    # EP64 row
    s += text(56, 302, "EP64（Decode 典型）", 18, AMBER, 800)
    s += text(56, 326, "384 / 64 = 6 个本卡专家 + 1 个冗余 = 7；8 个代表卡，实际 64 卡一组", 13, MUTED)
    for i in range(8):
        x = 56 + i * 110
        s += rect(x, 342, 100, 72, AMBER_BG, "#F5D0A9", 10, 1.2)
        s += text(x + 50, 370, f"卡 {i * 8}–{i * 8 + 7}", 10, AMBER, 700, "middle")
        s += text(x + 50, 396, "6 + 1", 17, INK, 800, "middle")

    # bar chart (right)
    bx, by = 960, 176
    s += text(bx, 140, "每步专家权重（相对值）", 13, INK, 800)
    bars = [("EP8", 52, BLUE), ("EP64", 7, AMBER), ("EP128", 4, TEAL)]
    maxv = 52
    for i, (label, val, color) in enumerate(bars):
        y = by + i * 54
        s += text(bx, y + 14, label, 11, color, 800)
        bw = 96 * val / maxv
        s += rect(bx + 48, y, bw, 22, color, color, 5, 0)
        s += text(bx + 48 + bw + 7, y + 16, f"{val}", 14, INK, 800)
    s += text(bx, 352, "52 / 7 ≈ 7.4×", 13, RED, 800)
    s += text(bx, 374, "52 / 4 = 13×", 13, RED, 800)
    s += text(bx, 400, "EP128 为公式外推", 10, SOFT)

    # bottom insight
    s += rect(56, 466, 1088, 152, "#FFFFFF", LINE, 12, 1.2)
    s += text(78, 498, "为什么 Decode 特别吃这一项？", 16, INK, 800)
    s += text(78, 528, "Prefill 一步有几千个 token，同一份专家权重被反复复用；Decode 一步每卡只有约 60 并发，", 13, MUTED)
    s += text(78, 552, "每个专家分到的 token 很少，权重却要整块从 HBM 读进来。本地专家数从 52 降到 7，", 13, MUTED)
    s += text(78, 576, "等于把「每步必须搬的权重」砍掉 7.4 倍 —— 这就是 Wide-EP 在 Decode 侧最直接的收益。", 13, MUTED)

    # small formula
    s += rect(880, 484, 244, 116, BLUE_BG, "#C7D2FE", 10, 1.2)
    s += text(900, 512, "本地专家数", 12, BLUE, 800)
    s += text(900, 540, "= 384 / EP + 冗余", 17, INK, 800)
    s += text(900, 566, "冗余：P 4 个 / D 1 个", 11, MUTED)
    s += text(900, 586, "冗余专家用来放热点副本", 10, SOFT)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 04 KVCache hierarchy
# ---------------------------------------------------------------------------
def fig_kvcache():
    w, h = 1200, 720
    s = fig_open(w, h)
    s += fig_title("KVCache 的三层账本：HBM、本机内存、独立 3FS",
                   "热数据在显存，会话窗口在内存，跨请求复用的前缀在 3FS；三层各自解决不同的复用距离")

    # HBM band
    s += rect(56, 126, 760, 150, PURPLE_BG, "#DDD6FE", 14, 1.4)
    s += pill(76, 146, 150, 30, "GPU HBM", PURPLE, "#FFFFFF", 13)
    s += text(76, 204, "运行中的 Block KV + State KV（含 SWA）", 16, INK, 800)
    s += text(76, 230, "容量：单卡显存 · 生命周期：随实例 · 访问：TB/s 级", 12, MUTED)
    s += text(76, 254, "命中即用，换入/落盘由下面的两层兜底", 12, MUTED)


    # host band
    s += rect(56, 300, 760, 150, AMBER_BG, "#F5D0A9", 14, 1.4)
    s += pill(76, 320, 190, 30, "本机内存（P/D 机器）", AMBER, "#FFFFFF", 12)
    s += text(76, 378, "SWA KV：每个序列一个定长 slot（StateBlock）", 16, INK, 800)
    s += text(76, 404, "20 层 × 134 token × 528 B = 1,415,040 B ≈ 1.4 MB / seq", 13, MUTED)
    s += text(76, 428, "单副本，3FS 上没有；TTL ≈ 180 s，命中率 > 98%", 12, MUTED)

    # 3FS band
    s += rect(56, 474, 760, 150, TEAL_BG, "#A7E3CB", 14, 1.4)
    s += pill(76, 494, 170, 30, "独立 3FS 集群", TEAL, "#FFFFFF", 13)
    s += text(76, 552, "Block KV：128-token 分页，4 层 main KV + indexer K", 16, INK, 800)
    s += text(76, 578, "100 PiB · 10 TiB/s 读 · 850 GiB/s 写 · 10+2 EC", 13, MUTED)
    s += text(76, 602, "TTL：agent 3 天 / chatbot 7 天；GC 按 LRU 淘汰", 12, MUTED)

    # arrows
    s += arrow(410, 276, 410, 300, "purple", 2)
    s += arrow(410, 450, 410, 474, "amber", 2)
    s += text(422, 292, "换入 / 落盘", 10, MUTED)
    s += text(422, 466, "GDR / RDMA", 10, MUTED)

    # right: why
    s += rect(840, 126, 304, 498, "#FFFFFF", LINE, 14, 1.4)
    s += text(860, 158, "为什么不用本机多级缓存？", 15, INK, 800)
    reasons = [
        ("任意 P 命中任意前缀", "缓存不绑定在产生它的那台机器上，路由自由。", BLUE),
        ("避免前缀亲和冲突", "不用为了缓存命中把请求钉死在某台 P，负载均衡更好做。", PURPLE),
        ("计算 / 存储解耦", "存储集群独立扩缩容，不被计算节点的规格绑住。", TEAL),
        ("故障域隔离", "计算节点故障率比存储高一个数量级以上，缓存放 3FS 更稳。", AMBER),
    ]
    y = 190
    for title, desc, color in reasons:
        s += circle(868, y + 6, 4, color)
        s += text(882, y + 10, title, 13, color, 800)
        # wrap desc into two short lines manually
        if len(desc) > 22:
            cut = desc.index("，") + 1 if "，" in desc[:24] else 16
            s += text(882, y + 32, desc[:cut], 11, MUTED)
            s += text(882, y + 50, desc[cut:], 11, MUTED)
        else:
            s += text(882, y + 32, desc, 11, MUTED)
        y += 88
    s += line(860, 566, 1124, 566, LINE, 1)
    s += text(860, 592, "结论：用一点网络带宽，换路由自由度", 12, INK, 800)
    s += text(860, 612, "与计算/存储的独立扩缩容。", 12, INK, 800)

    # bottom note
    s += rect(56, 646, 1088, 46, "#F7F9FC", "#E6EBF3", 10, 1)
    s += rich(76, 675, [("口径提醒：", RED, 800),
                        ("SWA 的 528 B/token 是单层口径；20 层合计约 10.5 KB/token，但只保留 134 token 的窗口，所以每序列只有 1.4 MB。", INK, 500)], 13)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 05 3FS + GDR
# ---------------------------------------------------------------------------
def fig_3fs():
    w, h = 1200, 660
    s = fig_open(w, h)
    s += fig_title("3FS + GDR：把「取缓存」变成一次不占 SM 的 DMA",
                   "10+2 纠删码保证可用性，GDR 让 KV 换入与 GPU 前向计算真正并行")

    # left: EC stripe
    s += text(56, 140, "10+2 纠删码：任意 10 个响应即可解码", 16, INK, 800)
    s += text(56, 164, "一个 EC 组 12 块，容忍 2 个存储节点同时故障", 12, MUTED)
    for i in range(12):
        x = 56 + i * 46
        is_parity = i >= 10
        s += rect(x, 186, 40, 62, AMBER_BG if is_parity else TEAL_BG,
                  AMBER if is_parity else TEAL, 8, 1.2)
        s += text(x + 20, 214, "P" if is_parity else "D", 13,
                  AMBER if is_parity else TEAL, 800, "middle")
        s += text(x + 20, 236, f"{i + 1}", 9, MUTED, 400, "middle")
    # decoder box
    s += rect(300, 312, 240, 54, "#FFFFFF", TEAL, 10, 1.4)
    s += text(420, 336, "任意 10 个块 → 解码", 14, TEAL, 800, "middle")
    s += text(420, 354, "恢复完整 KV block", 10, MUTED, 400, "middle")
    for i in (1, 3, 5, 7, 9, 11):
        s += arrow(56 + i * 46 + 20, 250, 420, 310, "teal", 1.1, "3 3")
    # read note
    s += text(56, 388, "读时同时向组内 11 台 Storage 发请求，", 11, MUTED)
    s += text(56, 406, "快者先得，慢节点不拖尾。", 11, MUTED)
    # GC
    s += rect(56, 430, 484, 96, "#FFFFFF", LINE, 10, 1.2)
    s += text(76, 460, "GC Worker", 14, INK, 800)
    s += text(76, 486, "每个 Storage 节点一个实例，按 LRU 周期淘汰最久未访问的", 11, MUTED)
    s += text(76, 506, "KVCache，把磁盘占用压在水位线以下。", 11, MUTED)

    # right: pipeline
    s += text(640, 140, "数据路径：从 3FS 到 HBM，三段各自异步", 16, INK, 800)
    steps = [
        ("① 3FS", "Block KV ~112 KiB 粒度随机读", TEAL, TEAL_BG, "teal"),
        ("② 宿主机 shm", "独立进程异步搬运，不阻塞 engine", BLUE, BLUE_BG, "blue"),
        ("③ HBM", "GDR 逐层 H2D，与前向计算 overlap", PURPLE, PURPLE_BG, "purple"),
    ]
    y = 176
    for i, (title, desc, color, bg, cname) in enumerate(steps):
        s += rect(640, y, 504, 76, bg, color, 12, 1.2)
        s += text(660, y + 30, title, 15, color, 800)
        s += text(660, y + 56, desc, 12, MUTED)
        if i < 2:
            s += arrow(892, y + 76, 892, y + 100, cname, 2)
        y += 100

    # timeline
    s += text(640, 486, "时间线：换入与前向重叠，GPU 不等 KV", 13, INK, 800)
    s += rect(640, 500, 504, 26, "#EEF1F6", "#EEF1F6", 5, 0)
    s += rect(640, 500, 150, 26, TEAL, TEAL, 5, 0)
    s += text(715, 518, "取 KV", 10, "#FFFFFF", 700, "middle")
    s += rect(790, 500, 130, 26, BLUE, BLUE, 5, 0)
    s += text(855, 518, "GDR 换入", 10, "#FFFFFF", 700, "middle")
    s += rect(800, 532, 344, 26, PURPLE, PURPLE, 5, 0)
    s += text(972, 550, "前向计算", 10, "#FFFFFF", 700, "middle")
    s += text(640, 584, "关键点：CUDA copy engine 对 112 KiB 小块拷贝性能不佳；", 11, MUTED)
    s += text(640, 604, "GDR 走 RDMA 网卡直接 DMA，能打满 PCIe，且不占 SM。", 11, MUTED)

    # bottom note
    s += text(56, 628, "跨机房补充：每 8 张卡约需 400 Gbps 互联带宽；P/D 可跨相邻机房部署，代价是光纤故障风险。", 11, SOFT)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 06 bounded replay
# ---------------------------------------------------------------------------
def fig_replay():
    w, h = 1200, 860
    s = fig_open(w, h)
    s += fig_title("SWA Bounded Replay：只回放最后 128 个 token，把重算代价变成常数",
                   "滑动窗口只关心最近 128 个 token；精确重建的误差会沿层传播，每层多 128 token，20 层就是 2560")

    # Panel A: V4 vs V4.1
    s += text(56, 132, "V4 的做法：SWA 也落盘，未命中时精确重算", 15, AMBER, 800)
    s += rect(56, 146, 1088, 34, AMBER_BG, AMBER, 8, 1)
    s += text(76, 168, "SWA KVCache 持久化（曾占持久 KVCache 近一半容量）", 12, AMBER, 700)
    s += text(56, 202, "但 SWA 只在会话内分钟级复用，会话结束即失效 —— 存得多，命中少。", 12, MUTED)

    s += text(56, 242, "V4.1 的做法：SWA 不进 3FS，缺失时只回放最后 128 个 token", 15, BLUE, 800)
    s += rect(56, 256, 1088, 34, "#F7F9FC", LINE, 8, 1)
    s += rect(56, 256, 940, 34, "#E9EDF5", "#C9D2E0", 8, 0)
    s += rect(996, 256, 148, 34, BLUE_BG, BLUE, 8, 1.4)
    s += text(76, 278, "Block KV 仍在 3FS，可跨请求复用", 12, MUTED, 600)
    s += text(1070, 278, "只回放 128", 12, BLUE, 800, "middle")
    s += text(56, 312, "代价与上下文长度、层数无关；SWA 命中率 >98%，未命中才触发。", 12, MUTED)

    # Panel B: error cone
    s += text(56, 356, "为什么精确重建要 2560 个 token？——误差锥", 15, INK, 800)
    top_y = 380
    for i in range(20):
        width = 30 * (20 - i)
        y = top_y + i * 9
        s += rect(76, y, width, 6, "#DCE3F7" if i < 18 else "#C7D2FE",
                  "#B9C6EE", 2, 0.6)
    s += text(76, 372, "第 20 层：需要 2560", 11, MUTED)
    s += text(76, 584, "第 1 层：128", 11, MUTED)
    # exact boundary
    s += rect(676, 380, 5, 171, RED, RED, 2, 0)
    s += text(676, 372, "精确重建 2560", 11, RED, 800, "middle")
    # bounded replay band
    s += rect(646, 380, 30, 171, BLUE, BLUE, 3, 0)
    s += text(646, 600, "Bounded Replay 只回放这 128 个", 11, BLUE, 700, "middle")

    # right text box
    s += rect(760, 350, 384, 230, "#FFFFFF", LINE, 12, 1.2)
    s += text(780, 380, "误差锥怎么来的？", 14, INK, 800)
    lines = [
        "第 1 层最后 128 个 token 的输出，依赖前 128 个输入；",
        "第 2 层要精确，就得把这 128 个位置在第 1 层也算准；",
        "每往上一层，边界多影响 128 个 token，20 层累积 2560。",
        "",
        "Bounded Replay 不补这条锥，只回放最后 128 个 token：",
        "边界近似，但代价从 O(层数 × 窗口) 变成 O(窗口)。",
    ]
    y = 410
    for line in lines:
        if line:
            s += text(780, y, line, 11, MUTED)
        y += 24

    # Panel C: hit policy
    s += text(56, 636, "命中长度怎么算？——L = 10,000 的例子（示意，非等比）", 15, INK, 800)
    y = 662
    segs = [
        (56, 500, "#E9EDF5", "#C9D2E0"),
        (556, 140, "#DCE3F7", "#B9C6EE"),
        (696, 180, BLUE_BG, BLUE),
        (876, 100, AMBER_BG, AMBER),
        (976, 168, RED_BG, RED),
    ]
    for x, ww, fill, stroke in segs:
        s += rect(x, y, ww, 36, fill, stroke, 6, 1.2)
    s += text(70, y + 23, "0 … 9,472", 11, MUTED)
    s += text(566, y + 23, "9,472–9,600", 10, MUTED, 600)
    s += text(706, y + 23, "9,600–9,728", 10, BLUE, 700)
    s += text(886, y + 23, "9,728–9,866", 9, AMBER, 700)
    s += text(986, y + 23, "9,866–10,000", 9, RED, 700)
    # labels
    s += text(696, 650, "Block 命中 L1 = 9,728", 11, BLUE, 800)
    s += text(876, 650, "最大命中 L-134 = 9,866", 11, AMBER, 800)
    s += text(976, 718, "尾部 134 必须留出", 11, RED, 700)
    # below
    s += text(56, 744, "① 先查 Block KV：L1 必须是 128 的整数倍。", 12, MUTED)
    s += text(56, 768, "② 再查 [L1-128, L1] 内有没有 SWA：有 → 命中 L1；没有 → 退一个 block 到 9,600，重算最后 128 个 token。", 12, MUTED)
    s += text(56, 792, "③ 上限 L-134：窗口 128 + 投机回退 6；命中再长，尾部也没有足够空间重建 SWA。", 12, MUTED)

    # bottom note
    s += text(56, 828, "一句话：Block KV 决定「能命中多长」，SWA KV 决定「最后一个 block 要不要退」。", 13, BLUE, 800)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 07 prefill cost model
# ---------------------------------------------------------------------------
def fig_cost_model():
    w, h = 1200, 680
    s = fig_open(w, h)
    s += fig_title("Prefill 单卡内：给定时间预算，反解这一步能算多少 token",
                   "chunk size 不固定；每步定一个纳秒级预算，用二次代价模型 cost(q,c) 反解 q，再用 DP 组内 allreduce-MIN 取最小预算")

    # left: step
    s += rect(56, 136, 230, 52, BLUE_BG, "#C7D2FE", 10, 1.2)
    s += text(76, 158, "第 N 步", 11, BLUE, 800)
    s += text(76, 178, "时间预算 T = 8 ms", 15, INK, 800)
    s += arrow(171, 188, 171, 214, "blue", 2)
    s += rect(56, 214, 230, 26, "#EEF1F6", "#D5DCE8", 6, 1)
    s += rect(56, 214, 230, 26, BLUE, BLUE, 6, 0)
    s += text(171, 232, "本步预算", 10, "#FFFFFF", 700, "middle")
    s += arrow(171, 240, 171, 266, "blue", 2)
    s += rect(56, 266, 230, 76, "#FFFFFF", LINE, 10, 1.2)
    s += text(76, 292, "反解 q*", 11, MUTED, 700)
    s += text(76, 320, "≈ 10,000 token", 20, INK, 800)
    s += text(56, 372, "q 上限 32,768", 11, MUTED)
    s += text(56, 394, "预算再被 DP 组内", 11, MUTED)
    s += text(56, 412, "allreduce-MIN 压低", 11, MUTED)

    # center: curve
    px0, py0, pw, ph = 340, 150, 400, 340
    s += rect(px0, py0, pw, ph, "#FFFFFF", LINE, 8, 1)
    for i in range(1, 5):
        s += line(px0, py0 + i * ph / 5, px0 + pw, py0 + i * ph / 5, "#EEF1F6", 1)
        s += line(px0 + i * pw / 5, py0, px0 + i * pw / 5, py0 + ph, "#EEF1F6", 1)
    # axes labels
    s += text(px0 + pw / 2, py0 + ph + 28, "q（本步 token 数）→", 12, MUTED, 600, "middle")
    s += f'<text x="{px0 - 14}" y="{py0 + ph / 2}" font-size="12" fill="{MUTED}" text-anchor="middle" transform="rotate(-90 {px0 - 14} {py0 + ph / 2})">cost（ms）→</text>'
    for q in (0, 4000, 8000, 12000, 16000):
        x = px0 + q / 16000 * pw
        s += text(x, py0 + ph + 18, f"{q // 1000}K" if q else "0", 9, SOFT, 400, "middle")
    for c in (0, 4, 8, 12, 16):
        y = py0 + ph - c / 16 * ph
        s += text(px0 - 8, y + 4, f"{c}", 9, SOFT, 400, "end")

    def cx(q): return px0 + q / 16000 * pw
    def cy(c): return py0 + ph - c / 16 * ph
    b1, b2 = 0.0006, 0.0012
    pts1 = [(cx(q), cy(2e-8 * q * q + b1 * q)) for q in range(0, 16001, 400)]
    pts2 = [(cx(q), cy(2e-8 * q * q + b2 * q)) for q in range(0, 11001, 400)]
    s += poly(pts1, BLUE, 2.8)
    s += poly(pts2, AMBER, 2.4, "6 4")
    # budget line
    s += line(px0, cy(8), px0 + pw, cy(8), RED, 1.6, "4 4")
    s += text(px0 + pw - 4, cy(8) - 8, "T = 8 ms", 11, RED, 800, "end")
    # intersections
    s += circle(cx(10000), cy(8), 5, BLUE, "#FFFFFF", 2)
    s += line(cx(10000), cy(8), cx(10000), py0 + ph, BLUE, 1, "3 3")
    s += text(cx(10000) + 8, cy(8) - 10, "q* ≈ 10.0K", 11, BLUE, 800)
    s += circle(cx(6050), cy(8), 5, AMBER, "#FFFFFF", 2)
    s += line(cx(6050), cy(8), cx(6050), py0 + ph, AMBER, 1, "3 3")
    s += text(cx(6050) - 8, cy(8) + 20, "q* ≈ 6.1K", 11, AMBER, 800, "end")
    # legend
    s += line(px0 + 14, py0 + 18, px0 + 44, py0 + 18, BLUE, 2.5)
    s += text(px0 + 50, py0 + 22, "c = 32K", 10, BLUE, 700)
    s += line(px0 + 124, py0 + 18, px0 + 154, py0 + 18, AMBER, 2, "6 4")
    s += text(px0 + 160, py0 + 22, "c = 128K", 10, AMBER, 700)

    # right: formula
    s += rect(790, 150, 354, 340, "#F7F9FC", LINE, 12, 1.2)
    s += text(810, 182, "把 q 反解出来", 15, INK, 800)
    s += text(810, 214, "cost(q, c) = a·q² + b_eff·q + d", 14, INK, 700)
    s += text(810, 242, "b_eff = b0 + b1·c", 12, MUTED)
    s += text(810, 276, "令 cost(q, c) = T：", 12, MUTED)
    s += text(810, 304, "a·q² + b_eff·q + (d − T) = 0", 14, INK, 700)
    s += text(810, 340, "q* = (−b_eff + √(b_eff² + 4a(T−d))) / 2a", 12, BLUE, 700)
    s += line(810, 360, 1124, 360, LINE, 1)
    s += text(810, 388, "示例（示意参数）", 12, INK, 800)
    s += text(810, 414, "a = 2e−8 ms/token²", 11, MUTED)
    s += text(810, 436, "b_eff = 6e−4 ms/token（c=32K）", 11, MUTED)
    s += text(810, 458, "T = 8 ms，d ≈ 0", 11, MUTED)
    s += text(810, 484, "→ q* ≈ 10,000 token", 13, BLUE, 800)

    # bottom: why time-based
    s += rect(56, 536, 1088, 118, "#FFFFFF", LINE, 12, 1.2)
    items = [
        ("固定 chunk", "前缀一长，每步耗时漂移，TBT 跟着抖。", RED),
        ("按预算反解", "每步贴住预算，TBT 稳，SLA 好守。", BLUE),
        ("allreduce-MIN", "取组内最慢 rank 的剩余预算，避免木桶效应。", TEAL),
    ]
    x = 78
    for title, desc, color in items:
        s += text(x, 568, title, 14, color, 800)
        s += text(x, 594, desc, 11, MUTED)
        x += 356
    s += text(78, 632, "一句话：把 chunked prefill 从「按空间切」升级为「按时间切」—— 预算以纳秒计，反解出的 q 才是这一步真正该算的量。", 13, INK, 700)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 08 async scheduling + variable verification
# ---------------------------------------------------------------------------
def fig_async():
    w, h = 1200, 770
    s = fig_open(w, h)
    s += fig_title("把 GPU 的空闲时间填满：异步调度 + 变长投机验证",
                   "Decode 每步都要等 sample 结果才能排下一步；把 CPU 调度挪到 GPU 计算期间，再把验证长度交给 GPU 现算")

    # timeline
    t0, t1 = 80, 1120
    ms = (t1 - t0) / 12.0
    def tx(t): return t0 + t * ms

    s += text(56, 132, "同步版：sample 之后要等 CPU 拿到结果，GPU 空转", 14, INK, 800)
    # GPU row
    s += text(56, 168, "GPU", 11, BLUE, 800)
    s += rect(tx(0), 150, tx(4) - tx(0), 34, BLUE_BG, BLUE, 6, 1.2)
    s += text(tx(2), 172, "forward(N)", 11, BLUE, 700, "middle")
    s += rect(tx(4), 150, tx(1) - tx(0), 34, PURPLE_BG, PURPLE, 6, 1.2)
    s += text(tx(4.5), 172, "sample", 10, PURPLE, 700, "middle")
    s += rect(tx(5), 150, tx(2) - tx(0), 34, RED_BG, RED, 6, 1.2)
    s += text(tx(6), 172, "GPU 空闲", 10, RED, 800, "middle")
    s += rect(tx(7), 150, tx(4) - tx(0), 34, BLUE_BG, BLUE, 6, 1.2)
    s += text(tx(9), 172, "forward(N+1)", 11, BLUE, 700, "middle")
    # CPU row
    s += text(56, 218, "CPU", 11, AMBER, 800)
    s += rect(tx(0), 200, tx(1) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(0.5), 218, "schedule(N)", 9, AMBER, 700, "middle")
    s += rect(tx(5), 200, tx(2) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(6), 218, "post(N-1)", 9, AMBER, 700, "middle")
    s += rect(tx(7), 200, tx(1) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(7.5), 218, "schedule(N+1)", 8, AMBER, 700, "middle")
    # idle bracket
    s += text(tx(6), 246, "↑ 这 2 ms，GPU 在等 CPU", 10, RED, 700, "middle")

    s += text(56, 292, "异步版：GPU 算 N 的时候，CPU 已经在排 N+1", 14, INK, 800)
    # GPU row
    s += text(56, 328, "GPU", 11, BLUE, 800)
    s += rect(tx(0), 310, tx(4) - tx(0), 34, BLUE_BG, BLUE, 6, 1.2)
    s += text(tx(2), 332, "forward(N)", 11, BLUE, 700, "middle")
    s += rect(tx(4), 310, tx(1) - tx(0), 34, PURPLE_BG, PURPLE, 6, 1.2)
    s += text(tx(4.5), 332, "sample(N)", 9, PURPLE, 700, "middle")
    s += rect(tx(5), 310, tx(4) - tx(0), 34, BLUE_BG, BLUE, 6, 1.2)
    s += text(tx(7), 332, "forward(N+1)", 11, BLUE, 700, "middle")
    # CPU row
    s += text(56, 378, "CPU", 11, AMBER, 800)
    s += rect(tx(5), 360, tx(2) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(6), 378, "schedule(N+1)", 9, AMBER, 700, "middle")
    s += rect(tx(5), 392, tx(2) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(6), 410, "post(N-1)", 9, AMBER, 700, "middle")
    s += rect(tx(7), 360, tx(1) - tx(0), 26, AMBER_BG, AMBER, 5, 1)
    s += text(tx(7.5), 378, "launch sample", 8, AMBER, 700, "middle")
    # overlap bracket
    s += line(tx(5), 436, tx(7), 436, TEAL, 2, "3 3")
    s += text(tx(6), 454, "GPU / CPU 重叠，无空闲", 10, TEAL, 800, "middle")

    # variable verification
    s += text(56, 500, "变长验证：把验证算力花在边际收益最高的 token 上", 14, INK, 800)
    s += text(56, 524, "5 个 draft token 的接受概率不同；固定验证 5 个，会在低概率位上浪费算力。", 11, MUTED)
    # bars
    probs = [0.95, 0.90, 0.80, 0.60, 0.40]
    bx, by, bw, maxh = 80, 560, 70, 100
    for i, p in enumerate(probs):
        x = bx + i * 96
        hh = maxh * p
        s += rect(x, by + maxh - hh, bw, hh, BLUE_BG, BLUE, 6, 1.2)
        s += text(x + bw / 2, by + maxh - hh - 8, f"{p:.2f}", 10, BLUE, 700, "middle")
        s += text(x + bw / 2, by + maxh + 18, f"draft {i + 1}", 9, MUTED, 400, "middle")
    # cut line
    s += line(bx + 4 * 96 - 10, by - 6, bx + 4 * 96 - 10, by + maxh + 4, RED, 2, "5 4")
    s += text(bx + 4 * 96 - 16, by - 14, "动态截断", 10, RED, 800, "end")
    # stats
    s += rect(600, 550, 504, 76, "#FFFFFF", LINE, 10, 1.2)
    s += text(620, 578, "验证 token 5.00 → 3.2–4.4", 12, INK, 700)
    s += text(620, 600, "接受长度 3.29 vs 3.20（基本不变）", 11, MUTED)
    s += text(620, 618, "生产运行点折合 +4~7% 吞吐（官方线上约 +6%）", 11, MUTED)
    # confidence box
    s += rect(600, 640, 504, 64, PURPLE_BG, "#DDD6FE", 10, 1.2)
    s += text(620, 666, "异步下 confidence 还没回传？", 11, PURPLE, 800)
    s += text(620, 688, "CPU 只定总预算；逐请求长度由 GPU kernel 现算（累乘/排序/remap），写回 pinned buffer。", 10, MUTED)

    # bottom note
    s += text(56, 740, "一句话：异步调度解决「CPU 等 GPU」，变长验证解决「GPU 等低概率 token」——两者都在填同一段空闲。", 12, BLUE, 800)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 09 EPLB
# ---------------------------------------------------------------------------
def fig_eplb():
    w, h = 1200, 760
    s = fig_open(w, h)
    s += fig_title("EPLB：冗余专家吸收热点，优化目标是每一步的最慢 rank",
                   "平均负载均衡不等于每步快；同步并行里，一步的耗时由最慢的 rank 决定")

    # left: cards
    s += text(56, 140, "每张卡多备 1 个冗余专家（Decode / EP64）", 15, INK, 800)
    s += text(56, 164, "384 / 64 = 6 个本卡专家 + 1 个冗余；冗余用来放热门专家的副本", 11, MUTED)
    for i in range(8):
        x = 56 + (i % 4) * 140
        y = 196 + (i // 4) * 120
        s += rect(x, y, 124, 98, "#FFFFFF", LINE, 10, 1.2)
        s += text(x + 62, y + 20, f"卡 {i}", 10, MUTED, 700, "middle")
        for j in range(7):
            ex = x + 8 + (j % 4) * 28
            ey = y + 32 + (j // 4) * 28
            hot = (j == 6 and i in (1, 5))
            s += rect(ex, ey, 22, 22, RED if hot else (AMBER_BG if j == 6 else BLUE_BG),
                      RED if hot else (AMBER if j == 6 else BLUE), 4, 0.8)
        s += text(x + 62, y + 92, "6 个本卡 + 1 个冗余", 8, SOFT, 400, "middle")
    s += text(56, 446, "红色 = 热门专家的两个副本；统计最近 N 步负载，每 M 步重排一次，", 10, MUTED)
    s += text(56, 464, "专家权重经 NVLink symm_mem 在组内 shuffle。", 10, MUTED)

    # right: deviation bars
    s += text(640, 140, "一步之内，8 个 rank 的负载并不相等", 15, INK, 800)
    s += text(640, 164, "优化目标不是「平均负载最小」，而是「历史窗口内每步最大负载之和最小」", 10, MUTED)
    loads = [0.99, 1.01, 0.98, 1.02, 1.09, 0.97, 1.00, 1.01]
    avg = sum(loads) / len(loads)
    base_y, scale = 330, 9.0  # 1% deviation = 9 px
    for i, load in enumerate(loads):
        x = 660 + i * 56
        dev = (load - avg) * 100
        hh = abs(dev) * scale
        if dev >= 0:
            s += rect(x, base_y - hh, 42, hh, BLUE_BG if dev < 5 else RED_BG,
                      BLUE if dev < 5 else RED, 5, 1.2)
            s += text(x + 21, base_y - hh - 7, f"{dev:+.1f}%", 9, BLUE if dev < 5 else RED, 700, "middle")
        else:
            s += rect(x, base_y, 42, hh, BLUE_BG, BLUE, 5, 1.2)
            s += text(x + 21, base_y + hh + 12, f"{dev:+.1f}%", 9, BLUE, 700, "middle")
        s += text(x + 21, 430, f"R{i}", 9, MUTED, 400, "middle")
    s += line(650, base_y, 1120, base_y, TEAL, 1.6, "4 4")
    s += text(1124, base_y + 4, "均值", 9, TEAL, 700)
    s += text(900, 190, "moe_lb = 最慢 rank / 均值 ≈ 1.09", 12, RED, 800, "middle")
    s += text(900, 212, "最慢的 R4 决定这一步的耗时", 10, MUTED, 400, "middle")
    s += text(640, 458, "把热点专家复制到空闲卡，把 R4 的偏差压回 ±2%，", 10, MUTED)
    s += text(640, 476, "max 下降，整步就快 —— 这是「最大负载」目标与「平均负载」目标的差别。", 10, MUTED)

    # bottom table
    s += rect(56, 500, 1088, 196, "#FFFFFF", LINE, 12, 1.2)
    s += text(78, 530, "Prefill 与 Decode 的 EPLB 参数：为什么一个 4 个冗余，一个 1 个？", 14, INK, 800)
    for label, x in [("", 78), ("Prefill", 420), ("Decode", 760)]:
        s += text(x, 562, label, 11, MUTED, 800)
    rows = [
        ("每卡冗余专家", "4 个", "1 个"),
        ("统计窗", "100 步", "1000 步"),
        ("重排周期", "1000 步", "10000 步"),
        ("实测 moe_lb", "1.045 ~ 1.074", "1.090"),
    ]
    y = 588
    for a, b, c in rows:
        s += line(78, y - 16, 1124, y - 16, "#EEF1F6", 1)
        s += text(78, y, a, 11, MUTED, 600)
        s += text(420, y, b, 11, BLUE, 700)
        s += text(760, y, c, 11, AMBER, 700)
        y += 24
    s += text(78, 684, "Prefill batch 大、专家负载波动剧烈，需要更多冗余吸收热点；Decode batch 小、负载平稳，1 个就够。", 10, SOFT)

    # bottom note
    s += text(56, 736, "一句话：冗余专家是「用显存换均衡」；目标函数选 max 而不是 mean，指标才会真的变好。", 12, BLUE, 800)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 10 economics
# ---------------------------------------------------------------------------
def fig_economics():
    w, h = 1200, 760
    s = fig_open(w, h)
    s += fig_title("38 美金/卡·时的成本拆解：钱花在哪，毛利从哪来",
                   "以下为第三方测算，不是 DeepSeek 官方成本数据；谷价、折旧年限、电价、PUE 均为假设，只用于判断量级")

    # left: revenue vs cost
    s += text(56, 140, "单卡小时收入 $38（谷价）", 15, INK, 800)
    s += rect(56, 156, 500, 46, BLUE_BG, BLUE, 10, 1.4)
    s += text(76, 186, "$38 / card·hour", 20, BLUE, 800)
    s += text(420, 186, "100%", 12, BLUE, 700, "middle")

    s += text(56, 238, "单卡小时成本 ≈ $2–2.5（下图放大 15× 显示）", 13, INK, 800)
    # cost bar, widths proportional to 2.5 total
    segs = [
        ("卡本身", 1.45, "#4D6BFE", BLUE_BG),
        ("电费", 0.12, "#F59E0B", AMBER_BG),
        ("基础设施", 0.40, "#0E9F6E", TEAL_BG),
        ("余量", 0.53, "#94A3B8", "#F1F5F9"),
    ]
    x = 56
    total = 2.5
    for label, val, color, bg in segs:
        ww = 500 * val / total
        s += rect(x, 254, ww, 46, bg, color, 0, 1)
        if ww > 60:
            s += text(x + ww / 2, 282, label, 10, color, 700, "middle")
        x += ww
    s += rect(56, 254, 500, 46, "none", LINE, 10, 1.2)
    # legend
    y = 326
    for label, val, color, bg in segs:
        s += circle(64, y - 4, 5, color)
        s += text(78, y, f"{label}  ${val:.2f}", 11, MUTED, 600)
        y += 24
    s += text(320, 326, "合计 ≈ $2.5", 12, INK, 800)
    s += text(320, 350, "毛利 ≈ $35.5–36 / 卡·时", 12, TEAL, 800)
    s += text(320, 374, "毛利率 ≈ 93–95%", 15, TEAL, 800)

    # right: comparison table
    s += rect(620, 140, 524, 240, "#FFFFFF", LINE, 12, 1.2)
    s += text(644, 172, "V3/R1  vs  V4.1 Flash（第三方推算）", 13, INK, 800)
    for label, x in [("", 644), ("V3 / R1", 840), ("V4.1", 1010)]:
        s += text(x, 204, label, 10, MUTED, 800)
    rows = [
        ("卡数", "~1,800", "~7,300"),
        ("单卡小时收入", "$13", "$38"),
        ("日收入", "~$0.56M", "~$6.7M"),
    ]
    y = 230
    for a, b, c in rows:
        s += line(644, y - 16, 1120, y - 16, "#EEF1F6", 1)
        s += text(644, y, a, 11, MUTED, 600)
        s += text(840, y, b, 11, AMBER, 700)
        s += text(1010, y, c, 11, BLUE, 700)
        y += 28
    s += text(644, 336, "单价降了，单卡收入反而涨 —— 靠的是缓存命中、稀疏注意力与投机解码。", 10, SOFT)
    s += text(644, 356, "年化收入量级：7300 × $38 × 24 × 365 ≈ $2.4B（谷价）。", 10, SOFT)

    # scenarios
    s += rect(620, 396, 524, 130, "#F7F9FC", "#E6EBF3", 10, 1)
    s += text(640, 424, "两种拿卡方式", 12, INK, 800)
    s += text(640, 450, "自有 GB200/B200：成本 $2–2.5 → 毛利率 ~94%", 11, MUTED)
    s += text(640, 472, "租 B200：$5–7 → 毛利率 82–87%", 11, MUTED)
    s += text(640, 500, "长期服务下，买卡相对租卡有约 2–3 倍成本优势。", 10, SOFT)

    # bottom caveats
    s += rect(56, 548, 1088, 142, RED_BG, "#F5C2C7", 12, 1.2)
    s += text(78, 578, "口径提醒：这不是官方成本表", 14, RED, 800)
    s += text(78, 604, "谷价、4 年折旧、¥0.6/度电价、PUE 1.4、100 PiB 存储等均为第三方假设；成本口径上，官方只披露了「155 万亿 tokens/天」与「$38/卡·时」。", 11, MUTED)
    s += text(78, 626, "这些数字适合判断量级与敏感性，不适合当作财务核算。真正决定毛利的是：拿卡价格、电价、在线效率（≈离线 80%）与 P:D 配比（≈1:1）。", 11, MUTED)
    s += text(78, 650, "敏感性：在线效率每掉 10 个百分点，或 P:D 明显偏离 1:1，单卡收入就会显著低于 $38 —— 同样的卡，收益差距出在调度与配比上。", 11, MUTED)

    # bottom note
    s += text(56, 722, "一句话：$38 不是「卡贵」，是「调度把卡用满了」；成本结构里真正的大头只有卡和电。", 12, BLUE, 800)
    return s + "</svg>"


def write(name, svg):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", path)


if __name__ == "__main__":
    write("00-cover.svg", fig_cover())
    write("01-overview.svg", fig_overview())
    write("02-roofline.svg", fig_roofline())
    write("03-wide-ep.svg", fig_wide_ep())
    write("04-kvcache.svg", fig_kvcache())
    write("05-3fs-gdr.svg", fig_3fs())
    write("06-bounded-replay.svg", fig_replay())
    write("07-prefill-cost-model.svg", fig_cost_model())
    write("08-async-verify.svg", fig_async())
    write("09-eplb.svg", fig_eplb())
    write("10-economics.svg", fig_economics())

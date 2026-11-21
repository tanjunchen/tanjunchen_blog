#!/usr/bin/env python3
"""Generate original SVG diagrams for the KV Cache panorama article.

Run from the repository root:
    python3 scripts/gen_kv_panorama_figs.py

The SVGs are rendered to 2x PNGs by scripts/render_kv_panorama_figs.sh.
All figures are hand-laid-out; no external assets are used.
"""
import html
import os
import sys

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "images",
                   "2026-11-21-kv-cache-panorama")
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
GRAY = "#E5E9F0"

FONT = ("'PingFang SC','Hiragino Sans GB','Microsoft YaHei',"
        "'Helvetica Neue',Arial,sans-serif")

MARKERS = {
    "blue": BLUE, "ink": INK, "teal": TEAL, "amber": AMBER,
    "purple": PURPLE, "red": RED, "soft": SOFT,
}


def esc(s):
    return html.escape(str(s), quote=False)


def text(x, y, s, size=18, fill=INK, weight=400, anchor="start", opacity=1.0,
         spacing=None):
    extra = ""
    if spacing is not None:
        extra += f' letter-spacing="{spacing}"'
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}"{extra}>'
            f'{esc(s)}</text>')


def rect(x, y, w, h, fill=CARD, stroke=LINE, rx=12, sw=1.5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def line(x1, y1, x2, y2, color=LINE, sw=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{sw}"{d}/>')


def arrow(x1, y1, x2, y2, color="blue", sw=2.5, dash=None):
    c = MARKERS[color]
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" '
            f'stroke-width="{sw}" marker-end="url(#ar-{color})"{d}/>')


def circle(cx, cy, r, fill, stroke="none", sw=0):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def pill(x, y, w, h, label, color=BLUE, bg=BLUE_BG, size=14, weight=700):
    return rect(x, y, w, h, bg, color, h / 2, 1.2) + \
        text(x + w / 2, y + h / 2 + size * 0.36, label, size, color, weight,
             "middle")


def text_width(s, size):
    """Rough width in px, enough for laying out pills and cards."""
    total = 0.0
    for ch in str(s):
        if ord(ch) < 128:
            total += size * 0.57
        elif ch in "，。、；：！？（）【】「」“”":
            total += size
        else:
            total += size
    return total


def tag(x, y, label, color=MUTED, size=12):
    return text(x, y, label, size, color, 500)


def fig_open(w, h, bg="#FFFFFF"):
    defs = ["<defs>"]
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


# ---------------------------------------------------------------------------
# 01 账本
# ---------------------------------------------------------------------------
def fig_ledger():
    w, h = 1200, 800
    s = fig_open(w, h)
    s += fig_title("先算一笔账：KV 到底有多重",
                   "以一个 70B GQA 模型为例，80 层、8 个 KV 头、128 维，FP16 存储")

    # left: formula card
    s += rect(56, 140, 520, 280, CARD, LINE, 16, 1.5)
    s += text(80, 178, "一个 token 的 KV", 16, BLUE, 800, spacing=1)
    s += text(80, 224, "2 × 80 × 8 × 128 × 2 B", 30, INK, 800)
    s += text(80, 264, "= 327,680 B", 21, BLUE, 800)
    s += text(232, 264, "≈ 320 KB / token", 21, BLUE, 700)
    s += line(80, 286, 552, 286, LINE, 1)

    items = [
        ("2", "K 和 V 各一份"),
        ("80", "Transformer 层数"),
        ("8", "KV 头数（GQA）"),
        ("128", "每个头的维度"),
        ("2 B", "FP16 一个数"),
    ]
    positions = [(80, 316), (330, 316), (80, 356), (330, 356), (80, 396)]
    for (num, label), (x, y) in zip(items, positions):
        s += text(x, y, num, 17, INK, 800)
        s += text(x + text_width(num, 17) + 10, y, label, 16, MUTED)

    # right: context ladder
    s += rect(600, 140, 544, 280, "#FFFFFF", LINE, 16, 1.5)
    s += text(624, 178, "上下文一长，账就吓人", 16, TEAL, 800, spacing=1)
    s += text(624, 204, "以下都是「一个请求」的量", 14, SOFT)

    rows = [
        ("8K", "2.5 GB", 210, BLUE_BG, BLUE),
        ("32K", "10 GB", 285, BLUE_BG, BLUE),
        ("128K", "40 GB", 375, AMBER_BG, AMBER),
        ("1M", "320 GB", 485, RED_BG, RED),
    ]
    y = 224
    for ctx, size, width, bg, color in rows:
        s += rect(624, y, width, 38, bg, color, 10, 1)
        s += text(640, y + 25, ctx, 16, color, 800)
        s += text(624 + width - 12, y + 25, size, 16, color, 800, "end")
        y += 46

    # bottom: two punch cards
    s += rect(56, 446, 530, 122, BLUE_BG, "#C7D2FE", 16, 1.5)
    s += text(78, 478, "一张 80GB 卡，装完 70B FP8 权重", 16, BLUE_DARK, 700)
    s += text(78, 512, "剩约 10GB", 28, BLUE, 800)
    s += text(262, 512, "÷ 320KB ≈ 3.1 万 token", 16, INK, 600)
    s += text(78, 544, "一个 32K 上下文的请求，就能把剩下的显存吃干净。", 14, MUTED)

    s += rect(602, 446, 542, 122, RED_BG, "#FECACA", 16, 1.5)
    s += text(624, 478, "八个 128K 请求同时在线", 16, RED, 700)
    s += text(624, 512, "8 × 40GB = 320GB", 28, RED, 800)
    s += text(624, 544, "等于四张 80GB 卡，只放历史，不放权重。", 14, MUTED)

    # bottom: bandwidth strip
    s += rect(56, 594, 1088, 124, "#FFFFFF", LINE, 16, 1.5)
    s += rect(56, 594, 5, 124, RED, RED, 2, 0)
    s += text(80, 626, "Decode 更麻烦：每生成一个 token，都要把这个请求的历史 KV 从 HBM 读一遍。", 17, INK, 700)
    s += text(80, 662, "128K 上下文，一个 token 要读 40GB 的 KV；3TB/s 的 HBM，理论上限也就每秒几十个 token。", 17, INK, 700)
    s += text(80, 696, "算力不是不够，是喂不饱。", 16, RED, 800)

    s += text(56, 756, "口径：Llama-3-70B 级别配置；FP16 KV。换模型时按公式替换层数、KV 头数和维度即可。", 13, SOFT)
    s += text(56, 780, "别把 890 字节/token 这类数字直接套过来：那是特定模型的「全局 KV」口径，不含每层滑动窗口。", 13, SOFT)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 02 八层
# ---------------------------------------------------------------------------
def fig_stack():
    w, h = 1200, 948
    s = fig_open(w, h)
    s += fig_title("KV 优化的八个层次：从模型内部，一直管到数据中心",
                   "前三层少生成，中间两层少浪费，后三层挪到更便宜的地方；八层可以叠加，代价也会叠加")

    groups = [
        (1, "模型结构", "GQA / MQA · MLA · 稀疏注意力 · 跨层复用", "省容量", BLUE, "#F5F8FF"),
        (2, "精度", "FP8 / FP4 · INT4 · 2–3 bit · 混合精度", "省容量 / 带宽", BLUE, "#F5F8FF"),
        (3, "保留", "attention sink · heavy hitter · 分层预算 · 学习型策略", "省容量", BLUE, "#F5F8FF"),
        (4, "分配", "PagedAttention · 前缀共享 · 写时复制 · RadixAttention", "省容量", TEAL, "#F3FBF8"),
        (5, "复用", "前缀缓存 · 前缀感知路由 · KV 感知路由", "省算力", TEAL, "#F3FBF8"),
        (6, "分层存储", "HBM → DRAM → NVMe → 分布式存储 · KV 池", "省显存", AMBER, "#FFFAF2"),
        (7, "传输", "PD 分离 · RDMA · 跨域迁移 · 传输压缩", "省时延", AMBER, "#FFFAF2"),
        (8, "调度", "Chunked Prefill · KV 预算 / QoS · 可观测与计费", "省成本", AMBER, "#FFFAF2"),
    ]

    y = 148
    for num, name, tech, gain, color, bg in groups:
        s += rect(56, y, 1088, 84, bg, LINE, 14, 1)
        s += rect(56, y, 5, 84, color, color, 2, 0)
        s += circle(96, y + 42, 20, color)
        s += text(96, y + 42 + 6, str(num), 17, "#FFFFFF", 800, "middle")
        s += text(132, y + 37, name, 21, INK, 800)
        s += text(132, y + 65, tech, 16, MUTED, 500)
        s += pill(936, y + 25, 180, 34, gain, color,
                  "#FFFFFF", 14)
        y += 88

    # legend
    ly = 862
    s += text(56, ly + 14, "作用范围", 12, SOFT, 700)
    legend = [("模型内部", BLUE), ("推理引擎", TEAL), ("集群与数据中心", AMBER)]
    x = 140
    for label, color in legend:
        s += circle(x + 7, ly + 9, 7, color)
        s += text(x + 20, ly + 14, label, 12, MUTED, 600)
        x += 150

    # bottom note
    s += rect(56, 890, 1088, 46, CARD, "#E6EBF3", 10, 1)
    s += text(76, 918, "八层不是八选一：结构层省下来的，精度层还能再省一遍；但每叠一层，精度和工程复杂度也会叠一层。", 14, MUTED)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 03 删除不等于释放
# ---------------------------------------------------------------------------
def fig_evict():
    w, h = 1200, 720
    s = fig_open(w, h)
    s += fig_title("逻辑删除，不等于物理释放",
                   "驱逐算法负责「删谁」，分配器负责「还页」；中间少了搬移，显存账单不会变")

    panels = [
        (56, "驱逐前", "24 个 token，占 3 个 block"),
        (420, "逻辑驱逐后", "注意力不算了，但块还占着"),
        (784, "物理合并后", "幸存 token 搬家，尾部块归还"),
    ]
    for px, title, sub in panels:
        s += rect(px, 140, 330, 380, "#FFFFFF", LINE, 16, 1.5)
        s += text(px + 18, 172, title, 18, INK, 800)
        s += text(px + 18, 194, sub, 11, MUTED)

    def block(px, by, label, states, color=BLUE):
        """states: list of 8 ints or 'x' or '' (unused)."""
        out = rect(px + 15, by, 300, 70, CARD, LINE, 10, 1)
        out += text(px + 25, by + 16, label, 10, SOFT, 600)
        for i, st in enumerate(states):
            sx = px + 24 + i * 34
            sy = by + 28
            if st == "":
                out += rect(sx, sy, 30, 30, "#F1F4F8", "#EDF1F7", 5, 1, "3 3")
            elif st == "x":
                out += rect(sx, sy, 30, 30, "#FFFFFF", "#FCA5A5", 5, 1.2, "4 3")
                out += text(sx + 15, sy + 20, "×", 13, "#F87171", 700, "middle")
            else:
                out += rect(sx, sy, 30, 30, BLUE_BG, BLUE, 5, 1.1)
                out += text(sx + 15, sy + 20, str(st), 10, BLUE, 700, "middle")
        return out

    # panel 1: tokens 1..24
    states1 = [list(range(1 + i * 8, 9 + i * 8)) for i in range(3)]
    for i, st in enumerate(states1):
        s += block(56, 216 + i * 86, f"Block {i}", st)
    s += text(74, 476, "显存账单：3 页", 15, INK, 800)
    s += tag(74, 498, "24 个 token 都有效", MUTED, 11)

    # panel 2: survivors
    survivors = [1, 2, 5, 8, 9, 12, 15, 18, 21, 22, 24]
    states2 = []
    for b in range(3):
        row = []
        for j in range(8):
            tok = b * 8 + j + 1
            row.append(tok if tok in survivors else "x")
        states2.append(row)
    for i, st in enumerate(states2):
        s += block(420, 216 + i * 86, f"Block {i}", st)
    s += text(438, 476, "显存账单：还是 3 页", 15, RED, 800)
    s += tag(438, 498, "空洞留在块里，尾部块也没释放", RED, 11)

    # panel 3: compacted
    states3 = []
    survivors3 = [1, 2, 5, 8, 9, 12, 15, 18, 21, 22, 24]
    for b in range(2):
        row = survivors3[b * 8:(b + 1) * 8]
        row += [""] * (8 - len(row))
        states3.append(row)
    for i, st in enumerate(states3):
        s += block(784, 216 + i * 86, f"Block {i}", st)
    # free block
    s += rect(799, 388, 300, 70, "#F8FAFC", "#CBD5E1", 10, 1.5, "6 4")
    s += text(949, 418, "Block 2", 12, SOFT, 700, "middle")
    s += text(949, 440, "已归还给显存池", 13, TEAL, 700, "middle")
    s += text(802, 476, "显存账单：2 页", 15, TEAL, 800)
    s += tag(802, 498, "真正少了一页", TEAL, 11)

    # arrows
    s += arrow(388, 330, 414, 330, "ink", 2.2)
    s += arrow(752, 330, 778, 330, "teal", 2.2)
    s += text(388, 318, "标记", 10, SOFT, 600, "middle")
    s += text(752, 318, "搬移", 10, TEAL, 600, "middle")

    # bottom callout
    s += rect(56, 548, 1088, 108, BLUE_BG, "#C7D2FE", 14, 1.5)
    s += text(78, 580, "为什么很多压缩方案「论文里降 70%，上线只降 20%」？", 16, BLUE_DARK, 800)
    s += text(78, 610, "因为删 token 是算法的事，还页是分配器的事。中间少了一步物理搬移，空洞就一直留在显存里。", 14, INK, 600)
    s += text(78, 638, "TriAttention 的做法：定期把幸存 token 搬成连续前缀，只压缩生成后缀，prompt 前缀保留不动。", 14, MUTED)

    s += text(56, 700, "示意图：一个 block 装 8 个 token；实际 block 大小、淘汰粒度和保留策略因引擎而异。", 12, SOFT)
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 04 分层
# ---------------------------------------------------------------------------
def fig_tier():
    w, h = 1200, 780
    s = fig_open(w, h)
    s += fig_title("KV 的分层存储：把冷数据请出显存",
                   "从 HBM 到分布式存储，容量越来越大，速度越来越慢；分层的关键是预判和限流")

    tiers = [
        ("L1", "GPU HBM", "正在跑的请求，热会话", "TB/s · 亚微秒", 170, 380, BLUE, BLUE_BG),
        ("L2", "CPU DRAM", "温会话，随时能回迁", "百 GB/s · 百纳秒", 130, 460, TEAL, TEAL_BG),
        ("L3", "本地 NVMe", "冷上下文，量大管饱", "GB/s · 百微秒", 90, 540, AMBER, AMBER_BG),
        ("L4", "分布式存储", "海量历史，跨节点共享", "网络 · 毫秒级", 50, 620, PURPLE, PURPLE_BG),
    ]

    y = 150
    for label, name, desc, metric, x, width, color, bg in tiers:
        s += rect(x, y, width, 104, bg, color, 16, 1.5)
        s += text(x + 22, y + 34, label, 13, color, 800, spacing=1.5)
        s += text(x + 22, y + 66, name, 21, INK, 800)
        s += text(x + 22, y + 90, desc, 12, MUTED)
        s += text(x + width - 20, y + 34, metric, 12, color, 700, "end")
        y += 118

    # right side: why + how
    rx = 720
    s += text(rx, 178, "为什么不干脆全放显存？", 18, INK, 800)
    reasons = [
        ("贵", "同样 1GB，HBM 和 SSD 的成本差一个数量级。"),
        ("冷热不均", "Agent 的长前缀可能几小时才用一次，占着 HBM 不划算。"),
        ("回迁有代价", "回迁会抢 PCIe / 网络带宽，得靠预取和限流兜住。"),
    ]
    y = 214
    for head, body in reasons:
        s += circle(rx + 8, y - 5, 5, AMBER)
        s += text(rx + 22, y, head, 15, INK, 800)
        s += text(rx + 22, y + 24, body, 13, MUTED)
        y += 68

    # formula box
    s += rect(rx, 430, 424, 190, "#FFFFFF", LINE, 14, 1.5)
    s += text(rx + 22, 462, "先算一笔回迁账", 15, INK, 800)
    s += text(rx + 22, 492, "回迁次数 ≈ 未命中次数", 15, BLUE, 700)
    s += text(rx + 22, 520, "命中率每高一点，PCIe 和网络就少堵一点。", 13, MUTED)
    s += text(rx + 22, 548, "所以分层不是「层数越多越好」，", 13, MUTED)
    s += text(rx + 22, 570, "而是「预取准、回迁稳、限流狠」。", 13, INK, 600)
    s += text(rx + 22, 598, "一个反直觉的点：回迁本身也会制造毛刺。", 12, RED, 600)

    # stack caption
    s += text(56, 628, "越往下：容量更大、成本更低、速度更慢。分层不是免费的，每一跳都有代价。", 12, MUTED)

    # bottom vendors strip
    s += rect(56, 650, 1088, 78, CARD, "#E6EBF3", 14, 1)
    s += text(78, 680, "工程上把这套东西做成共享 KV 池的代表", 13, MUTED, 600)
    tags = [("Mooncake", BLUE), ("LMCache", TEAL), ("NVMe-oF", AMBER),
            ("CXL 内存池", PURPLE), ("DPU 卸载", INK)]
    x = 78
    for label, color in tags:
        ww = max(92, text_width(label, 13) + 28)
        s += pill(x, 692, ww, 26, label, color, "#FFFFFF", 12)
        x += ww + 10

    s += text(56, 758, "示意：各层容量、带宽、时延随硬件和部署方式变化；图中只表达数量级关系。", 12, SOFT)
    return s + "</svg>"


FIGS = {
    "01-ledger": fig_ledger,
    "02-layers": fig_stack,
    "03-eviction": fig_evict,
    "04-tiering": fig_tier,
}


def main():
    names = sys.argv[1:] or list(FIGS)
    for name in names:
        svg = FIGS[name]()
        path = os.path.join(OUT, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path} ({len(svg)} chars)")


if __name__ == "__main__":
    main()

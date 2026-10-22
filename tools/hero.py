#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hero.py — 博客头图生成器（Pillow 程序化绘制，1280×720 JPEG）

风格对齐 blog/2026-ai-debug-handbook-hero.jpg / blog/2026-long-doc-hero.jpg：
深蓝底 #0A0E1A + 细网格 + 悬浮玻璃拟态面板 + 青/紫/琥珀霓虹线条 + 发光端点，
画面下方 1/4 留暗（文章标题会叠在这里），四周约 8% 安全边距，
无人物、无白底、无中文文字、无水印。

用法：
    python3 tools/hero.py blog/2026-foo-hero.jpg --seed 12 --accent cyan

坑位提醒：做加法混合（ImageChops.add）时两层图必须同尺寸，
否则结果会被裁剪成较小的那张。
"""
import argparse, math, os, random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H = 1280, 720
BG = (10, 14, 26)
CYAN = (0, 229, 255)
VIOLET = (168, 85, 247)
AMBER = (245, 158, 11)
PINK = (244, 114, 182)
GREEN = (52, 211, 153)

ACCENTS = {
    "cyan":   [CYAN, VIOLET, AMBER],
    "violet": [VIOLET, PINK, CYAN],
    "amber":  [AMBER, PINK, VIOLET],
    "green":  [GREEN, CYAN, AMBER],
    "mixed":  [CYAN, AMBER, VIOLET, PINK],
}

LINE_COLORS = [CYAN, VIOLET, AMBER]


def gradient_bg(size, top, bottom):
    """竖向渐变：用小图放大，比逐像素快得多"""
    w, h = size
    strip = Image.new("RGB", (1, 64))
    px = strip.load()
    for y in range(64):
        t = y / 63
        px[0, y] = (int(top[0] + (bottom[0] - top[0]) * t),
                    int(top[1] + (bottom[1] - top[1]) * t),
                    int(top[2] + (bottom[2] - top[2]) * t))
    return strip.resize((w, h), Image.BICUBIC)


def radial_glow(size, center, radius, color, strength=1.0):
    """同尺寸径向光晕（加法混合用）"""
    w, h = size
    layer = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    steps = 24
    for i in range(steps, 0, -1):
        t = i / steps
        r = radius * t
        k = (1.0 - t) ** 2.2 * strength
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  fill=(int(color[0] * k), int(color[1] * k), int(color[2] * k)))
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.22))


def add(base, layer):
    if layer.size != base.size:
        layer = layer.resize(base.size, Image.LANCZOS)
    return ImageChops.add(base, layer)


def grid_overlay(base, step=60, alpha=13):
    w, h = base.size
    g = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(g)
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=(0, alpha, alpha))
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(0, alpha, alpha))
    return add(base, g)


def neon_line(draw, p0, p1, color, width=5, alpha=255):
    draw.line([p0, p1], fill=color + (alpha,), width=width, joint="curve")
    r = width / 2
    for p in (p0, p1):
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color + (alpha,))


def make_panel(w, h, colors, rnd, density=0.9):
    """画一块玻璃拟态面板（RGBA，带霓虹线条）"""
    pad = 40
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = [pad, pad, pad + w, pad + h]
    d.rounded_rectangle(box, radius=18, fill=(210, 225, 255, 22))
    d.rounded_rectangle(box, radius=18, outline=(200, 220, 255, 72), width=2)

    # 霓虹线条
    y = pad + 26
    while y < pad + h - 26:
        if rnd.random() < 0.78 * density:
            x0 = pad + rnd.randint(22, 40)
            x1 = x0 + rnd.randint(int(w * 0.22), int(w * 0.78))
            c = rnd.choice(colors)
            neon_line(d, (x0, y), (x1, y), c, width=rnd.choice([4, 5, 6]))            # 端点发光
            if rnd.random() < 0.42:
                gx, gy = x1, y
                for rr, aa in ((11, 34), (7, 70), (4, 235)):
                    d.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], fill=c + (aa,))
            y += rnd.randint(19, 27)
        else:
            y += rnd.randint(14, 20)

    return layer


def glow_dot(canvas, xy, color, radius=26, strength=0.9):
    g = radial_glow(canvas.size, xy, radius, color, strength)
    return add(canvas, g)


def generate(out_path, seed=1, accent="cyan"):
    rnd = random.Random(seed)
    colors = ACCENTS.get(accent, ACCENTS["cyan"])

    canvas = gradient_bg((W, H), (14, 19, 36), (7, 10, 19))

    # 顶部与两侧的彩色环境光
    canvas = add(canvas, radial_glow((W, H), (rnd.randint(180, 420), rnd.randint(40, 140)),
                                     rnd.randint(300, 420), colors[0], 0.5))
    canvas = add(canvas, radial_glow((W, H), (rnd.randint(880, 1150), rnd.randint(60, 200)),
                                     rnd.randint(280, 380), colors[1], 0.42))
    canvas = add(canvas, radial_glow((W, H), (rnd.randint(520, 780), rnd.randint(430, 560)),
                                     rnd.randint(240, 320), colors[2 % len(colors)], 0.20))

    canvas = grid_overlay(canvas, step=60, alpha=13)

    # 三块悬浮面板：中间大、左右小，轻微旋转
    specs = [
        # (中心 x, 中心 y, 宽, 高, 角度, 密度)
        (rnd.randint(590, 700), rnd.randint(280, 330), rnd.randint(420, 470), rnd.randint(260, 300), rnd.uniform(-7, -3), 1.0),
        (rnd.randint(210, 260), rnd.randint(300, 360), rnd.randint(200, 235), rnd.randint(150, 175), rnd.uniform(-13, -8), 0.95),
        (rnd.randint(1010, 1080), rnd.randint(300, 360), rnd.randint(190, 225), rnd.randint(150, 175), rnd.uniform(7, 13), 0.95),
    ]
    for cx, cy, pw, ph, ang, dens in specs:
        panel = make_panel(pw, ph, colors, rnd, dens)
        panel = panel.rotate(ang, resample=Image.BICUBIC, expand=True)
        px, py = cx - panel.width // 2, cy - panel.height // 2
        canvas = canvas.convert("RGBA")
        canvas.alpha_composite(panel, (px, py))
        canvas = canvas.convert("RGB")

    # 面板辉光
    for cx, cy, pw, ph, ang, dens in specs:
        canvas = glow_dot(canvas, (cx, cy - ph // 3), colors[0], radius=int(pw * 0.42), strength=0.30)

    # 底部压暗，给标题留出干净区域
    fade = Image.new("RGB", (W, H), (0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for y in range(H - 340, H):
        t = (y - (H - 340)) / 340.0
        v = int(16 * (1 - t) ** 1.4)
        fd.line([(0, y), (W, y)], fill=(v, v, v + 2))
    canvas = add(canvas, fade)

    # 暗角
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.22, -H * 0.30, W * 1.22, H * 1.30], fill=118)
    vig = vig.filter(ImageFilter.GaussianBlur(170))
    dark = Image.new("RGB", (W, H), (5, 7, 14))
    canvas = Image.composite(canvas, dark, vig)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.save(out_path, "JPEG", quality=90, optimize=True, progressive=True)
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--accent", default="cyan", choices=list(ACCENTS.keys()))
    a = ap.parse_args()
    p = generate(a.out, a.seed, a.accent)
    from PIL import Image as _I
    im = _I.open(p)
    print(f"OK {p}  {im.size[0]}×{im.size[1]}  {os.path.getsize(p) // 1024} KB")

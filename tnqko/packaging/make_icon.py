#!/usr/bin/env python3
"""Иконка TnQkoWallpaper: синтвейв-закат в окне с кошачьими ушками. Рисует packaging/icon-1024.png (Pillow)."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 2048  # рисуем в 2× и уменьшаем — сглаженные края
k = S / 1024


def P(*xy):
    return [v * k for v in xy]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def vgradient(size, stops):
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                d.line([(0, y), (w, y)], fill=lerp(c0, c1, (t - p0) / max(1e-6, p1 - p0)) + (255,))
                break
    return img


def rounded(mask_img, radius):
    """Скругляет углы маски: размытие + порог."""
    return mask_img.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: 255 if v > 127 else 0)


def main(out):
    # силуэт: окно со скруглёнными углами + два уха
    mask = Image.new("L", (S, S), 0)
    m = ImageDraw.Draw(mask)
    m.rounded_rectangle(P(104, 214, 920, 924), radius=190 * k, fill=255)
    m.polygon(P(150, 420, 222, 88, 452, 250), fill=255)
    m.polygon(P(874, 420, 802, 88, 572, 250), fill=255)
    mask = rounded(mask, 14 * k)

    horizon = 640
    scene = vgradient((S, S), [
        (0.00, (26, 12, 64)), (0.30, (88, 32, 150)), (0.52, (214, 76, 150)),
        (horizon / 1024, (255, 150, 120)), (horizon / 1024 + 0.001, (30, 10, 52)), (1.0, (14, 6, 30)),
    ])
    d = ImageDraw.Draw(scene)

    # звёзды
    import random
    rnd = random.Random(7)
    for _ in range(70):
        x, y = rnd.uniform(110, 914), rnd.uniform(100, 420)
        r = rnd.choice([1.5, 2, 2.5, 3.5])
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=(255, 240, 255, rnd.randint(140, 255)))

    # свечение солнца
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(P(232, 300, 792, 860), fill=(255, 120, 160, 150))
    scene.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70 * k)))

    # солнце с полосками
    cx, cy, r = 512, 560, 232
    sun = vgradient((S, S), [(0.0, (255, 236, 130)), (cy / 1024, (255, 170, 110)), (horizon / 1024, (255, 70, 140)), (1.0, (255, 70, 140))])
    smask = Image.new("L", (S, S), 0)
    sm = ImageDraw.Draw(smask)
    sm.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=255)
    sm.rectangle(P(0, horizon, 1024, 1024), fill=0)
    y, gap = 520, 6
    while y < horizon:
        sm.rectangle(P(0, y, 1024, y + gap), fill=0)
        y += gap + 22 - (y - 520) / 12
        gap += 3.2
    scene.paste(sun, (0, 0), smask)

    # горы
    d.polygon(P(104, horizon, 230, 560, 330, 610, 420, 540, 512, horizon), fill=(58, 18, 92, 255))
    d.polygon(P(560, horizon, 660, 548, 740, 600, 830, 520, 920, horizon), fill=(58, 18, 92, 255))

    # пол-сетка в перспективе
    line = (255, 80, 200, 255)
    vx = 512
    for i in range(-14, 15):
        x0 = vx + i * 34
        x1 = vx + i * 230
        d.line(P(x0, horizon, x1, 1024), fill=line, width=int(4 * k))
    t = 0.0
    for j in range(1, 12):
        yy = horizon + (1024 - horizon) * (j / 11) ** 2.1
        d.line(P(0, yy, 1024, yy), fill=line, width=int(4 * k))
    d.line(P(0, horizon, 1024, horizon), fill=(255, 190, 230, 255), width=int(5 * k))

    # кнопка «play» на солнце — это всё-таки видео-обои
    tri = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(tri).polygon(P(462, 420, 462, 540, 566, 480), fill=(255, 255, 255, 235))
    tri = Image.composite(tri, Image.new("RGBA", (S, S), (0, 0, 0, 0)), rounded(tri.split()[3], 6 * k))
    scene.alpha_composite(tri)

    # внутренняя часть ушей
    inner = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    idr = ImageDraw.Draw(inner)
    idr.polygon(P(196, 330, 236, 160, 372, 262), fill=(255, 140, 190, 255))
    idr.polygon(P(828, 330, 788, 160, 652, 262), fill=(255, 140, 190, 255))
    inner = Image.composite(inner, Image.new("RGBA", (S, S), (0, 0, 0, 0)), rounded(inner.split()[3], 10 * k))
    scene.alpha_composite(inner)

    art = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    art.paste(scene, (0, 0), mask)

    # блик по краю
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(2 * k))
    rim.paste((255, 220, 255, 90), (0, 0), edge)
    art.alpha_composite(rim)

    # мягкая тень
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((20, 0, 40, 110), (0, int(18 * k)), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26 * k))
    shadow.alpha_composite(art)

    shadow.resize((1024, 1024), Image.LANCZOS).save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("icon-1024.png")))

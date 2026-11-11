#!/usr/bin/env python3
"""Иконка TnQkoMusically: кошачий силуэт (как у TnQkoWallpaper), внутри — кружок «1» с кругом подхода и ноты."""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2048
k = S / 1024


def P(*xy):
    return [v * k for v in xy]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def vgradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=lerp(top, bottom, y / (h - 1)) + (255,))
    return img


def rounded(mask, r):
    return mask.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, int(size))
        except OSError:
            pass
    return ImageFont.load_default()


def main(out):
    mask = Image.new("L", (S, S), 0)
    m = ImageDraw.Draw(mask)
    m.rounded_rectangle(P(104, 214, 920, 924), radius=190 * k, fill=255)
    m.polygon(P(150, 420, 222, 88, 452, 250), fill=255)
    m.polygon(P(874, 420, 802, 88, 572, 250), fill=255)
    mask = rounded(mask, 14 * k)

    scene = vgradient((S, S), (34, 14, 70), (14, 8, 34))
    d = ImageDraw.Draw(scene)
    rnd = random.Random(11)
    for _ in range(60):
        x, y = rnd.uniform(110, 914), rnd.uniform(110, 900)
        r = rnd.choice([1.5, 2, 2.5, 3])
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=(255, 235, 255, rnd.randint(90, 220)))

    cx, cy = 512, 590
    # свечение
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(P(cx - 300, cy - 300, cx + 300, cy + 300), fill=(255, 110, 170, 140))
    scene.alpha_composite(glow.filter(ImageFilter.GaussianBlur(80 * k)))

    # круг подхода
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse(P(cx - 300, cy - 300, cx + 300, cy + 300), outline=(255, 170, 120, 255), width=int(16 * k))
    scene.alpha_composite(ring)

    # кружок с градиентом
    r = 200
    disc = vgradient((S, S), (255, 120, 170), (217, 119, 87))
    dm = Image.new("L", (S, S), 0)
    ImageDraw.Draw(dm).ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=255)
    scene.paste(disc, (0, 0), dm)
    d = ImageDraw.Draw(scene)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 255), width=int(22 * k))
    f = font(230 * k)
    d.text((cx * k, (cy + 6) * k), "1", font=f, fill=(255, 255, 255, 255), anchor="mm")

    # ноты
    def note(x, y, s, color):
        d.ellipse(P(x - 34 * s, y - 24 * s, x + 34 * s, y + 24 * s), fill=color)
        d.rectangle(P(x + 22 * s, y - 150 * s, x + 34 * s, y), fill=color)
        d.polygon(P(x + 22 * s, y - 150 * s, x + 90 * s, y - 110 * s, x + 90 * s, y - 80 * s, x + 34 * s, y - 112 * s), fill=color)

    note(205, 560, 0.7, (255, 200, 230, 255))
    note(805, 560, 0.55, (160, 150, 255, 255))
    note(250, 860, 0.5, (255, 170, 120, 230))

    inner = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    idr = ImageDraw.Draw(inner)
    idr.polygon(P(196, 330, 236, 160, 372, 262), fill=(255, 140, 190, 255))
    idr.polygon(P(828, 330, 788, 160, 652, 262), fill=(255, 140, 190, 255))
    inner = Image.composite(inner, Image.new("RGBA", (S, S), (0, 0, 0, 0)), rounded(inner.split()[3], 10 * k))
    scene.alpha_composite(inner)

    art = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    art.paste(scene, (0, 0), mask)
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    rim.paste((255, 220, 255, 90), (0, 0), mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(2 * k)))
    art.alpha_composite(rim)

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((20, 0, 40, 110), (0, int(18 * k)), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26 * k))
    shadow.alpha_composite(art)
    shadow.resize((1024, 1024), Image.LANCZOS).save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("icon-1024.png")))

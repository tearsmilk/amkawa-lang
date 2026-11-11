#!/usr/bin/env python3
"""Иконка TnQkoTweaks: кошачий силуэт серии TnQko, внутри — три ползунка настроек."""
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

    # три ползунка
    tracks = [(430, (143, 217, 191)), (585, (243, 191, 211)), (740, (200, 194, 240))]
    knobs = [640, 380, 560]
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (y, col), kx in zip(tracks, knobs):
        gd.ellipse(P(kx - 90, y - 90, kx + 90, y + 90), fill=col + (120,))
    scene.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40 * k)))
    d = ImageDraw.Draw(scene)
    for (y, col), kx in zip(tracks, knobs):
        d.rounded_rectangle(P(220, y - 16, 804, y + 16), radius=16 * k, fill=(255, 255, 255, 60))
        d.rounded_rectangle(P(220, y - 16, kx, y + 16), radius=16 * k, fill=col + (255,))
        d.ellipse(P(kx - 58, y - 58, kx + 58, y + 58), fill=(255, 255, 255, 255))
        d.ellipse(P(kx - 36, y - 36, kx + 36, y + 36), fill=col + (255,))

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

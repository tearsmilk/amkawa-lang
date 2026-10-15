"""Built-in palettes and palette files (.gpl GIMP, .hex, .pal JASC)."""
from pathlib import Path

PRESETS = {
    "DB32": "000000 222034 45283c 663931 8f563b df7126 d9a066 eec39a fbf236 99e550 6abe30 37946e 4b692f 524b24 323c39 "
            "3f3f74 306082 5b6ee1 639bff 5fcde4 cbdbfc ffffff 9badb7 847e87 696a6a 595652 76428a ac3232 d95763 d77bba "
            "8f974a 8a6f30",
    "PICO-8": "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa",
    "Sweetie 16": "1a1c2c 5d275d b13e53 ef7d57 ffcd75 a7f070 38b764 257179 29366f 3b5dc9 41a6f6 73eff7 f4f4f4 94b0c2 566c86 333c57",
    "Endesga 32": "be4a2f d77643 ead4aa e4a672 b86f50 733e39 3e2731 a22633 e43b44 f77622 feae34 fee761 63c74d 3e8948 265c42 "
                  "193c3e 124e89 0099db 2ce8f5 ffffff c0cbdc 8b9bb4 5a6988 3a4466 262b44 181425 ff0044 68386c b55088 "
                  "f6757a e8b796 c28569",
    "Game Boy": "0f380f 306230 8bac0f 9bbc0f",
    "Claude": "141413 3d3d3a 6f6e69 a8a59c e3dfd3 f0eee6 faf9f5 ffffff 5c2a1a 9a3f24 c6613f d97757 e8a487 f6ded3 "
              "3e8e63 7bb487 2e5e9e 8fb5e8 8a4fc2 c3a6f0 b5862e e2c27a",
    "Оттенки серого": " ".join(f"{v:02x}{v:02x}{v:02x}" for v in range(0, 256, 17)),
}


def preset(name):
    return [0xFF000000 | int(h, 16) for h in PRESETS.get(name, PRESETS["DB32"]).split()]


def load(path):
    path = Path(path)
    text = path.read_text("utf-8", errors="replace")
    colors = []
    ext = path.suffix.lower()
    if ext == ".gpl":
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] in "#" or line.startswith(("GIMP", "Name:", "Columns:")):
                continue
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                r, g, b = (int(p) for p in parts[:3])
                colors.append(0xFF000000 | (r << 16) | (g << 8) | b)
    elif ext == ".pal" and text.startswith("JASC-PAL"):
        for line in text.splitlines()[3:]:
            parts = line.split()
            if len(parts) >= 3:
                r, g, b = (int(p) for p in parts[:3])
                colors.append(0xFF000000 | (r << 16) | (g << 8) | b)
    else:  # .hex: one RRGGBB per line
        for line in text.split():
            line = line.strip().lstrip("#")
            if len(line) in (6, 8):
                try:
                    v = int(line, 16)
                except ValueError:
                    continue
                colors.append(v if len(line) == 8 else 0xFF000000 | v)
    if not colors:
        raise ValueError("В файле не найдено цветов")
    return colors


def save(path, colors, name="Дзета"):
    path = Path(path)
    if path.suffix.lower() == ".gpl":
        lines = ["GIMP Palette", f"Name: {name}", "Columns: 8", "#"]
        for c in colors:
            lines.append(f"{(c >> 16) & 255:3d} {(c >> 8) & 255:3d} {c & 255:3d}\t#{c & 0xFFFFFF:06x}")
        path.write_text("\n".join(lines) + "\n", "utf-8")
    else:
        path.write_text("\n".join(f"{c & 0xFFFFFF:06x}" for c in colors) + "\n", "utf-8")

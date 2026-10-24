"""Playable maps («Мир», continents, countries): a bbox plus the ISO codes whose polygons count as land."""
from . import geo

CONTINENTS = {"Asia": "Азия", "Europe": "Европа", "Africa": "Африка", "North America": "Северная Америка",
              "South America": "Южная Америка", "Oceania": "Океания"}

REGIONS = [
    ("world", "Мир", [-180, -56, 180, 78], None),
    ("europe", "Европа", [-25, 34, 45, 72], {"continent": "Europe"}),
    ("russia", "Россия", [19, 41, 180, 78], {"iso": ["RU"]}),
    ("usa", "США", [-125, 24, -66, 49], {"iso": ["US"]}),
    ("asia", "Азия", [25, -11, 150, 60], {"continent": "Asia"}),
    ("south_america", "Южная Америка", [-82, -56, -34, 13], {"continent": "South America"}),
    ("north_america", "Северная Америка", [-170, 7, -52, 72], {"continent": "North America"}),
    ("africa", "Африка", [-18, -35, 52, 38], {"continent": "Africa"}),
    ("oceania", "Океания", [112, -48, 180, 0], {"continent": "Oceania"}),
]


class Area:
    def __init__(self, key, name, bbox, isos, kind="region"):
        self.key, self.name, self.bbox, self.isos, self.kind = key, name, list(bbox), set(isos), kind
        self.size_km = max(500.0, geo.bbox_diagonal_km(self.bbox))

    def random_point(self, rng):
        res = geo.random_land_point(geo.countries(), self.isos, self.bbox, rng)
        if not res:
            raise ValueError(f"На карте «{self.name}» нет суши")
        return res


def _isos(spec):
    cs = geo.countries()
    if spec is None:
        return [c["iso"] for c in cs.items if c["continent"] not in ("Antarctica", "Seven seas (open ocean)")]
    if "iso" in spec:
        return spec["iso"]
    return [c["iso"] for c in cs.items if c["continent"] == spec["continent"]]


def regions():
    return [Area(k, n, b, _isos(spec)) for k, n, b, spec in REGIONS]


def country_area(iso):
    c = geo.countries().by_iso.get(iso)
    if not c:
        return None
    w, s, e, n = c["bbox"]
    pad = 0.05
    return Area(f"c:{iso}", c["name"], [w - pad, s - pad, e + pad, n + pad], [iso], kind="country")


def all_areas():
    """Regions first, then every country alphabetically (Russian names)."""
    out = regions()
    for name, iso in geo.countries().names():
        out.append(country_area(iso))
    return out


def area(key):
    for a in regions():
        if a.key == key:
            return a
    if key.startswith("c:"):
        return country_area(key[2:]) or regions()[0]
    return regions()[0]

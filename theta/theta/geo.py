"""Geometry: great-circle distance, point-in-polygon on the bundled Natural Earth countries, Web-Mercator tile math,
distance formatting."""
import json
import math
import random
from functools import lru_cache

from .paths import resource_path

EARTH_KM = 6371.0088
TILE = 256


def haversine(lat1, lon1, lat2, lon2):
    """Distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def fmt_distance(km):
    if km < 1:
        return f"{int(round(km * 1000))} м"
    if km < 10:
        return f"{km:.1f} км".replace(".", ",")
    return f"{int(round(km)):,} км".replace(",", " ")


def point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < x:
                inside = not inside
        j = i
    return inside


def in_bbox(lon, lat, bbox):
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


class Countries:
    """Bundled Natural Earth 110m admin-0 polygons: {iso, name (ru), en, continent, bbox, polys}."""

    def __init__(self, items):
        self.items = items
        self.by_iso = {c["iso"]: c for c in items}

    @classmethod
    def load(cls, path=None):
        path = path or resource_path("assets", "countries.json")
        return cls(json.loads(path.read_text("utf-8")))

    def contains(self, country, lat, lon):
        if not in_bbox(lon, lat, country["bbox"]):
            return False
        return any(point_in_ring(lon, lat, ring) for ring in country["polys"])

    def find(self, lat, lon):
        for c in self.items:
            if self.contains(c, lat, lon):
                return c
        return None

    def names(self):
        return sorted(((c["name"], c["iso"]) for c in self.items), key=lambda x: x[0])


@lru_cache(maxsize=1)
def countries():
    return Countries.load()


def random_land_point(countries_, isos, bbox, rng, tries=4000):
    """Random point inside one of the countries (iso codes) and the bbox; None when nothing fits."""
    w, s, e, n = bbox
    cands = [countries_.by_iso[i] for i in isos if i in countries_.by_iso]
    for _ in range(tries):
        lon, lat = rng.uniform(w, e), rng.uniform(s, n)
        for c in cands:
            if countries_.contains(c, lat, lon):
                return lat, lon, c
    return None


# ---- Web Mercator

def lonlat_to_world(lon, lat, zoom):
    """Pixel coordinates in the world image at this zoom (256·2^z wide)."""
    size = TILE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * size
    lat = max(-85.0511, min(85.0511, lat))
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * size
    return x, y


def world_to_lonlat(x, y, zoom):
    size = TILE * (2 ** zoom)
    lon = x / size * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / size))))
    return lon, lat


def tile_url(z, x, y):
    n = 2 ** z
    x %= n
    return f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def bbox_diagonal_km(bbox):
    w, s, e, n = bbox
    return haversine(s, w, n, e)


def seeded(seed):
    return random.Random(seed)

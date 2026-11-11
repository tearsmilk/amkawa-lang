"""Imagery sources. A Location is one playable spot: coordinates plus one or more images (a 360° panorama or a
flat photo), where it came from and whom to credit. Sources run in worker threads (no Qt here)."""
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import net
from ..paths import cache_dir


class SourceError(Exception):
    pass


@dataclass
class Location:
    lat: float
    lon: float
    url: str                      # best image url
    pano: bool = False
    source: str = ""
    attribution: str = ""
    heading: float = 0.0          # compass angle of the image centre (degrees, 0 = north)
    id: str = ""
    seq: str = ""                 # sequence id (Mapillary) for movement
    extra: dict = field(default_factory=dict)
    path: str = ""                # local cached file once downloaded

    def to_dict(self):
        return {"lat": self.lat, "lon": self.lon, "url": self.url, "pano": self.pano, "source": self.source,
                "attribution": self.attribution, "heading": self.heading, "id": self.id, "seq": self.seq}


class Source:
    name = ""
    title = ""
    moves = False

    def __init__(self, settings):
        self.settings = settings

    def available(self):
        return True

    def hint(self):
        return ""

    def pick(self, area, rng):
        raise NotImplementedError

    def neighbors(self, loc):
        """(prev, next) Locations along the capture sequence, None when unknown."""
        return None, None


class ImageCache:
    """Downloaded photos under <data>/cache/images, trimmed to `cache_mb` (oldest access first)."""

    def __init__(self, settings):
        self.settings = settings
        self.folder = cache_dir() / "images"
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, url):
        return self.folder / (hashlib.sha1(url.encode()).hexdigest()[:24] + ".img")

    def fetch(self, url, cancel=None):
        p = self.path(url)
        if p.exists() and p.stat().st_size > 0:
            os.utime(p, None)
            return p
        net.download(url, p, timeout=60, cancel=cancel)
        self.trim()
        return p

    def trim(self):
        limit = max(50, int(self.settings.get("cache_mb") or 500)) * 1024 * 1024
        files = sorted(self.folder.glob("*.img"), key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        while files and total > limit:
            f = files.pop(0)
            total -= f.stat().st_size
            f.unlink(missing_ok=True)

    def size(self):
        return sum(f.stat().st_size for f in self.folder.glob("*.img"))

    def clear(self):
        for f in self.folder.glob("*.img"):
            f.unlink(missing_ok=True)
        tiles = cache_dir() / "tiles"
        if tiles.exists():
            for f in tiles.rglob("*.png"):
                f.unlink(missing_ok=True)


def by_name(name, settings):
    from . import commons, mapillary, streetview

    if name == "commons":
        return commons.CommonsSource(settings)
    if name == "mapillary":
        return mapillary.MapillarySource(settings)
    return streetview.StreetViewSource(settings)


def all_sources(settings):
    from . import commons, mapillary, streetview

    return [streetview.StreetViewSource(settings), mapillary.MapillarySource(settings), commons.CommonsSource(settings)]


def default_source(settings):
    """Street View when a Google key exists, else Mapillary with a token, else Commons."""
    for s in all_sources(settings):
        if s.available():
            return s.name
    return "commons"


def now():
    return time.time()

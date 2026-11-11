"""Wikimedia Commons: geotagged photos near a point (no token). Commons asks for attribution — the author and
licence are shown over the picture."""
import html
import re

from .. import __version__, net
from . import Location, Source, SourceError

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": f"Theta/{__version__} (mc-ru.org; local GeoGuessr-like game)"}
BAD_WORDS = ("map", "карта", "diagram", "logo", "flag", "coat of arms", "plan", "document", "scan", "chart", "stamp",
             "poster", "icon", "svg", "drawing", "painting")


def _plain(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def normalize(page):
    info = (page.get("imageinfo") or [{}])[0]
    coords = (page.get("coordinates") or [{}])[0]
    meta = info.get("extmetadata") or {}
    w, h = int(info.get("width") or 0), int(info.get("height") or 0)
    title = page.get("title", "")
    cats = (meta.get("Categories", {}).get("value") or "") + " " + title
    if w < 1200 or h < 500 or w < h or not coords.get("lat"):
        return None
    if any(b in cats.lower() for b in BAD_WORDS):
        return None
    author = _plain(meta.get("Artist", {}).get("value", "")) or "автор неизвестен"
    lic = _plain(meta.get("LicenseShortName", {}).get("value", ""))
    url = info.get("thumburl") or info.get("url") or ""
    if not url:
        return None
    return Location(lat=float(coords["lat"]), lon=float(coords["lon"]), url=url, pano=False, source="commons",
                    attribution=f"{author} · {lic} · Wikimedia Commons".strip(" ·"),
                    id=str(page.get("pageid") or ""), extra={"title": title[5:] if title.startswith("File:") else title})


def search(lat, lon, radius_m=10000, limit=50):
    params = {"action": "query", "generator": "geosearch", "ggscoord": f"{lat:.5f}|{lon:.5f}",
              "ggsradius": int(min(10000, radius_m)), "ggslimit": limit, "ggsnamespace": 6,
              "prop": "imageinfo|coordinates", "iiprop": "url|extmetadata|size", "iiurlwidth": 2048, "format": "json"}
    data = net.get_json(API, params=params, headers=HEADERS)
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        loc = normalize(page)
        if loc:
            out.append(loc)
    return out


class CommonsSource(Source):
    name = "commons"
    title = "Wikimedia Commons — фотографии мест"
    moves = False

    def pick(self, area, rng, points=10):
        last = None
        for _ in range(points):
            lat, lon, _c = area.random_point(rng)
            try:
                found = search(lat, lon)
            except net.NetError as e:
                last = e
                continue
            if found:
                return rng.choice(found)
        raise SourceError("Не нашли фотографий в этом районе" + (f" ({last})" if last else "") + " — попробуйте другую карту")

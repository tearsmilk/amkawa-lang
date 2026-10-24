"""Mapillary Graph API v4: street-level photos and 360° panoramas inside a bbox, plus the capture sequence for
moving forward / back. Needs a free client token (mapillary.com/dashboard/developers)."""
from .. import net
from . import Location, Source, SourceError

API = "https://graph.mapillary.com"
FIELDS = "id,thumb_1024_url,thumb_2048_url,computed_geometry,geometry,is_pano,compass_angle,sequence,captured_at"
RADII = (0.05, 0.2, 0.6, 1.5, 3.0)      # degrees, widened until something is found


def normalize(item):
    geom = item.get("computed_geometry") or item.get("geometry") or {}
    coords = geom.get("coordinates") or [0, 0]
    url = item.get("thumb_2048_url") or item.get("thumb_1024_url") or ""
    return Location(lat=float(coords[1]), lon=float(coords[0]), url=url, pano=bool(item.get("is_pano")),
                    source="mapillary", attribution="Mapillary · CC BY-SA 4.0", heading=float(item.get("compass_angle") or 0),
                    id=str(item.get("id") or ""), seq=str(item.get("sequence") or ""),
                    extra={"captured_at": item.get("captured_at")})


def search_bbox(token, bbox, pano=True, limit=50):
    w, s, e, n = bbox
    params = {"access_token": token, "fields": FIELDS, "bbox": f"{w:.5f},{s:.5f},{e:.5f},{n:.5f}", "limit": limit}
    if pano:
        params["is_pano"] = "true"
    data = net.get_json(f"{API}/images", params=params)
    return [normalize(i) for i in data.get("data") or [] if i.get("thumb_2048_url") or i.get("thumb_1024_url")]


def image(token, image_id):
    data = net.get_json(f"{API}/{image_id}", params={"access_token": token, "fields": FIELDS})
    return normalize(data)


def sequence_ids(token, seq):
    data = net.get_json(f"{API}/image_ids", params={"access_token": token, "sequence_id": seq})
    return [str(d["id"]) for d in data.get("data") or []]


class MapillarySource(Source):
    name = "mapillary"
    title = "Mapillary — панорамы улиц"
    moves = True

    def token(self):
        return (self.settings.get("mapillary_token") or "").strip()

    def available(self):
        return bool(self.token())

    def hint(self):
        return "Нужен бесплатный токен: mapillary.com → Developers → Register application → Client token; вставьте его в Настройках."

    def pick(self, area, rng, points=6):
        token = self.token()
        if not token:
            raise SourceError("Нет токена Mapillary — добавьте его в Настройках")
        last = None
        for _ in range(points):
            lat, lon, _c = area.random_point(rng)
            for r in RADII:
                bbox = (lon - r, lat - r, lon + r, lat + r)
                try:
                    found = search_bbox(token, bbox, pano=True)
                    if not found and r >= RADII[2]:
                        found = search_bbox(token, bbox, pano=False)
                except net.NetError as e:
                    last = e
                    if "401" in str(e) or "403" in str(e) or "400" in str(e):
                        raise SourceError("Mapillary не принял токен — проверьте его в Настройках") from e
                    break
                found = [f for f in found if f.url]
                if found:
                    found.sort(key=lambda f: (not f.pano, rng.random()))
                    best = found[0]
                    return best
        raise SourceError("Не нашли снимков в этом районе" + (f" ({last})" if last else "") + " — попробуйте другую карту")

    def neighbors(self, loc):
        token = self.token()
        if not token or not loc.seq or not loc.id:
            return None, None
        ids = sequence_ids(token, loc.seq)
        if loc.id not in ids:
            return None, None
        i = ids.index(loc.id)
        prev = image(token, ids[i - 1]) if i > 0 else None
        nxt = image(token, ids[i + 1]) if i + 1 < len(ids) else None
        return prev, nxt

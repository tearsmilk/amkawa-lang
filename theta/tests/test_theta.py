"""Headless checks against a local fake of every service: Mapillary (search / sequence), Wikimedia Commons
(geosearch), Google Street View metadata, OSM tiles and the images themselves. Run from theta/:
`python -m tests.test_theta` or via `run.py --selftest`."""
import http.server
import io
import json
import random
import tempfile
import threading
import urllib.parse
from pathlib import Path


def _png(w, h, color):
    from PySide6.QtGui import QColor, QImage, QPainter

    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    p = QPainter(img)
    p.fillRect(0, 0, w // 2, h // 2, QColor("#D97757"))
    p.end()
    buf = io.BytesIO()
    from PySide6.QtCore import QBuffer, QIODevice

    qb = QBuffer()
    qb.open(QIODevice.WriteOnly)
    img.save(qb, "PNG")
    buf.write(bytes(qb.data()))
    return buf.getvalue()


class Fake(http.server.BaseHTTPRequestHandler):
    calls = []
    pano_png = b""
    flat_png = b""
    tile_png = b""

    def log_message(self, *_):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data, ctype="image/png"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        Fake.calls.append(u.path)
        base = f"http://{self.headers['Host']}"
        if u.path == "/mly/images":
            w, s, e, n = map(float, q["bbox"][0].split(","))
            if e - w < 0.3:          # small bbox → nothing, forces widening
                return self._json({"data": []})
            pano = q.get("is_pano", ["false"])[0] == "true"
            lat, lon = (s + n) / 2, (w + e) / 2
            return self._json({"data": [{"id": "101", "thumb_2048_url": base + "/img/pano.png", "is_pano": pano,
                                         "compass_angle": 90.0, "sequence": "seqA", "captured_at": 1,
                                         "computed_geometry": {"type": "Point", "coordinates": [lon, lat]}},
                                        {"id": "102", "thumb_1024_url": base + "/img/flat.png", "is_pano": False,
                                         "sequence": "seqA", "geometry": {"type": "Point", "coordinates": [lon + 0.001, lat]}}]})
        if u.path == "/mly/image_ids":
            return self._json({"data": [{"id": "100"}, {"id": "101"}, {"id": "102"}]})
        if u.path.startswith("/mly/"):
            iid = u.path.rsplit("/", 1)[1]
            return self._json({"id": iid, "thumb_2048_url": base + "/img/flat.png", "is_pano": False, "sequence": "seqA",
                               "geometry": {"type": "Point", "coordinates": [37.6, 55.75]}})
        if u.path == "/commons":
            lat, lon = map(float, q["ggscoord"][0].split("|"))
            return self._json({"query": {"pages": {
                "1": {"pageid": 1, "title": "File:Nice view.jpg", "coordinates": [{"lat": lat, "lon": lon}],
                      "imageinfo": [{"thumburl": base + "/img/flat.png", "width": 2000, "height": 1200,
                                     "extmetadata": {"Artist": {"value": "<a href=x>Ivan</a>"}, "LicenseShortName": {"value": "CC BY 4.0"}}}]},
                "2": {"pageid": 2, "title": "File:Map of town.png", "coordinates": [{"lat": lat, "lon": lon}],
                      "imageinfo": [{"thumburl": base + "/img/flat.png", "width": 2000, "height": 1200, "extmetadata": {}}]},
                "3": {"pageid": 3, "title": "File:Small.jpg", "coordinates": [{"lat": lat, "lon": lon}],
                      "imageinfo": [{"thumburl": base + "/img/flat.png", "width": 600, "height": 400, "extmetadata": {}}]}}}})
        if u.path == "/svmeta":
            lat, lon = map(float, q["location"][0].split(","))
            if int(q["radius"][0]) < 15000:
                return self._json({"status": "ZERO_RESULTS"})
            if q["key"][0] == "bad":
                return self._json({"status": "REQUEST_DENIED", "error_message": "The provided API key is invalid."})
            return self._json({"status": "OK", "pano_id": "PANO123", "copyright": "© Google", "date": "2021-05",
                               "location": {"lat": lat + 0.01, "lng": lon - 0.01}})
        if u.path.startswith("/tiles/"):
            return self._bytes(Fake.tile_png)
        if u.path == "/img/pano.png":
            return self._bytes(Fake.pano_png)
        if u.path == "/img/flat.png":
            return self._bytes(Fake.flat_png)
        self._json({"error": "nope"}, 404)


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def run(tmp=None, with_webengine=True):
    from theta import game as gamemod
    from theta import geo, maps, net
    from theta.paths import Settings
    from theta.sources import ImageCache, SourceError, commons, mapillary, streetview

    Fake.pano_png, Fake.flat_png, Fake.tile_png = _png(512, 256, "#5B8CC4"), _png(640, 400, "#7BA05B"), _png(256, 256, "#E6ECF0")
    httpd, base = serve()
    saved = (mapillary.API, commons.API, streetview.META, geo.tile_url)
    mapillary.API, commons.API, streetview.META = base + "/mly", base + "/commons", base + "/svmeta"
    geo.tile_url = lambda z, x, y: f"{base}/tiles/{z}/{x}/{y}.png"
    calls = 0
    try:
        # scoring
        assert gamemod.score(0, 14000) == 5000 and gamemod.score(1400, 14000) == int(round(5000 * 2.718281828 ** -1))
        assert gamemod.score(20000, 14000) < 5 and 0 < gamemod.score(500, 1000) < 5000
        # distances & formatting
        assert abs(geo.haversine(55.7558, 37.6173, 59.9343, 30.3351) - 634) < 5
        assert geo.fmt_distance(0.4) == "400 м" and geo.fmt_distance(4.26) == "4,3 км" and geo.fmt_distance(1234.4) == "1 234 км"
        # point in polygon on known cities
        cs = geo.countries()
        assert cs.find(55.75, 37.62)["iso"] == "RU" and cs.find(48.86, 2.35)["iso"] == "FR"
        assert cs.find(40.71, -74.0)["iso"] == "US" and cs.find(-33.87, 151.21)["iso"] == "AU"
        assert cs.find(0.0, -140.0) is None    # Pacific
        # areas pick land only
        rng = random.Random(7)
        ru = maps.area("russia")
        for _ in range(10):
            lat, lon, c = ru.random_point(rng)
            assert c["iso"] == "RU" and cs.find(lat, lon)["iso"] == "RU"
        eu = maps.area("europe")
        assert eu.size_km > 3000 and "FR" in eu.isos and "RU" not in {c for c in eu.isos if c == "US"}
        assert maps.area("c:JP").name == "Япония" and maps.area("nope").key == "world"
        # tile math round-trip
        x, y = geo.lonlat_to_world(37.6, 55.75, 10)
        lon, lat = geo.world_to_lonlat(x, y, 10)
        assert abs(lon - 37.6) < 1e-6 and abs(lat - 55.75) < 1e-6
        assert saved[3](3, 9, 2) == "https://tile.openstreetmap.org/3/1/2.png"   # x wraps
        s = Settings(Path(tmp or tempfile.mkdtemp()) / "settings.json")
        s.update(mapillary_token="tok", google_key="good", cache_mb=50)
        # Mapillary: small bbox empty → widened → pano preferred; neighbours along the sequence
        src = mapillary.MapillarySource(s)
        loc = src.pick(maps.area("world"), random.Random(1))
        assert loc.pano and loc.id == "101" and loc.heading == 90 and loc.seq == "seqA" and loc.url.endswith("pano.png")
        prev, nxt = src.neighbors(loc)
        assert prev.id == "100" and nxt.id == "102" and not nxt.pano
        assert not mapillary.MapillarySource(Settings(Path(tempfile.mkdtemp()) / "s.json")).available()
        # Commons: filters maps / small pictures, keeps attribution
        found = commons.search(48.86, 2.35)
        assert len(found) == 1 and found[0].attribution.startswith("Ivan · CC BY 4.0") and found[0].extra["title"] == "Nice view.jpg"
        csrc = commons.CommonsSource(s)
        assert csrc.pick(maps.area("europe"), random.Random(2)).source == "commons" and not csrc.moves
        # Street View metadata: radius widening, official-only, bad key → clear error
        svs = streetview.StreetViewSource(s)
        loc2 = svs.pick(maps.area("usa"), random.Random(3))
        assert loc2.source == "streetview" and loc2.id == "PANO123" and loc2.extra["date"] == "2021-05" and not loc2.url
        assert streetview.normalize({"status": "ZERO_RESULTS"}) is None
        assert "pano=PANO123" in streetview.static_url("k", "PANO123", 90)
        s["google_key"] = "bad"
        try:
            svs.pick(maps.area("usa"), random.Random(3))
            raise AssertionError("bad key accepted")
        except SourceError as e:
            assert "REQUEST_DENIED" in str(e)
        s["google_key"] = "good"
        assert "<script" in streetview.page_html("k&k") and "k%26k" in streetview.page_html("k&k")
        # image cache: download, reuse, trim
        cache = ImageCache(s)
        p = cache.fetch(loc.url)
        assert p.exists() and cache.fetch(loc.url) == p and cache.size() > 0
        cache.clear()
        assert cache.size() == 0
        # a full classic game of 5 rounds through the controller (Mapillary fake), with preloading
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        runner = net.Runner(4)
        rec = gamemod.Records(Path(tmp or tempfile.mkdtemp()) / "records.json")
        s.update(mode="classic", map="world", source="mapillary", time_limit=0)
        cfg = gamemod.Config(s, seed=42)
        g = gamemod.Game(s, runner, cfg, rec)
        seen = {"ready": [], "done": [], "fin": None}
        g.round_ready.connect(lambda i, loc_, path: seen["ready"].append((i, loc_, path)))
        g.round_done.connect(lambda r: seen["done"].append(r))
        g.finished.connect(lambda sm: seen.__setitem__("fin", sm))
        g.failed.connect(lambda m: (_ for _ in ()).throw(AssertionError(m)))
        g.start()
        for round_ in range(5):
            _wait(app, lambda: len(seen["ready"]) == round_ + 1)
            i, loc_, path = seen["ready"][-1]
            assert i == round_ and Path(path).exists()
            res = g.guess(loc_.lat + 0.001, loc_.lon)        # ~100 m off → nearly full points
            assert res["score"] >= 4900 and res["distance"] < 0.2
            if round_ < 4:
                g.next_round()
        g.next_round()
        _wait(app, lambda: seen["fin"] is not None)
        fin = seen["fin"]
        assert fin["score"] == sum(r["score"] for r in fin["rounds"]) and len(fin["rounds"]) == 5 and fin["max"] == 25000
        assert rec.top("world", "classic")[0]["score"] == fin["score"] and rec.recent()[0]["seed"] == 42
        # streak mode ends on the first miss; daily is seeded by the date and recorded once
        cfg2 = gamemod.Config(s, mode="streak", seed=5)
        g2 = gamemod.Game(s, runner, cfg2, rec)
        seen2 = {"ready": [], "fin": None}
        g2.round_ready.connect(lambda i, loc_, path: seen2["ready"].append(loc_))
        g2.finished.connect(lambda sm: seen2.__setitem__("fin", sm))
        g2.start()
        _wait(app, lambda: len(seen2["ready"]) == 1)
        truth = geo.countries().find(seen2["ready"][0].lat, seen2["ready"][0].lon)
        assert g2.guess(iso=truth["iso"])["correct"] and g2.streak == 1
        g2.next_round()
        _wait(app, lambda: len(seen2["ready"]) == 2)
        assert not g2.guess(iso="ZZ")["correct"] and seen2["fin"] and seen2["fin"]["streak"] == 1
        d1, d2 = gamemod.Config(s, mode="daily"), gamemod.Config(s, mode="daily")
        assert d1.seed == d2.seed == gamemod.daily_seed() and d1.map_key == "world" and d1.time_limit == 0
        assert rec.daily_result() is None
        rec.set_daily(1234)
        assert rec.daily_result() == 1234
        # timeout without a guess scores 0
        cfg3 = gamemod.Config(s, seed=9)
        cfg3.time_limit = 30
        g3 = gamemod.Game(s, runner, cfg3, rec)
        got = []
        g3.round_ready.connect(lambda *a: got.append(a))
        g3.start()
        _wait(app, lambda: got)
        assert g3.time_left() is not None and g3.timeout()["score"] == 0
        # map widget renders offscreen with fake tiles and takes a guess
        from theta.map import SlippyMap, TileCache

        tiles = TileCache(runner)
        m = SlippyMap(tiles)
        m.resize(400, 300)
        m.set_view(55.75, 37.6, 5)
        m.grab()
        _wait(app, lambda: not tiles.pending, 10)
        assert tiles.mem and m.grab().width() == 400
        got_guess = []
        m.guessed.connect(lambda la, lo: got_guess.append((la, lo)))
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent

        pos = QPointF(200, 150)
        m.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        m.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        assert got_guess and abs(got_guess[0][0] - 55.75) < 0.5 and abs(got_guess[0][1] - 37.6) < 0.5
        m.truth = (55.0, 37.0)
        m.fit([m.guess, m.truth])
        assert m.grab().width() == 400
        # panorama viewer: load the fake equirect image, look around, compass follows heading
        from PySide6.QtGui import QImage
        from theta.pano import EquirectView, FlatView

        v = EquirectView()
        v.resize(480, 270)
        v.set_image(QImage(str(cache.fetch(loc.url))), heading=90)
        assert v.compass() == 90
        v.yaw = 45
        assert v.compass() == 135 and v.grab().width() == 480
        fv = FlatView()
        fv.resize(300, 200)
        fv.set_image(QImage(str(cache.fetch(found[0].url))))
        assert fv.grab().height() == 200
        calls = len(Fake.calls)
        # Street View panel (QtWebEngine) builds offscreen and accepts a pano before Maps is ready
        if with_webengine and streetview.webengine_available():
            panel = streetview.make_panel("k", None)
            panel.resize(320, 200)
            panel.show_pano("PANO123", {"move": True, "pan": True, "zoom": True})
            assert panel.pending == ("PANO123", {"move": True, "pan": True, "zoom": True})
            panel.bridge.message("maps", "ready")
            app.processEvents()
            assert panel.maps_ready and panel.pending is None
            panel.bridge.message("pano", json.dumps({"id": "PANO123"}))
            assert panel.current == "PANO123"
            msgs = []
            panel.failed.connect(msgs.append)
            panel.bridge.message("status", "ZERO_RESULTS")
            assert msgs and "ZERO_RESULTS" in msgs[0]
            panel.deleteLater()
        return {"calls": calls}
    finally:
        mapillary.API, commons.API, streetview.META, geo.tile_url = saved
        httpd.shutdown()


def _wait(app, cond, seconds=15):
    import time

    t0 = time.monotonic()
    while not cond():
        app.processEvents()
        time.sleep(0.005)
        if time.monotonic() - t0 > seconds:
            raise AssertionError("timeout waiting")


if __name__ == "__main__":
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    print(run())

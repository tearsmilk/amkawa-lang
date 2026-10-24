"""Google Street View: free Metadata API to find a panorama near a random point (pano_id only), then the real
interactive panorama in a QtWebEngine page with the Maps JavaScript API (that load is the only billable call,
≈ $14 per 1000 — the monthly $200 credit covers ≈ 14 000 rounds). Needs the user's own API key with the
Maps JavaScript API and Street View Static API enabled (console.cloud.google.com)."""
import json
import urllib.parse

from .. import net
from . import Location, Source, SourceError

META = "https://maps.googleapis.com/maps/api/streetview/metadata"
STATIC = "https://maps.googleapis.com/maps/api/streetview"
JS_API = "https://maps.googleapis.com/maps/api/js"
RADII_M = (5000, 15000, 50000)


def metadata(key, lat, lon, radius_m=50000, outdoor=True):
    params = {"location": f"{lat:.6f},{lon:.6f}", "radius": int(radius_m), "key": key}
    if outdoor:
        params["source"] = "outdoor"
    return net.get_json(META, params=params)


def normalize(meta):
    if (meta or {}).get("status") != "OK":
        return None
    loc = meta.get("location") or {}
    return Location(lat=float(loc.get("lat", 0)), lon=float(loc.get("lng", 0)), url="", pano=True,
                    source="streetview", attribution="© Google", id=str(meta.get("pano_id") or ""),
                    extra={"date": meta.get("date", ""), "copyright": meta.get("copyright", "")})


def static_url(key, pano_id, heading=0, size="640x400"):
    return STATIC + "?" + urllib.parse.urlencode({"size": size, "pano": pano_id, "heading": int(heading), "key": key})


class StreetViewSource(Source):
    name = "streetview"
    title = "Google Street View — интерактивные панорамы"
    moves = True

    def key(self):
        return (self.settings.get("google_key") or "").strip()

    def available(self):
        return bool(self.key())

    def hint(self):
        return ("Нужен свой ключ Google Maps Platform (console.cloud.google.com → API и сервисы → Учётные данные). "
                "Включите Maps JavaScript API и Street View Static API. Поиск точек бесплатный; показ панорамы ≈ $14 за "
                "1000 раундов, бесплатного кредита $200/мес хватает примерно на 14 000 раундов.")

    def pick(self, area, rng, points=12):
        key = self.key()
        if not key:
            raise SourceError("Нет ключа Google — добавьте его в Настройках")
        official = bool(self.settings.get("sv_official_only", True))
        last = None
        for _ in range(points):
            lat, lon, _c = area.random_point(rng)
            for r in RADII_M:
                try:
                    meta = metadata(key, lat, lon, r)
                except net.NetError as e:
                    last = e
                    break
                status = meta.get("status")
                if status in ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "INVALID_REQUEST"):
                    raise SourceError(f"Google отклонил запрос ({status}): {meta.get('error_message') or 'проверьте ключ и включённые API'}")
                loc = normalize(meta)
                if loc and (not official or "google" in (loc.extra.get("copyright") or "").lower()):
                    # the pano must still be on this map (the radius may have crossed a border)
                    if area.kind == "country" and not _inside(area, loc):
                        continue
                    return loc
        raise SourceError("Street View не нашёл панорам в этом районе" + (f" ({last})" if last else "") + " — попробуйте другую карту")

    def neighbors(self, loc):
        return None, None    # movement happens inside the Maps JS panorama itself


def _inside(area, loc):
    from .. import geo

    c = geo.countries().by_iso.get(next(iter(area.isos)))
    return bool(c) and geo.countries().contains(c, loc.lat, loc.lon)


# ---- the interactive panel (Qt WebEngine); optional at import time so the game runs without PySide6-Addons

def webengine_available():
    try:
        from PySide6 import QtWebChannel, QtWebEngineWidgets  # noqa: F401
        return True
    except ImportError:
        return False


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body,#pano{margin:0;height:100%;width:100%;background:#141413;overflow:hidden}
#msg{position:absolute;left:0;right:0;top:45%;text-align:center;color:#F4F2EC;font:15px Georgia,serif}</style>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head><body><div id="pano"></div><div id="msg">Загружаем панораму…</div>
<script>
var bridge = null, pano = null, opts = {move: true, pan: true, zoom: true}, startId = null, startPov = null;
function say(k, v) { if (bridge) bridge.message(k, typeof v === "string" ? v : JSON.stringify(v)); }
new QWebChannel(qt.webChannelTransport, function (ch) { bridge = ch.objects.bridge; say("channel", "ready"); });
function initMaps() {
  try {
    pano = new google.maps.StreetViewPanorama(document.getElementById("pano"), {
      addressControl: false, showRoadLabels: false, disableDefaultUI: true, motionTracking: false,
      motionTrackingControl: false, fullscreenControl: false, enableCloseButton: false, imageDateControl: false,
      linksControl: opts.move, clickToGo: opts.move, zoomControl: opts.zoom, scrollwheel: opts.zoom,
      panControl: false, visible: true });
    pano.addListener("pano_changed", function () { say("pano", {id: pano.getPano()}); document.getElementById("msg").style.display = "none"; });
    pano.addListener("status_changed", function () { say("status", pano.getStatus()); });
    pano.addListener("pov_changed", function () {
      if (!opts.pan && startPov) { var p = pano.getPov(); if (Math.abs(p.heading - startPov.heading) > 0.5 || Math.abs(p.pitch - startPov.pitch) > 0.5) pano.setPov(startPov); }
      if (!opts.zoom && pano.getZoom() !== 1) pano.setZoom(1);
    });
    say("maps", "ready");
  } catch (e) { say("error", String(e)); }
}
window.gm_authFailure = function () { say("error", "Google не принял ключ (gm_authFailure): проверьте ключ и Maps JavaScript API"); };
window.theta = {
  show: function (id, o) {
    opts = o || opts; startId = id; startPov = {heading: (o && o.heading) || 0, pitch: 0};
    if (!pano) { say("error", "Maps JS ещё не загружен"); return; }
    pano.setOptions({linksControl: opts.move, clickToGo: opts.move, zoomControl: opts.zoom, scrollwheel: opts.zoom});
    document.getElementById("msg").style.display = "block";
    pano.setPov(startPov); pano.setZoom(1); pano.setPano(id); pano.setVisible(true);
  },
  reset: function () { if (pano && startId) { pano.setPano(startId); pano.setPov(startPov); pano.setZoom(1); } },
  pov: function () { return pano ? JSON.stringify(pano.getPov()) : "{}"; }
};
</script>
<script async defer src="__API__?key=__KEY__&v=weekly&callback=initMaps&language=ru"
  onerror="say('error','Не удалось загрузить Maps JavaScript API')"></script>
</body></html>"""


def page_html(key):
    return PAGE.replace("__API__", JS_API).replace("__KEY__", urllib.parse.quote(key, safe=""))


def make_panel(key, parent=None):
    """StreetViewPanel or None when QtWebEngine is missing."""
    if not webengine_available():
        return None
    from PySide6.QtCore import QObject, QUrl, Signal, Slot
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineWidgets import QWebEngineView

    class Bridge(QObject):
        got = Signal(str, str)

        @Slot(str, str)
        def message(self, kind, value):
            self.got.emit(kind, value)

    class StreetViewPanel(QWebEngineView):
        pano_changed = Signal(str)
        failed = Signal(str)
        ready = Signal()

        def __init__(self, key, parent=None):
            super().__init__(parent)
            self.key = key
            self.bridge = Bridge(self)
            self.bridge.got.connect(self._message)
            self.channel = QWebChannel(self)
            self.channel.registerObject("bridge", self.bridge)
            self.page().setWebChannel(self.channel)
            self.maps_ready = False
            self.pending = None
            self.current = ""
            self.setHtml(page_html(key), QUrl("https://theta.local/"))

        def _message(self, kind, value):
            if kind == "maps":
                self.maps_ready = True
                self.ready.emit()
                if self.pending:
                    self.show_pano(*self.pending)
                    self.pending = None
            elif kind == "pano":
                try:
                    self.current = json.loads(value).get("id", "")
                except ValueError:
                    self.current = ""
                self.pano_changed.emit(self.current)
            elif kind == "status" and value not in ("OK", ""):
                self.failed.emit("Панорама недоступна: " + value)
            elif kind == "error":
                self.failed.emit(value)

        def show_pano(self, pano_id, opts):
            if not self.maps_ready:
                self.pending = (pano_id, opts)
                return
            self.page().runJavaScript(f"window.theta && window.theta.show({json.dumps(pano_id)}, {json.dumps(opts)})")

        def reset(self):
            self.page().runJavaScript("window.theta && window.theta.reset()")

    return StreetViewPanel(key, parent)

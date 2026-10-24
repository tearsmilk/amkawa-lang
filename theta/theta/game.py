"""Game rules: modes (classic, country streak, daily), scoring, the round loop with background location fetching
and preloading, local records."""
import datetime as dt
import math
import random
import time

from PySide6.QtCore import QObject, Signal

from . import geo, maps
from .paths import data_dir, load_json, save_json
from .sources import ImageCache, SourceError, by_name

MODES = {"classic": "Классика", "streak": "Страны подряд", "daily": "Задание дня"}
TIME_LIMITS = [(0, "Без ограничения"), (30, "30 секунд"), (60, "1 минута"), (120, "2 минуты")]
MAX_ROUND = 5000
ROUNDS = 5


def score(distance_km, size_km):
    """0–5000 points: full for < ~25 m, exponential decay scaled by the map's diagonal."""
    if distance_km < 0.025:
        return MAX_ROUND
    return int(round(MAX_ROUND * math.exp(-distance_km / (max(1.0, size_km) * 0.1))))


def daily_seed(day=None):
    day = day or dt.date.today()
    return f"theta-daily-{day.isoformat()}"


class Config:
    def __init__(self, settings, mode=None, map_key=None, seed=None, source=None):
        self.mode = mode or settings.get("mode") or "classic"
        self.map_key = map_key or settings.get("map") or "world"
        self.source = source or settings.get("source") or "streetview"
        self.time_limit = int(settings.get("time_limit") or 0)
        self.no_move = bool(settings.get("no_move"))
        self.no_pan = bool(settings.get("no_pan"))
        self.no_zoom = bool(settings.get("no_zoom"))
        self.rounds = ROUNDS if self.mode != "streak" else 10 ** 6
        if self.mode == "daily":
            self.map_key, self.seed, self.time_limit = "world", daily_seed(), 0
            self.no_move = self.no_pan = self.no_zoom = False
        else:
            self.seed = seed if seed is not None else random.randrange(1 << 62)
        self.area = maps.area(self.map_key)

    def opts(self):
        return {"move": not self.no_move, "pan": not self.no_pan, "zoom": not self.no_zoom}


class Records:
    def __init__(self, file=None):
        self.file = file or data_dir() / "records.json"
        self.data = load_json(self.file, {"games": [], "daily": {}})

    def save(self):
        save_json(self.file, self.data)

    def add(self, entry):
        self.data["games"].insert(0, entry)
        self.data["games"] = self.data["games"][:500]
        self.save()

    def top(self, map_key=None, mode=None, n=10):
        games = [g for g in self.data["games"] if (not map_key or g["map"] == map_key) and (not mode or g["mode"] == mode)]
        key = (lambda g: g.get("streak", 0)) if mode == "streak" else (lambda g: g["score"])
        return sorted(games, key=key, reverse=True)[:n]

    def recent(self, n=6):
        return self.data["games"][:n]

    def daily_result(self, day=None):
        return self.data["daily"].get((day or dt.date.today()).isoformat())

    def set_daily(self, score_, day=None):
        self.data["daily"][(day or dt.date.today()).isoformat()] = score_
        self.save()


class Game(QObject):
    """One game. Emits: loading(text), round_ready(index, Location, image_path|None), round_done(result dict),
    finished(summary dict), failed(text). Locations come from a worker thread via the runner; the next round is
    preloaded while the current one is played."""

    loading = Signal(str)
    round_ready = Signal(int, object, object)
    round_done = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, settings, runner, config, records, source=None):
        super().__init__()
        self.settings, self.runner, self.config, self.records = settings, runner, config, records
        self.source = source or by_name(config.source, settings)
        self.cache = ImageCache(settings)
        self.rng = random.Random(self.config.seed)
        self.rounds = []            # result dicts
        self.index = -1
        self.current = None         # (Location, path)
        self.preloaded = None
        self.pending = False
        self.started = 0.0
        self.streak = 0
        self.over = False

    # -- flow
    def start(self):
        self.next_round()

    def _fetch(self):
        loc = self.source.pick(self.config.area, self.rng)
        path = str(self.cache.fetch(loc.url)) if loc.url else None
        loc.path = path or ""
        return loc, path

    def next_round(self):
        if self.over:
            return
        self.index += 1
        if self.index >= self.config.rounds:
            self.finish()
            return
        if self.preloaded is not None:
            loc, path = self.preloaded
            self.preloaded = None
            self._begin(loc, path)
            return
        self.loading.emit("Ищем место…")
        self.runner.run(self._fetch, lambda r: self._begin(*r), self._fail)

    def _begin(self, loc, path):
        self.current = (loc, path)
        self.started = time.monotonic()
        self.round_ready.emit(self.index, loc, path)
        if self.index + 1 < self.config.rounds and not self.pending:
            self.pending = True
            self.runner.run(self._fetch, self._store_preload, lambda e: self._store_preload(None))

    def _store_preload(self, r):
        self.pending = False
        self.preloaded = r

    def _fail(self, e):
        self.failed.emit(str(e) if isinstance(e, (SourceError, Exception)) else "Не удалось загрузить место")

    def time_left(self):
        if not self.config.time_limit:
            return None
        return max(0.0, self.config.time_limit - (time.monotonic() - self.started))

    def guess(self, lat=None, lon=None, iso=None):
        """Classic/daily: a point. Streak: a country iso. Returns the result dict."""
        if self.current is None or self.over:
            return None
        loc, _ = self.current
        used = time.monotonic() - self.started
        res = {"round": self.index + 1, "lat": loc.lat, "lon": loc.lon, "pano": loc.id, "source": loc.source,
               "time": round(used, 1), "guess": None, "distance": None, "score": 0}
        truth = geo.countries().find(loc.lat, loc.lon)
        res["country"] = truth["name"] if truth else ""
        res["iso"] = truth["iso"] if truth else ""
        if self.config.mode == "streak":
            res["guess_iso"] = iso or ""
            res["correct"] = bool(iso) and bool(truth) and iso == truth["iso"]
            self.streak = self.streak + 1 if res["correct"] else 0
            res["streak"] = self.streak
            res["score"] = MAX_ROUND if res["correct"] else 0
        else:
            if lat is None:
                res["distance"] = None
                res["score"] = 0
            else:
                res["guess"] = (lat, lon)
                res["distance"] = geo.haversine(lat, lon, loc.lat, loc.lon)
                res["score"] = score(res["distance"], self.config.area.size_km)
        self.rounds.append(res)
        self.round_done.emit(res)
        if self.config.mode == "streak" and not res["correct"]:
            self.finish()
        return res

    def timeout(self):
        if self.config.mode == "streak":
            return self.guess(iso="")
        return self.guess()

    def total(self):
        return sum(r["score"] for r in self.rounds)

    def finish(self):
        if self.over:
            return
        self.over = True
        n = len(self.rounds)
        summary = {"mode": self.config.mode, "map": self.config.map_key, "map_name": self.config.area.name,
                   "score": self.total(), "max": MAX_ROUND * (n if self.config.mode != "streak" else 1), "rounds": self.rounds,
                   "streak": max([r.get("streak", 0) for r in self.rounds] or [0]), "source": self.config.source,
                   "nick": self.settings.get("nickname") or "Игрок", "date": time.time(), "seed": self.config.seed,
                   "time_limit": self.config.time_limit, "no_move": self.config.no_move}
        if n:
            self.records.add(summary)
            if self.config.mode == "daily":
                self.records.set_daily(summary["score"])
        self.finished.emit(summary)
        return summary

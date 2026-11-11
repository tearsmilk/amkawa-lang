"""Capture engine on top of the bundled static ffmpeg (avfoundation input on macOS).

* `Recorder` — one recording: screen (or a region of it) + 0..2 audio devices → temporary .mkv → remux to the
  chosen container when stopped (an .mkv survives a crash, mp4/mov are only written at the end).
* `ReplayBuffer` — the same capture written as short Matroska segments in a ring (`-f segment -segment_wrap`).
  `save()` waits for the "after" part, then cuts [press − before, press + after] out of the ring with a stream copy.

Everything is plain `subprocess` + polling from the Qt timer of the caller (`poll()`), so it is testable headless
with an `-f lavfi` source instead of a screen (see `CaptureSpec.source`)."""
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import cache_dir, resource_path

IS_MAC = sys.platform == "darwin"
QUALITY_BPP = (0.045, 0.07, 0.11, 0.18)  # bits per pixel per frame: Низкое, Среднее, Высокое, Максимум
QUALITY_CRF = (30, 25, 21, 17)
_POPEN = dict(stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
if sys.platform == "win32":
    _POPEN["creationflags"] = 0x08000000


def ffmpeg_exe():
    candidates = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(resource_path("ffmpeg", "ffmpeg"))
    if os.environ.get("GAMMA_FFMPEG"):
        candidates.append(Path(os.environ["GAMMA_FFMPEG"]))
    try:
        import imageio_ffmpeg

        candidates.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(Path(found))
    for c in candidates:
        if c and Path(c).is_file():
            if not os.access(c, os.X_OK):
                try:
                    os.chmod(c, 0o755)
                except OSError:
                    pass
            return str(c)
    return None


def run(args, timeout=60):
    """Run ffmpeg synchronously; returns (code, stderr text)."""
    exe = ffmpeg_exe()
    if not exe:
        return -1, "ffmpeg не найден"
    try:
        p = subprocess.run([exe, "-hide_banner", "-nostdin", *args], capture_output=True, timeout=timeout)
        return p.returncode, p.stderr.decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


_DEVICES = None


def list_devices(refresh=False):
    """{'video': [(index, name)], 'audio': [(index, name)]} from avfoundation (macOS only)."""
    global _DEVICES
    if _DEVICES is not None and not refresh:
        return _DEVICES
    out = {"video": [], "audio": []}
    if IS_MAC:
        _, err = run(["-f", "avfoundation", "-list_devices", "true", "-i", ""], timeout=15)
        kind = None
        for line in err.splitlines():
            if "video devices" in line:
                kind = "video"
            elif "audio devices" in line:
                kind = "audio"
            else:
                m = re.search(r"\]\s*\[(\d+)\]\s*(.+)$", line)
                if m and kind:
                    out[kind].append((int(m.group(1)), m.group(2).strip()))
    _DEVICES = out
    return out


def audio_devices():
    return [name for _, name in list_devices()["audio"]]


def screen_device(qt_index):
    """avfoundation video device index of 'Capture screen N' (same order as Qt / NSScreen: main display first)."""
    screens = [(i, n) for i, n in list_devices()["video"] if n.lower().startswith("capture screen")]
    for i, n in screens:
        if n.lower().endswith(f" {qt_index}"):
            return i
    return screens[0][0] if screens else None


def has_encoder(name):
    code, err = run(["-f", "lavfi", "-i", "color=black:s=64x64:r=5", "-frames:v", "3", "-c:v", name,
                     "-f", "null", "-"], timeout=30)
    return code == 0


@dataclass
class CaptureSpec:
    screen: int = 0                       # Qt screen index
    screen_size: tuple = (1920, 1080)     # logical size of that screen (points)
    dpr: float = 1.0                      # its device pixel ratio
    region: tuple = None                  # (x, y, w, h) in points relative to the screen, None = whole screen
    fps: int = 30
    quality: int = 2
    encoder: str = "hw"                   # "hw" (VideoToolbox) | "x264"
    max_height: int = 0
    cursor: bool = True
    clicks: bool = False
    audio: list = field(default_factory=list)   # avfoundation audio device names (0..2)
    source: list = None                   # tests / other platforms: ready-made ffmpeg input args instead of a screen
    source_audio: list = None             # …and their audio stream labels, e.g. ["1:a"]
    gop: float = 2.0                      # keyframe interval, s

    def pixel_size(self):
        w, h = (self.region[2], self.region[3]) if self.region else self.screen_size
        k = self.dpr
        if self.max_height and h * k > self.max_height:
            k = self.max_height / h
        return max(2, int(w * k) // 2 * 2), max(2, int(h * k) // 2 * 2)


def build_inputs(spec):
    """→ (input args, video label, [audio labels])."""
    if spec.source:
        return list(spec.source), "0:v", list(spec.source_audio or [])
    if not IS_MAC:
        raise RuntimeError("Запись экрана работает на macOS")
    dev = screen_device(spec.screen)
    if dev is None:
        raise RuntimeError("Экран для записи не найден. Разрешите Гамме запись экрана в Системных настройках.")
    args = ["-thread_queue_size", "1024", "-f", "avfoundation", "-capture_cursor", "1" if spec.cursor else "0",
            "-capture_mouse_clicks", "1" if spec.clicks else "0", "-framerate", str(spec.fps),
            "-pixel_format", "nv12"]
    names = dict((n, i) for i, n in list_devices()["audio"])
    audio = [names.get(a, a) for a in spec.audio[:2] if a]
    labels = []
    if audio:
        args += ["-i", f"{dev}:{audio[0]}"]
        labels.append("0:a")
        for k, a in enumerate(audio[1:], 1):
            args += ["-thread_queue_size", "1024", "-f", "avfoundation", "-i", f"none:{a}"]
            labels.append(f"{k}:a")
    else:
        args += ["-i", f"{dev}:none"]
    return args, "0:v", labels


def video_filter(spec):
    f = []
    if spec.region:
        sw, sh = spec.screen_size
        x, y, w, h = spec.region
        # in input pixels whatever the backing scale is: iw / sw = pixels per point
        f.append(f"crop=w=iw*{w}/{sw}:h=ih*{h}/{sh}:x=iw*{x}/{sw}:y=ih*{y}/{sh}")
    pw, ph = spec.pixel_size()
    f.append(f"scale={pw}:{ph}:flags=bicubic")
    f.append("format=yuv420p")
    return ",".join(f)


def encoder_args(spec):
    pw, ph = spec.pixel_size()
    q = max(0, min(3, spec.quality))
    gop = max(1, int(round(spec.fps * spec.gop)))
    if spec.encoder == "hw" and IS_MAC:
        kbps = int(pw * ph * spec.fps * QUALITY_BPP[q] / 1000)
        kbps = max(800, min(kbps, 80000))
        return ["-c:v", "h264_videotoolbox", "-allow_sw", "1", "-realtime", "1", "-profile:v", "high",
                "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.5)}k", "-bufsize", f"{kbps * 2}k", "-g", str(gop)]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(QUALITY_CRF[q]), "-pix_fmt", "yuv420p",
            "-g", str(gop), "-keyint_min", str(gop)]


def capture_args(spec):
    inputs, v, audio = build_inputs(spec)
    graph = [f"[{v}]{video_filter(spec)}[v]"]
    maps = ["-map", "[v]"]
    if len(audio) == 1:
        maps += ["-map", audio[0]]
    elif len(audio) > 1:
        graph.append("".join(f"[{a}]" for a in audio) + f"amix=inputs={len(audio)}:duration=longest:normalize=0[a]")
        maps += ["-map", "[a]"]
    args = inputs + ["-filter_complex", ";".join(graph)] + maps + encoder_args(spec)
    if audio:
        args += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    return args


def remux(src, dst, timeout=600):
    dst = Path(dst)
    extra = ["-movflags", "+faststart"] if dst.suffix.lower() in (".mp4", ".mov") else []
    return run(["-y", "-i", str(src), "-map", "0", "-c", "copy", *extra, str(dst)], timeout=timeout)


def thumbnail(video, out, at=0.5, width=360):
    code, _ = run(["-y", "-ss", str(at), "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2",
                   str(out)], timeout=30)
    if code != 0 or not Path(out).exists():
        code, _ = run(["-y", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", str(out)], timeout=30)
    return code == 0 and Path(out).exists()


def probe_duration(path):
    _, err = run(["-i", str(path)], timeout=20)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


class _Proc:
    """A running ffmpeg with stderr in a log file."""

    def __init__(self, args, log):
        exe = ffmpeg_exe()
        if not exe:
            raise RuntimeError("Не найден ffmpeg — переустановите Гамму")
        self.log = Path(log)
        self._fh = open(self.log, "wb")
        self.p = subprocess.Popen([exe, "-hide_banner", "-loglevel", "warning", *args], stderr=self._fh, **_POPEN)

    def alive(self):
        return self.p.poll() is None

    def stop(self, timeout=8.0):
        """Ask ffmpeg to finish the file ('q'), kill if it hangs; returns the exit code."""
        if self.alive():
            try:
                self.p.stdin.write(b"q")
                self.p.stdin.flush()
                self.p.stdin.close()
            except Exception:
                pass
            try:
                self.p.wait(timeout)
            except subprocess.TimeoutExpired:
                try:
                    self.p.send_signal(signal.SIGINT)
                    self.p.wait(3)
                except Exception:
                    self.p.kill()
                    self.p.wait()
        self._fh.close()
        return self.p.returncode

    def tail(self, n=6):
        try:
            lines = [ln for ln in self.log.read_text("utf-8", "replace").splitlines() if ln.strip()]
        except OSError:
            return ""
        return "\n".join(lines[-n:])


def explain(err):
    low = err.lower()
    if "permission" in low or "not authorized" in low or "screen capture" in low and "fail" in low:
        return "Нет доступа к записи экрана или микрофону — разрешите Гамме в Системных настройках → Защита и безопасность."
    if "input/output error" in low or "no such" in low:
        return "Устройство записи недоступно: " + err.strip().splitlines()[-1]
    return err.strip().splitlines()[-1] if err.strip() else "ffmpeg завершился с ошибкой"


class Recorder:
    """Single recording. start() → poll() regularly → stop() → final path (or error)."""

    def __init__(self, spec, out_path):
        self.spec = spec
        self.out = Path(out_path)
        self.tmp = self.out.with_name("." + self.out.stem + ".gamma.mkv")
        self.proc = None
        self.t0 = None
        self.error = None

    def start(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        args = ["-y", *capture_args(self.spec), "-f", "matroska", str(self.tmp)]
        self.proc = _Proc(args, cache_dir("logs") / "record.log")
        self.t0 = time.monotonic()

    def elapsed(self):
        return 0.0 if self.t0 is None else time.monotonic() - self.t0

    def poll(self):
        """False when ffmpeg died on its own (error set)."""
        if self.proc and not self.proc.alive():
            if self.error is None:
                self.error = explain(self.proc.tail())
            return False
        return True

    def stop(self):
        """Finish and remux; returns the final file path or None (self.error)."""
        if not self.proc:
            return None
        self.proc.stop()
        if not self.tmp.exists() or self.tmp.stat().st_size < 1000:
            self.error = self.error or explain(self.proc.tail())
            self.tmp.unlink(missing_ok=True)
            return None
        if self.out.suffix.lower() == ".mkv":
            os.replace(self.tmp, self.out)
            return self.out
        code, err = remux(self.tmp, self.out)
        if code != 0:
            # keep what was recorded rather than losing it
            fallback = self.out.with_suffix(".mkv")
            os.replace(self.tmp, fallback)
            return fallback
        self.tmp.unlink(missing_ok=True)
        return self.out

    def cancel(self):
        if self.proc:
            self.proc.stop(3)
        self.tmp.unlink(missing_ok=True)


class ReplayBuffer:
    """Ring of segments; save(before, after) → a clip with `before` seconds before the call and `after` after it."""

    def __init__(self, spec, keep_seconds, segment=10.0, folder=None, threaded=True):
        self.spec = spec
        self.seg = float(segment)
        self.dir = (Path(folder) if folder else cache_dir("replay")).resolve()
        self.wrap = int(math.ceil(keep_seconds / self.seg)) + 3
        self.proc = None
        self.entries = []          # [(name, start, end)] in buffer time, chronological
        self._list_pos = 0
        self.offset = None         # wall(monotonic) − buffer time, calibrated from finished segments
        self.t0 = None
        self.pending = []          # [{"press", "before", "after", "out", "cb"}]
        self.error = None
        self.threaded = threaded   # cut clips in a worker thread (cb is then called from that thread)

    # -- lifecycle
    def start(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.spec.gop = 1.0  # cut points are keyframes: 1 s precision
        args = ["-y", *capture_args(self.spec),
                "-force_key_frames", "expr:gte(t,n_forced*1)",
                "-f", "segment", "-segment_time", str(self.seg), "-segment_wrap", str(self.wrap),
                "-segment_format", "matroska", "-reset_timestamps", "1",
                "-segment_list", str(self.dir / "list.csv"), "-segment_list_type", "csv",
                str(self.dir / "seg%03d.mkv")]
        self.proc = _Proc(args, cache_dir("logs") / "replay.log")
        self.t0 = time.monotonic()

    def running(self):
        return self.proc is not None and self.proc.alive()

    def stop(self, flush=True):
        if self.proc:
            self.proc.stop(5)
        self._read_list()
        if flush:
            for job in list(self.pending):
                self._assemble(job)
        self.pending = []
        self.proc = None

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def buffered(self):
        """Seconds currently available in the ring."""
        if not self.entries:
            return 0.0 if self.t0 is None else min(time.monotonic() - self.t0, self.seg)
        first = self.entries[max(0, len(self.entries) - self.wrap + 1)][1]
        return self.entries[-1][2] - first + (time.monotonic() - self._wall(self.entries[-1][2]))

    # -- saving
    def save(self, before, after, out, cb=None):
        """Schedule a clip; cb(path_or_None, error) is called from poll() when it is written."""
        if self.offset is None and self.t0 is not None:
            self.offset = self.t0
        job = {"press": time.monotonic(), "before": float(before), "after": float(after), "out": Path(out), "cb": cb}
        self.pending.append(job)
        return job

    def remaining(self, job):
        return max(0.0, job["press"] + job["after"] - time.monotonic())

    def poll(self):
        if self.proc and not self.proc.alive() and self.error is None:
            self.error = explain(self.proc.tail())
        self._read_list()
        for job in list(self.pending):
            if not self.entries:
                continue
            end_needed = self._buf(job["press"]) + job["after"]
            if self.entries[-1][2] >= end_needed - 0.05 or not self.running():
                self._assemble(job)
        return self.error is None

    def _wall(self, t):
        return (self.offset if self.offset is not None else (self.t0 or 0.0)) + t

    def _buf(self, wall):
        return wall - (self.offset if self.offset is not None else (self.t0 or 0.0))

    def _read_list(self):
        path = self.dir / "list.csv"
        try:
            with open(path, "rb") as fh:
                fh.seek(self._list_pos)
                chunk = fh.read()
        except OSError:
            return
        if not chunk:
            return
        cut = chunk.rfind(b"\n") + 1
        self._list_pos += cut
        now = time.monotonic()
        for line in chunk[:cut].decode("utf-8", "replace").splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                name, start, end = parts[0], float(parts[1]), float(parts[2])
            except ValueError:
                continue
            self.entries.append((name, start, end))
            off = now - end
            self.offset = off if self.offset is None else min(self.offset, off)
        self.entries = self.entries[-(self.wrap * 4):]

    def _assemble(self, job):
        self.pending.remove(job)
        live = self.entries[-(self.wrap - 1):]  # older names were already overwritten by the ring
        t1 = self._buf(job["press"]) - job["before"]
        t2 = self._buf(job["press"]) + job["after"]
        use = [e for e in live if e[2] > t1 and e[1] < t2 and (self.dir / e[0]).exists()]
        if self.threaded and self.running():
            import threading

            threading.Thread(target=self._cut, args=(job, use, t1, t2), daemon=True).start()
        else:
            self._cut(job, use, t1, t2)

    def _cut(self, job, use, t1, t2):
        result, error = None, None
        if not use:
            error = "Буфер отката ещё пуст"
        else:
            listing = self.dir / f"concat-{int(job['press'] * 1000)}.txt"
            listing.write_text("ffconcat version 1.0\n" + "".join(f"file '{self.dir / e[0]}'\n" for e in use), "utf-8")
            skip = max(0.0, t1 - use[0][1])
            dur = min(t2, use[-1][2]) - max(t1, use[0][1])
            out = job["out"]
            out.parent.mkdir(parents=True, exist_ok=True)
            extra = ["-movflags", "+faststart"] if out.suffix.lower() in (".mp4", ".mov") else []
            code, err = run(["-y", "-ss", f"{skip:.3f}", "-f", "concat", "-safe", "0", "-i", str(listing),
                             "-t", f"{max(0.5, dur):.3f}", "-map", "0", "-c", "copy", *extra, str(out)],
                            timeout=300)
            listing.unlink(missing_ok=True)
            if code == 0 and out.exists():
                result = out
            else:
                error = explain(err)
        if job["cb"]:
            job["cb"](result, error)

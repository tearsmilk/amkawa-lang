"""Real-time audio engine: microphone -> voice -> virtual mic (Discord) + monitor (headphones)."""
import collections
import threading
import time

import numpy as np

from .voices import ENGINE_SR, Passthrough

try:
    import sounddevice as sd
except Exception as exc:  # PortAudio missing — the UI still opens and shows the error
    sd = None
    SD_ERROR = str(exc)
else:
    SD_ERROR = ""

CALLBACK_FRAMES = 480  # 10 ms
VIRTUAL_MIC_HINTS = ("amkawa", "blackhole", "loopback", "soundflower", "vb-cable", "cable input")


def list_devices():
    """Return (inputs, outputs) as lists of device names usable through CoreAudio."""
    if sd is None:
        return [], []
    inputs, outputs = [], []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return [], []
    preferred = None
    for i, api in enumerate(hostapis):
        if "core" in api["name"].lower():
            preferred = i
    for dev in devices:
        if preferred is not None and dev["hostapi"] != preferred:
            continue
        if dev["max_input_channels"] > 0:
            inputs.append(dev["name"])
        if dev["max_output_channels"] > 0:
            outputs.append(dev["name"])
    return inputs, outputs


def default_devices():
    if sd is None:
        return None, None
    try:
        inp, out = sd.default.device
        names = [d["name"] for d in sd.query_devices()]
        return (names[inp] if inp is not None and inp >= 0 else None,
                names[out] if out is not None and out >= 0 else None)
    except Exception:
        return None, None


def is_virtual_mic(name):
    low = (name or "").lower()
    return any(h in low for h in VIRTUAL_MIC_HINTS)


def _device_index(name, kind):
    if name is None:
        return None
    for i, dev in enumerate(sd.query_devices()):
        channels = dev["max_input_channels"] if kind == "input" else dev["max_output_channels"]
        if dev["name"] == name and channels > 0:
            return i
    raise RuntimeError(f"Устройство не найдено: {name}")


class Ring:
    """Thread-safe audio FIFO with priming (to absorb bursty producers) and latency cap."""

    def __init__(self):
        self.lock = threading.Lock()
        self.buf = np.zeros(0, dtype=np.float32)
        self.prime = CALLBACK_FRAMES * 2
        self.max_len = ENGINE_SR
        self.primed = False

    def configure(self, block_size):
        with self.lock:
            self.prime = block_size + CALLBACK_FRAMES * 4
            self.max_len = block_size * 3 + ENGINE_SR // 5
            self.buf = np.zeros(0, dtype=np.float32)
            self.primed = False

    def write(self, data):
        with self.lock:
            self.buf = np.concatenate([self.buf, data])
            if len(self.buf) > self.max_len:  # running behind: drop the oldest audio
                self.buf = self.buf[-self.prime:]

    def read(self, n):
        with self.lock:
            if not self.primed:
                if len(self.buf) < self.prime:
                    return np.zeros(n, dtype=np.float32)
                self.primed = True
            if len(self.buf) >= n:
                out, self.buf = self.buf[:n], self.buf[n:]
                return out
            out = np.zeros(n, dtype=np.float32)
            out[: len(self.buf)] = self.buf
            self.buf = np.zeros(0, dtype=np.float32)
            self.primed = False  # underrun: wait for a full block again
            return out

    def clear(self):
        with self.lock:
            self.buf = np.zeros(0, dtype=np.float32)
            self.primed = False


class AudioEngine:
    def __init__(self):
        self.voice = Passthrough()
        self.voice_lock = threading.Lock()
        self.input_device = None
        self.output_device = None
        self.monitor_device = None
        self.monitor_enabled = False
        self.monitor_volume = 0.8
        self.input_gain = 1.0
        self.output_gain = 1.0
        self.gate_db = -50.0
        self.bypass = False

        self.in_level = 0.0
        self.out_level = 0.0
        self.load = 0.0  # processing time / real time
        self.error = ""

        self._in_queue = collections.deque()
        self._in_event = threading.Event()
        self._out_ring = Ring()
        self._mon_ring = Ring()
        self._streams = []
        self._worker = None
        self._running = False
        self._gate_gain = 1.0
        self._gate_hold = 0

    # ---------------------------------------------------------------- control
    @property
    def running(self):
        return self._running

    def set_voice(self, voice):
        with self.voice_lock:
            old = self.voice
            self.voice = voice or Passthrough()
            self._in_queue.clear()
            self._out_ring.configure(self.voice.block_size)
            self._mon_ring.configure(self.voice.block_size)
        if old is not None and old is not voice:
            old.close()

    def start(self):
        if sd is None:
            raise RuntimeError("Не найден аудио-драйвер PortAudio: " + SD_ERROR)
        self.stop()
        self.error = ""
        self._out_ring.configure(self.voice.block_size)
        self._mon_ring.configure(self.voice.block_size)
        self._in_queue.clear()
        self._running = True
        try:
            in_idx = _device_index(self.input_device, "input")
            self._streams.append(sd.InputStream(
                device=in_idx, channels=1, samplerate=ENGINE_SR, blocksize=CALLBACK_FRAMES,
                dtype="float32", latency="low", callback=self._on_input))
            if self.output_device:
                self._streams.append(self._open_output(self.output_device, self._out_ring, 1.0))
            if self.monitor_device:
                self._streams.append(self._open_output(self.monitor_device, self._mon_ring, None))
            for stream in self._streams:
                stream.start()
        except Exception:
            self.stop()
            raise
        self._worker = threading.Thread(target=self._work, name="voice-worker", daemon=True)
        self._worker.start()

    def stop(self):
        self._running = False
        self._in_event.set()
        for stream in self._streams:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams = []
        if self._worker is not None:
            self._worker.join(timeout=2)
            self._worker = None
        self.in_level = self.out_level = 0.0

    def _open_output(self, name, ring, fixed_volume):
        idx = _device_index(name, "output")
        channels = min(2, sd.query_devices(idx)["max_output_channels"])

        def callback(outdata, frames, _time, _status):
            data = ring.read(frames)
            if fixed_volume is None:
                data = data * (self.monitor_volume if self.monitor_enabled else 0.0)
            outdata[:] = data[:, None]

        return sd.OutputStream(device=idx, channels=channels, samplerate=ENGINE_SR,
                               blocksize=CALLBACK_FRAMES, dtype="float32", latency="low",
                               callback=callback)

    # ---------------------------------------------------------------- audio thread
    def _on_input(self, indata, frames, _time, _status):
        data = indata[:, 0] * self.input_gain
        self.in_level = max(float(np.sqrt(np.mean(data ** 2))), self.in_level * 0.8)
        self._in_queue.append(data.copy())
        self._in_event.set()

    def _gate(self, chunk):
        rms = float(np.sqrt(np.mean(chunk ** 2)) + 1e-12)
        db = 20.0 * np.log10(rms)
        if db > self.gate_db:
            self._gate_hold = 20  # ~200 ms hold
        elif self._gate_hold > 0:
            self._gate_hold -= 1
        target = 1.0 if self._gate_hold > 0 else 0.0
        ramp = np.linspace(self._gate_gain, target, len(chunk), dtype=np.float32)
        self._gate_gain = target
        return chunk * ramp

    def _work(self):
        pending = []
        pending_len = 0
        while self._running:
            if not self._in_queue:
                self._in_event.wait(0.1)
                self._in_event.clear()
                continue
            chunk = self._in_queue.popleft()
            chunk = self._gate(chunk)
            pending.append(chunk)
            pending_len += len(chunk)
            with self.voice_lock:
                voice = self.voice
                size = voice.block_size
                if pending_len < size:
                    continue
                data = np.concatenate(pending)
                block, rest = data[:size], data[size:]
                pending, pending_len = ([rest], len(rest)) if len(rest) else ([], 0)
                started = time.perf_counter()
                try:
                    out = block if self.bypass else voice.process(block)
                except Exception as exc:  # keep the stream alive, show the error
                    self.error = f"Ошибка голоса: {exc}"
                    out = block
                spent = time.perf_counter() - started
            self.load = 0.8 * self.load + 0.2 * (spent / (size / ENGINE_SR))
            out = np.clip(np.asarray(out, dtype=np.float32) * self.output_gain, -1.0, 1.0)
            self.out_level = max(float(np.sqrt(np.mean(out ** 2))), self.out_level * 0.6)
            self._out_ring.write(out)
            self._mon_ring.write(out)
            # if we fall behind real time, skip stale input instead of piling up latency
            backlog = sum(len(c) for c in self._in_queue)
            if backlog > size * 2 + ENGINE_SR // 2:
                self._in_queue.clear()

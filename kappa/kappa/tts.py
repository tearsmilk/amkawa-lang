"""Text-to-speech: the system synthesizer speaks the text, then the selected voice model re-voices it.

macOS uses the built-in `say` (works offline; Big Sur ships e.g. Milena (ru), Samantha (en)).
Other systems fall back to `espeak-ng` so the feature can be developed and tested there.
"""
import copy
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .voices import ENGINE_SR

# female system voices that sound best as a base for anime voices, in order of preference
PREFERRED = ["Milena", "Katya", "Samantha", "Kyoko", "Karen", "Moira", "Tessa", "Victoria", "Allison", "Ava"]


@dataclass
class SystemVoice:
    name: str
    lang: str

    @property
    def label(self):
        return f"{self.name} ({self.lang})"


def _say_voices():
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=20).stdout
    voices = []
    for line in out.splitlines():
        # "Milena              ru_RU    # Здравствуйте, меня зовут Милена."
        m = re.match(r"^(.+?)\s{2,}([a-z]{2}[_-][A-Za-z]{2,})\s+#", line)
        if m:
            voices.append(SystemVoice(m.group(1).strip(), m.group(2)))
    return voices


def list_voices():
    try:
        if sys.platform == "darwin":
            voices = _say_voices()
        elif shutil.which("espeak-ng"):
            voices = [SystemVoice("ru+f3", "ru_RU"), SystemVoice("en+f3", "en_US"), SystemVoice("ja+f3", "ja_JP")]
        else:
            voices = []
    except Exception:
        voices = []
    rank = {name: i for i, name in enumerate(PREFERRED)}
    voices.sort(key=lambda v: (rank.get(v.name, 100), not v.lang.startswith("ru"), v.name))
    return voices


def _read_wav(path):
    with wave.open(str(path), "rb") as wf:
        sr, ch, width = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if width != 2:
        raise RuntimeError("Неожиданный формат звука от синтезатора")
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    if sr != ENGINE_SR:
        from scipy.signal import resample_poly

        g = np.gcd(ENGINE_SR, sr)
        audio = resample_poly(audio, ENGINE_SR // g, sr // g).astype(np.float32)
    return audio


def synthesize(text, voice=None, rate=1.0):
    """Speak `text` with a system voice; returns mono float32 audio at ENGINE_SR."""
    text = text.strip()
    if not text:
        raise ValueError("Введите текст")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "text.txt"
        src.write_text(text, "utf-8")
        out = tmp / "speech.wav"
        if sys.platform == "darwin":
            cmd = ["say", "-f", str(src), "-o", str(out), "--file-format=WAVE",
                   f"--data-format=LEI16@{ENGINE_SR}", "-r", str(int(180 * rate))]
            if voice:
                cmd[1:1] = ["-v", voice]
        elif shutil.which("espeak-ng"):
            cmd = ["espeak-ng", "-f", str(src), "-w", str(out), "-s", str(int(165 * rate))]
            if voice:
                cmd[1:1] = ["-v", voice]
        else:
            raise RuntimeError("Синтезатор речи не найден")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not out.exists():
            raise RuntimeError(result.stderr.strip() or "Синтезатор речи не сработал")
        return _read_wav(out)


def revoice(audio, voice, **params):
    """Run a finished clip through a voice model, using a private copy of its streaming state."""
    if voice is None:
        return audio
    if hasattr(voice, "with_block"):
        clone = voice.with_block(2.0)  # neural voices: big blocks are much faster offline
    else:
        clone = copy.copy(voice)  # shares the (heavy) state tables, not the buffers
        clone.reset()
    if params:
        clone.set_params(**params)
    block = clone.block_size
    # the voices are streaming: feed silence after the clip to flush their internal latency
    tail = max(block * 2, 4096) + ENGINE_SR // 4
    padded = np.concatenate([audio, np.zeros(tail + (-(len(audio) + tail)) % block, np.float32)])
    out = np.concatenate([clone.process(padded[i:i + block]) for i in range(0, len(padded), block)])
    # drop leading silence introduced by the voice's latency, keep a short lead-in
    voiced = np.flatnonzero(np.abs(out) > 1e-3)
    if len(voiced):
        start = max(0, voiced[0] - ENGINE_SR // 50)
        end = min(len(out), voiced[-1] + ENGINE_SR // 10)
        out = out[start:end]
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 0.98:
        out = out * (0.98 / peak)
    return out.astype(np.float32)

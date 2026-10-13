"""Real-time RVC (Retrieval-based Voice Conversion) voice: any RVC v1/v2 `.pth` model.

Pipeline per block: 48k input window -> 16k -> ContentVec features + YIN pitch ->
RVC synthesizer (only the tail is synthesised) -> 48k -> SOLA crossfade with the previous block.
"""
import threading

import numpy as np
import torch
from scipy.signal import resample_poly

from . import ENGINE_SR, Voice
from .hubert import ContentVec
from .pitch import yin_f0

_hubert_lock = threading.Lock()
_hubert_cache = {}

F0_MIN, F0_MAX = 50.0, 1100.0
MEL_MIN = 1127.0 * np.log(1.0 + F0_MIN / 700.0)
MEL_MAX = 1127.0 * np.log(1.0 + F0_MAX / 700.0)


def load_contentvec(path):
    with _hubert_lock:
        key = str(path)
        if key not in _hubert_cache:
            _hubert_cache.clear()
            _hubert_cache[key] = ContentVec.load(path)
        return _hubert_cache[key]


def read_checkpoint(path):
    """Load an RVC checkpoint without executing pickled code."""
    cpt = torch.load(str(path), map_location="cpu", weights_only=True)
    if not isinstance(cpt, dict) or "weight" not in cpt or "config" not in cpt:
        raise ValueError("Это не RVC-модель (нет 'weight'/'config' внутри .pth)")
    return cpt


def describe_checkpoint(path):
    cpt = read_checkpoint(path)
    return {
        "version": cpt.get("version", "v1"),
        "f0": int(cpt.get("f0", 1)),
        "sr": int(cpt["config"][-1]),
    }


def build_synth(cpt):
    from .rvc_pack.models import (
        SynthesizerTrnMs256NSFsid,
        SynthesizerTrnMs256NSFsid_nono,
        SynthesizerTrnMs768NSFsid,
        SynthesizerTrnMs768NSFsid_nono,
    )

    config = list(cpt["config"])
    config[-3] = cpt["weight"]["emb_g.weight"].shape[0]
    version = cpt.get("version", "v1")
    f0 = int(cpt.get("f0", 1))
    cls = {
        ("v1", 1): SynthesizerTrnMs256NSFsid,
        ("v1", 0): SynthesizerTrnMs256NSFsid_nono,
        ("v2", 1): SynthesizerTrnMs768NSFsid,
        ("v2", 0): SynthesizerTrnMs768NSFsid_nono,
    }[(version, f0)]
    net = cls(*config, is_half=False)
    if hasattr(net, "enc_q"):
        del net.enc_q
    net.load_state_dict(cpt["weight"], strict=False)
    net.eval()
    for p in net.parameters():
        p.requires_grad_(False)
    return net, version, f0, int(config[-1])


def _ms(seconds):
    """Round seconds to a whole number of 10 ms steps, in 48 kHz samples."""
    return max(1, int(round(seconds * 100))) * (ENGINE_SR // 100)


class RVCVoice(Voice):
    def __init__(self, model_path, contentvec_path, pitch=0.0, block_time=0.4, extra_time=0.8,
                 crossfade_time=0.05, speaker=0):
        self.hubert = load_contentvec(contentvec_path)
        cpt = read_checkpoint(model_path)
        self.net, self.version, self.use_f0, self.tgt_sr = build_synth(cpt)
        del cpt
        self.speaker = torch.LongTensor([int(speaker)])
        self.pitch = float(pitch)
        self.block_size = _ms(block_time)
        self.extra = _ms(extra_time)
        self.sola_buf = _ms(crossfade_time)
        self.sola_search = _ms(0.01)
        self.total = self.extra + self.sola_buf + self.sola_search + self.block_size
        self.fade_in = np.sin(0.5 * np.pi * np.linspace(0, 1, self.sola_buf)) ** 2
        self.fade_out = 1.0 - self.fade_in
        g = np.gcd(ENGINE_SR, self.tgt_sr)
        self.up, self.down = ENGINE_SR // g, self.tgt_sr // g
        self.reset()

    def set_params(self, pitch=None, **_):
        if pitch is not None:
            self.pitch = float(pitch)

    def reset(self):
        self.window = np.zeros(self.total, dtype=np.float32)
        self.prev_tail = np.zeros(self.sola_buf, dtype=np.float32)

    def _coarse(self, f0):
        mel = 1127.0 * np.log(1.0 + f0 / 700.0)
        voiced = mel > 0
        mel[voiced] = (mel[voiced] - MEL_MIN) * 254.0 / (MEL_MAX - MEL_MIN) + 1.0
        mel = np.clip(mel, 1, 255)
        return np.rint(mel).astype(np.int64)

    @torch.no_grad()
    def _convert(self, wav48):
        wav16 = resample_poly(wav48, 1, 3).astype(np.float32)
        p_len = len(wav16) // 160
        feats = self.hubert(torch.from_numpy(wav16)[None], self.version)
        feats = torch.cat([feats, feats[:, -1:, :]], dim=1)
        feats = torch.nn.functional.interpolate(feats.transpose(1, 2), scale_factor=2).transpose(1, 2)
        p_len = min(p_len, feats.shape[1])
        feats = feats[:, :p_len]
        out_frames = (self.sola_buf + self.sola_search + self.block_size) // (ENGINE_SR // 100)
        rate = torch.tensor([min(1.0, out_frames / p_len)])
        lengths = torch.LongTensor([p_len])
        if self.use_f0:
            f0 = yin_f0(wav16)[:p_len]
            if len(f0) < p_len:
                f0 = np.pad(f0, (0, p_len - len(f0)))
            f0 = f0 * 2.0 ** (self.pitch / 12.0)
            pitch = torch.from_numpy(self._coarse(f0.copy()))[None]
            pitchf = torch.from_numpy(f0.astype(np.float32))[None]
            audio = self.net.infer(feats, lengths, pitch, pitchf, self.speaker, rate)[0]
        else:
            audio = self.net.infer(feats, lengths, self.speaker, rate)[0]
        audio = audio[0, 0].numpy()
        if self.up != self.down:
            audio = resample_poly(audio, self.up, self.down)
        return audio.astype(np.float32)

    def process(self, block):
        n = len(block)
        self.window[:-n] = self.window[n:]
        self.window[-n:] = block
        if np.max(np.abs(self.window[-(n + self.sola_buf):])) < 1e-4:
            self.prev_tail[:] = 0
            return np.zeros(n, dtype=np.float32)
        out = self._convert(self.window)
        need = self.sola_buf + self.sola_search + n
        if len(out) < need:
            out = np.pad(out, (need - len(out), 0))
        out = out[-need:]

        # SOLA: find the offset where the new audio lines up best with the previous tail
        search = out[: self.sola_buf + self.sola_search]
        corr = np.correlate(search, self.prev_tail, mode="valid")
        energy = np.sqrt(np.convolve(search ** 2, np.ones(self.sola_buf), mode="valid") + 1e-8)
        offset = int(np.argmax(corr / energy))
        result = out[offset:offset + n].copy()
        result[: self.sola_buf] = result[: self.sola_buf] * self.fade_in + self.prev_tail * self.fade_out
        self.prev_tail = out[offset + n: offset + n + self.sola_buf].copy()
        if len(self.prev_tail) < self.sola_buf:
            self.prev_tail = np.pad(self.prev_tail, (0, self.sola_buf - len(self.prev_tail)))
        return result

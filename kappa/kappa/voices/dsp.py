"""Built-in voices: a streaming phase-vocoder pitch shifter with independent formant control.

Runs in pure numpy, needs no downloads and has ~25 ms latency, so it works on any Intel Mac.
"""
import numpy as np

from . import ENGINE_SR, Voice

TWO_PI = 2.0 * np.pi


def _wrap(phase):
    return phase - TWO_PI * np.round(phase / TWO_PI)


class SpectralVoice(Voice):
    """Pitch shift + formant shift + brightness + breathiness, frame by frame."""

    def __init__(self, pitch=12.0, formant=1.2, brightness=2.0, breath=0.0, n_fft=2048, hop=512):
        self.n_fft = n_fft
        self.hop = hop
        self.block_size = hop
        self.bins = n_fft // 2 + 1
        self.window = np.hanning(n_fft + 1)[:-1].astype(np.float64)
        # Hann analysis * Hann synthesis overlap-adds to 1.5 at 75% overlap (n_fft / hop == 4).
        self.ola_norm = np.sum(self.window ** 2) / hop
        self.k = np.arange(self.bins, dtype=np.float64)
        self.expected_adv = TWO_PI * hop * self.k / n_fft
        # cepstral lifter: keeps the spectral envelope, drops pitch harmonics
        self.lifter = 28
        self.rng = np.random.default_rng()
        self.set_params(pitch=pitch, formant=formant, brightness=brightness, breath=breath)
        self.reset()

    def set_params(self, pitch=None, formant=None, brightness=None, breath=None, **_):
        if pitch is not None:
            self.pitch = float(pitch)
            self.ratio = 2.0 ** (self.pitch / 12.0)
        if formant is not None:
            self.formant = float(formant)
        if brightness is not None:
            self.brightness = float(brightness)
        if breath is not None:
            self.breath = float(breath)
        self._prepare_maps()

    def _prepare_maps(self):
        k = self.k
        # Output bin j takes energy from source bin j / ratio (fractional, linear interpolation).
        src = k / self.ratio
        self.src_valid = src <= self.bins - 1
        src = np.clip(src, 0, self.bins - 1)
        self.src_lo = np.floor(src).astype(np.int64)
        self.src_hi = np.minimum(self.src_lo + 1, self.bins - 1)
        self.src_frac = src - self.src_lo
        self.src_near = np.clip(np.round(src).astype(np.int64), 0, self.bins - 1)
        # Target envelope = source envelope stretched by the formant ratio.
        fsrc = np.clip(k / self.formant, 0, self.bins - 1)
        self.fmt_lo = np.floor(fsrc).astype(np.int64)
        self.fmt_hi = np.minimum(self.fmt_lo + 1, self.bins - 1)
        self.fmt_frac = fsrc - self.fmt_lo
        self.fmt_valid = (k / self.formant) <= self.bins - 1
        # Gentle high shelf above ~2.5 kHz for the "bright anime" sparkle.
        freqs = k * ENGINE_SR / self.n_fft
        shelf = 1.0 / (1.0 + np.exp(-(freqs - 2500.0) / 600.0))
        self.eq = 10.0 ** (self.brightness * shelf / 20.0)
        # keep rumble out
        self.eq *= 1.0 / (1.0 + (90.0 / np.maximum(freqs, 1.0)) ** 4)

    def reset(self):
        self.in_buf = np.zeros(self.n_fft)
        self.out_buf = np.zeros(self.n_fft)
        self.last_phase = np.zeros(self.bins)
        self.sum_phase = np.zeros(self.bins)

    def _envelope(self, mag):
        cep = np.fft.irfft(np.log(mag + 1e-9))
        cep[self.lifter:-self.lifter + 1] = 0.0
        return np.exp(np.fft.rfft(cep).real)

    def _frame(self, frame):
        # zero-phase framing keeps neighbouring bins of one partial in phase
        spec = np.fft.rfft(np.fft.ifftshift(frame * self.window))
        mag = np.abs(spec)
        phase = np.angle(spec)

        delta = _wrap(phase - self.last_phase - self.expected_adv)
        self.last_phase = phase
        true_adv = self.expected_adv + delta  # phase advance per hop of every source bin

        # pitch shift by moving partials
        new_mag = mag[self.src_lo] * (1.0 - self.src_frac) + mag[self.src_hi] * self.src_frac
        new_mag *= self.src_valid
        new_adv = true_adv[self.src_near] * self.ratio
        self.sum_phase = _wrap(self.sum_phase + new_adv)

        # formant correction: impose the (shifted) source envelope onto the new spectrum
        env_src = self._envelope(mag)
        env_new = self._envelope(new_mag)
        target = env_src[self.fmt_lo] * (1.0 - self.fmt_frac) + env_src[self.fmt_hi] * self.fmt_frac
        target *= self.fmt_valid
        gain = np.clip(target / (env_new + 1e-9), 0.0, 8.0)
        new_mag *= gain * self.eq

        out = new_mag * np.exp(1j * self.sum_phase)
        if self.breath > 0.0:
            noise_phase = self.rng.uniform(-np.pi, np.pi, self.bins)
            air = target * self.eq * self.breath * 0.35
            air *= self.k > (self.bins * 0.04)  # breath lives above ~1 kHz
            out = out + air * np.exp(1j * noise_phase)
        return np.fft.fftshift(np.fft.irfft(out, self.n_fft)) * self.window / self.ola_norm

    def process(self, block):
        block = np.asarray(block, dtype=np.float64)
        hop = self.hop
        out = np.empty(len(block))
        for start in range(0, len(block), hop):
            chunk = block[start:start + hop]
            n = len(chunk)
            self.in_buf[:-n] = self.in_buf[n:]
            self.in_buf[-n:] = chunk
            self.out_buf += self._frame(self.in_buf)
            out[start:start + n] = self.out_buf[:n]
            self.out_buf[:-n] = self.out_buf[n:]
            self.out_buf[-n:] = 0.0
        return out.astype(np.float32)

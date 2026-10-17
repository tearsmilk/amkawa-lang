"""Fast vectorised YIN pitch tracker (numpy only) used by the RVC engine."""
import numpy as np


def yin_f0(audio, sr=16000, hop=160, f0_min=50.0, f0_max=1100.0, threshold=0.15):
    """Return one f0 value (Hz, 0 = unvoiced) per `hop` samples, centred like RVC expects."""
    audio = np.asarray(audio, dtype=np.float64)
    tau_min = max(2, int(sr / f0_max))
    tau_max = int(sr / f0_min)
    win = 512
    frame_len = win + tau_max
    n_frames = len(audio) // hop + 1
    pad = frame_len // 2
    padded = np.pad(audio, (pad, pad + frame_len))
    idx = np.arange(n_frames)[:, None] * hop + np.arange(frame_len)[None, :]
    frames = padded[idx]

    # d(tau) = E(x[0:W]) + E(x[tau:tau+W]) - 2 * sum x[j] x[j+tau]
    n = 1 << int(np.ceil(np.log2(frame_len + win)))
    fa = np.fft.rfft(frames, n)
    fb = np.fft.rfft(frames[:, :win], n)
    cross = np.fft.irfft(fa * np.conj(fb), n)[:, :tau_max + 1]
    sq = np.cumsum(np.pad(frames ** 2, ((0, 0), (1, 0))), axis=1)
    energy0 = sq[:, win][:, None]
    taus = np.arange(tau_max + 1)
    energy_tau = sq[:, taus + win] - sq[:, taus]
    diff = energy0 + energy_tau - 2.0 * cross
    diff[:, 0] = 0.0

    # cumulative mean normalised difference
    cum = np.cumsum(diff[:, 1:], axis=1)
    cmnd = np.ones_like(diff)
    cmnd[:, 1:] = diff[:, 1:] * taus[1:] / np.maximum(cum, 1e-12)

    search = cmnd[:, tau_min:tau_max]
    below = search < threshold
    has = below.any(axis=1)
    first = np.where(has, below.argmax(axis=1), search.argmin(axis=1))
    # walk to the local minimum after the first threshold crossing
    rows = np.arange(n_frames)
    for _ in range(8):
        nxt = np.minimum(first + 1, search.shape[1] - 1)
        better = search[rows, nxt] < search[rows, first]
        first = np.where(better, nxt, first)
    tau = first + tau_min
    # parabolic interpolation
    t0 = np.clip(tau - 1, 0, tau_max)
    t2 = np.clip(tau + 1, 0, tau_max)
    a, b, c = cmnd[rows, t0], cmnd[rows, tau], cmnd[rows, t2]
    denom = a - 2 * b + c
    safe = np.where(np.abs(denom) > 1e-9, denom, 1.0)
    shift = np.where(np.abs(denom) > 1e-9, 0.5 * (a - c) / safe, 0.0)
    shift = np.clip(shift, -1, 1)
    f0 = sr / (tau + shift)

    voiced = has & (cmnd[rows, tau] < threshold * 2)
    rms = np.sqrt(np.mean(frames[:, :win] ** 2, axis=1))
    voiced &= rms > 1e-3
    f0 = np.where(voiced, f0, 0.0)

    # 3-tap median to kill single-frame octave jumps
    if n_frames >= 3:
        stacked = np.stack([np.r_[f0[:1], f0[:-1]], f0, np.r_[f0[1:], f0[-1:]]])
        f0 = np.median(stacked, axis=0)
    return f0

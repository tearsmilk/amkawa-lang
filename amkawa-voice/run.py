"""Entry point (used by PyInstaller and for `python run.py`)."""
import sys


def selftest():
    """Headless check used by CI on the built app: every engine imports and produces audio."""
    import numpy as np

    from amkawa_voice import catalog, engine
    from amkawa_voice.voices.dsp import SpectralVoice
    from amkawa_voice.voices.pitch import yin_f0
    from amkawa_voice.voices.rvc_pack import models  # noqa: F401  (torch + RVC net import)
    from amkawa_voice.voices.hubert import ContentVec

    ContentVec()
    t = np.arange(48000) / 48000
    x = sum(np.sin(2 * np.pi * 140 * h * t) / h for h in range(1, 20)).astype(np.float32) * 0.1
    for model in catalog.BUILTIN:
        v = SpectralVoice(**model.params)
        y = np.concatenate([v.process(x[i:i + v.block_size]) for i in range(0, len(x), v.block_size)])
        assert np.isfinite(y).all() and y.std() > 1e-3, model.id
    f0 = yin_f0(x[::3])
    assert abs(np.median(f0[f0 > 0]) - 140) < 5
    print("devices:", engine.list_devices(), engine.SD_ERROR or "")
    import PySide6.QtWidgets  # noqa: F401
    print("selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from amkawa_voice.ui import main

    sys.exit(main())

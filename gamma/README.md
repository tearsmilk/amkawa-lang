# γ Гамма — Gamma

Screen recorder and screenshot tool in the Claude-like style of the other apps in this repo (ivory / charcoal,
terracotta accent, serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by
`.github/workflows/gamma-macos.yml` (self-test included).

| Feature | How |
|---|---|
| Снимок области (⇧⌘2) | Frozen picture of the screen under the cursor, drag a rectangle (handles, arrows, loupe with pixel coordinates, size in pixels); a click = whole screen. PNG / JPEG, clipboard, preview toast, shutter sound, delay 0–10 s |
| Снимок экрана (⇧⌘1) | Screen under the cursor or all screens stitched |
| Запись области (⇧⌘8) | Select a region, pick the sound on the selection toolbar, countdown, dashed frame around the region, floating bar with timer / stop / discard; the same hotkey stops |
| Запись экрана (⇧⌘9) | Whole screen; the same hotkey stops |
| Звук | none / microphone / system (through a loopback device such as BlackHole — found automatically) / both mixed |
| Откат (⇧⌘0, toggle ⇧⌘-) | Replay buffer: the screen is continuously written as 10 s segments into a ring; the hotkey saves the last *N* minutes (default 5) and keeps recording *M* more (default 1) → one 6-minute clip |
| Настройки | folders for video / screenshots, MP4 / MOV / MKV, fps, quality, VideoToolbox or x264, size cap, cursor / clicks, countdown, hide Гамма's own windows from captures, audio devices, replay lengths and screen, theme |
| Горячие клавиши | Any combination per action; global on macOS (Carbon `RegisterEventHotKey`, physical keys — work in the Russian layout, no Accessibility permission) |

## How it works

- **Capture engine** (`gamma/ffmpeg.py`): the static ffmpeg 7.1 from `imageio-ffmpeg` (avfoundation, VideoToolbox,
  x264; `minos 11.0`) is bundled into the app. Screen + up to two audio devices → crop (relative to the input size,
  so Retina scale does not matter) → scale to even size → H.264 + AAC into a temporary `.mkv`, remuxed to the chosen
  container on stop (a crash never loses the recording).
- **Replay buffer**: the same pipeline with `-f segment -segment_wrap` (1 s keyframes) plus a CSV segment list;
  buffer time ↔ wall clock is calibrated from finished segments; saving concatenates the needed segments with
  `-ss / -t` and a stream copy (no re-encode) in a worker thread.
- **Windows over the screen** (`gamma/overlay.py`): region selector, recording frame / bar, countdown, toasts — put
  above the menu bar and full-screen apps and excluded from screen capture (`NSWindowSharingNone`) through tiny
  ctypes bridges in `gamma/macos.py` (no PyObjC).
- Menu-bar icon γ with all actions; closing the window keeps Гамма running there.

## Run

```bash
cd gamma
pip install -r requirements.txt imageio-ffmpeg==0.6.0
python run.py              # the app
python run.py --selftest   # headless checks (records a test pattern, replay 3 s + 2 s, UI, hotkey editor)
```

## Design

Figma file «Гамма — UI» (team Lotus): `design/figma/01_ui_kit.js`, `design/figma/02_screens.js`.

# μ Мю — Mu

Live2D Cubism-style editor for 2D VTuber models, in the Claude-like style of the other apps in this repo
(ivory / charcoal, terracotta accent, serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by
`.github/workflows/mu-macos.yml`.

The workflow is Cubism's: take a 2D illustration — a layered PSD or a single picture cut into parts inside the app —
mesh it, rig it with warp / rotation deformers and parameter keyforms, add physics, then pose and stream it.

| Workspace | What it does |
|---|---|
| Нарезка | Lasso / polygon / brush / magic-wand selections on a layer; cut or copy to a new layer with automatic hole filling (push-pull inpainting); mirror copy, merge down, import a picture as a layer |
| Риг | Parts tree, auto-mesh, mesh editing (slide on texture) and deformation into keys, warp and rotation deformers, Cubism-standard parameters with ◆ keys, **auto-rig** from layer roles (head XYZ, blink, eye smile, gaze with iris clipping, brows, mouth, cheeks, body XYZ, breathing, arms, legs, hair / skirt physics) |
| Физика | Pendulum groups (inputs → output parameter), live test |
| Студия | Photo background, any number of copies (and other `.mu` models), move / scale / mirror / order, ready-made poses and emotions, saved poses with preview thumbnails, PNG / JPEG export |
| Эфир | Mouse follow, blinking, breathing, idle sway, microphone lip sync (`sounddevice`), emotions on 1–9, borderless chroma-key window for OBS |
| Гайдбук | Built-in guide incl. system requirements |

## Files

- **`.mu`** — own project format: zip with `model.json`, `textures/*.png`, studio backgrounds and a thumbnail.
- **PSD** — reader (raw / RLE, groups, Unicode names, blend modes) and layered writer.
- **Cubism `.moc3` (experimental)** — `mu/moc3.py` writes MOC3 v3.00 plus `.model3.json`, `.physics3.json`,
  `.cdi3.json` and texture atlases for VTube Studio. Validated against the official Cubism Core (5.1, WASM build):
  the Core accepts the file (`csmHasMocConsistency`), and its vertex output matches Мю's own evaluation to
  < 1 px for rest, head turns, blink, arms and mouth poses.
- **Inochi2D `.inp`** — import and export.
- **PNGTuber** — idle / talk / blink / talk+blink pictures.

## Run

```bash
pip install -r requirements.txt
python run.py              # app
python run.py --selftest   # headless checks (CI)
```

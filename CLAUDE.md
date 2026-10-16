# Repo notes for Claude

- `kappa/` — Каппа / Kappa (κ, macOS anime voice changer, formerly Amkawa Voice), `epsilon/` — Epsilon (notes/calendar app, formerly Milkys Hub),
  `nu/` — Ню / Nu (ν, VS Code-like code editor with a pty terminal), `zeta/` — Дзета / Zeta (ζ, Aseprite-like pixel-art
  editor, native .aseprite read/write), `delta/` — Дельта / Delta (δ, manga / character painting app with pressure
  brushes, layers, manga tools and After Effects-style keyframe animation), `lambda/` — Лямбда / Lambda (λ, offline
  Figma-like suite: design files, FigJam-like boards, presentations, website editor; package `lyambda` because
  `lambda` is a Python keyword), `mu/` — Мю / Mu (μ, Live2D Cubism-like VTuber model editor: cut a 2D illustration /
  PSD into parts, meshes, warp + rotation deformers, parameter keyforms, auto-rig, physics, photo studio with poses,
  live mode for OBS; own `.mu` files, PSD, Inochi2D and experimental Cubism `.moc3` export). All target macOS 11+ Intel x64 and are built into `.dmg` by `.github/workflows/*-macos.yml` (self-test included).
- **Epsilon design lives in Figma** (file `P9vRt9ShTejyOkC7fYqWU4`, team Lotus): the UI kit and *every* screen.
  When you add or change a screen, dialog or component in Epsilon, update `epsilon/design/figma/01_ui_kit.js` /
  `02_screens.js` in the same change and run them via the Figma MCP `use_figma` tool (Starter plan has a small
  monthly MCP call limit — if it is hit, schedule a retry and tell the user).
- **Ню, Дзета, Дельта, Лямбда and Мю designs** follow the same rule: `nu/design/figma/*.js` → Figma file «Ню — UI»,
  `zeta/design/figma/*.js` → «Дзета — UI», `delta/design/figma/*.js` → «Дельта — UI», `lambda/design/figma/*.js` →
  «Лямбда — UI», `mu/design/figma/*.js` → «Мю — UI» (team Lotus, create them on the first run).
- Мю's `.moc3` writer can be checked against the official Cubism Core (download `live2dcubismcore.min.js`, run it in
  Node and compare drawable vertex positions with `Model.evaluate`); the Core is proprietary — never commit it.
- UI language is Russian; style is Claude-like (ivory/charcoal, terracotta #D97757 accent, serif headings, minimal animation).

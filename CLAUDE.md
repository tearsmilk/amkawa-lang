# Repo notes for Claude

- `kappa/` — Каппа / Kappa (κ, macOS anime voice changer, formerly Amkawa Voice), `epsilon/` — Epsilon (notes/calendar app, formerly Milkys Hub),
  `nu/` — Ню / Nu (ν, VS Code-like code editor with a pty terminal), `zeta/` — Дзета / Zeta (ζ, Aseprite-like pixel-art
  editor, native .aseprite read/write), `delta/` — Дельта / Delta (δ, manga / character painting app with pressure
  brushes, layers, manga tools and After Effects-style keyframe animation), `lambda/` — Лямбда / Lambda (λ, offline
  Figma-like suite: design files, FigJam-like boards, presentations, website editor; package `lyambda` because
  `lambda` is a Python keyword), `mu/` — Мю / Mu (μ, Live2D Cubism-like VTuber model editor: cut a 2D illustration /
  PSD into parts, meshes, warp + rotation deformers, parameter keyforms, auto-rig, physics, photo studio with poses,
  live mode for OBS; own `.mu` files, PSD, Inochi2D and experimental Cubism `.moc3` export), `gamma/` — Гамма / Gamma (γ,
  screen recorder + screenshots: region / full screen, sound, global hotkeys, replay buffer «откат»; bundles the static
  ffmpeg from `imageio-ffmpeg`), `alpha/` — Альфа / Alpha (α, local Trello-like kanban: boards, lists, cards with
  labels / members / dates / checklists / attachments / covers / custom fields, drag and drop, table / calendar /
  dashboard views, Butler-like automation, Trello JSON import), `eta/` — Эта / Eta (η, Minecraft launcher: loading page, home with a
  compact instance card, live Modrinth and CurseForge catalogs (`.mrpack` / CurseForge zip install, sha1-checked mod downloads;
  CurseForge needs an API key from console.curseforge.com in settings), own instances, offline accounts, settings with «Оформление» — accent, window background, glass, side bar
  left / right / folded; `eta/launch.py` downloads Minecraft, Mojang's Java runtime, Fabric / Quilt / Forge / NeoForge and runs the game; accounts: offline, mc-ru.org, Microsoft). All target macOS 11+ Intel x64 and are built into `.dmg` by `.github/workflows/*-macos.yml` (self-test included); Эта is also built into a single Windows x64 `Eta.exe` by `.github/workflows/eta-windows.yml` (`eta/packaging/Eta-windows.spec`, `build_windows.ps1`).
  `rurukasuka/` — rurukaSuka, client Fabric cosmetics mod for Minecraft 1.21.11 (wardrobe, руры, friends; talks to mc-ru.org,
  Mojang mappings, Gradle wrapper, built by `.github/workflows/rurukasuka-mod.yml`, releases `rurukasuka-v*`); Эта installs it into
  Fabric/Quilt instances as a system mod and hands over the mc-ru.org session via `config/rurukasuka_launcher.json`.
  `theta/` — Тета / Theta (θ, local GeoGuessr-like game, macOS only: Google Street View in QtWebEngine (own key, free
  Metadata API picks the pano), Mapillary panoramas (token) and Wikimedia Commons photos, own OSM slippy map for the
  guess, Natural Earth countries bundled for land-only picks and the country-streak mode; classic / streak / daily,
  local records; built into `.dmg` by `.github/workflows/theta-macos.yml`).
- **Epsilon design lives in Figma** (file `P9vRt9ShTejyOkC7fYqWU4`, team Lotus): the UI kit and *every* screen.
  When you add or change a screen, dialog or component in Epsilon, update `epsilon/design/figma/01_ui_kit.js` /
  `02_screens.js` in the same change and run them via the Figma MCP `use_figma` tool (Starter plan has a small
  monthly MCP call limit — if it is hit, schedule a retry and tell the user).
- **Ню, Дзета, Дельта, Лямбда, Мю, Гамма, Альфа, Эта and Тета designs** follow the same rule (`theta/design/figma/*.js` → «Тета — UI»): `nu/design/figma/*.js` → Figma file «Ню — UI»,
  `zeta/design/figma/*.js` → «Дзета — UI», `delta/design/figma/*.js` → «Дельта — UI», `lambda/design/figma/*.js` →
  «Лямбда — UI», `mu/design/figma/*.js` → «Мю — UI», `gamma/design/figma/*.js` → «Гамма — UI», `alpha/design/figma/*.js` → «Альфа — UI»,
  `eta/design/figma/*.js` → «Эта — UI» (team Lotus, create them on the first run).
- Мю's `.moc3` writer can be checked against the official Cubism Core (download `live2dcubismcore.min.js`, run it in
  Node and compare drawable vertex positions with `Model.evaluate`); the Core is proprietary — never commit it.
- UI language is Russian; style is Claude-like (ivory/charcoal, terracotta #D97757 accent, serif headings, minimal animation).

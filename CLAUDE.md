# Repo notes for Claude

- `amkawa-voice/` — Amkawa Voice (macOS voice changer), `epsilon/` — Epsilon (notes/calendar app, formerly Milkys Hub).
  Both target macOS 11+ Intel x64 and are built into `.dmg` by `.github/workflows/*-macos.yml` (self-test included).
- **Epsilon design lives in Figma** (file `P9vRt9ShTejyOkC7fYqWU4`, team Lotus): the UI kit and *every* screen.
  When you add or change a screen, dialog or component in Epsilon, update `epsilon/design/figma/01_ui_kit.js` /
  `02_screens.js` in the same change and run them via the Figma MCP `use_figma` tool (Starter plan has a small
  monthly MCP call limit — if it is hit, schedule a retry and tell the user).
- UI language is Russian; style is Claude-like (ivory/charcoal, terracotta #D97757 accent, serif headings, minimal animation).

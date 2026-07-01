# Roadmap

## Done ✅
- Core language: variables, `tyan` functions, `moshi/else`, `while`, `for … in`, lists, math, strings, comparisons/logic.
- Two interpreters: JavaScript (`src/amkawa.js`) and Python (`reference-python/`).
- VSCode extension (pure JS, runs with no external runtime).
- Browser playground with a 2D drawing canvas.
- Discord bots + a tiny HTTP server (Python reference, written from scratch — no external libs).

## Good first contributions 🌱
- More built-ins: string helpers (`upper`, `split`, `join`), math (`sqrt`, `abs`, `floor`), list ops (`map`, `filter`, `sort`).
- **Maps / dictionaries** as a value type (`{ }`), plus a proper `for key in map`.
- Playground: live syntax highlighting in the editor, and highlight the error line.
- Drawing: an animation loop (`every_frame { ... }`), keyboard/mouse input, images.
- Sound built-ins.
- Nicer errors (show the offending code line with a caret).

## Bigger goals 🚀
- A small **standard library** written in Aminakawa itself.
- A **module system** (`import`).
- Share/run programs from a URL.
- A docs website (host `docs/guide.html` on GitHub Pages).

## The dream 🌙 — self-hosting
Rewrite the Aminakawa interpreter **in Aminakawa itself**. This means writing a lexer,
parser and evaluator as `.amkawa` code, then running it with the current JS/Python
interpreter (bootstrapping). It's a big project and mostly a badge of honor for a
language — perfect long-term target for contributors who want a real challenge.
Prereqs that would help first: maps/dictionaries, string helpers, file reading.

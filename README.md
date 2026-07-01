# Aminakawa 🌸

A tiny **anime-flavored programming language**. Simple syntax, runs anywhere — no install.

- ▶ **Try it now:** open `playground/index.html` in a browser. Write code, hit Run, it draws.
- 🧩 **In VSCode:** install `vscode-extension/` (copy to `~/.vscode/extensions/`) and press ▶ on any `.amkawa` file. No Python needed.
- 📖 **Learn it:** open `docs/guide.html` — a from-zero tutorial.

```
tyan hello(name) {
  back "Konnichiwa, " + name + "!"
}

nya(hello("Aoi"))

# draw something
background("#0e0d11")
color("#ff9ec7")
circle(100, 100, 40)
```

## Keywords
`tyan` def · `back` return · `moshi`/`else` if · `while` · `for … in …` ·
`and`/`or`/`not` · `hai`/`iie` true/false · `mu` null

## Built-ins
`nya` print · `len` · `num` · `str` · `ask` input · `range` · `push` · `random` ·
drawing: `background` `color` `rect` `circle` `line` `dot` `text` `width` `height`

## Project layout
- `src/amkawa.js` — the language (lexer → parser → interpreter), in JavaScript.
- `playground/index.html` — browser IDE with a canvas. Self-contained.
- `vscode-extension/` — syntax highlighting + Run button (pure JS, no Python).
- `reference-python/` — alternate implementation in Python, with **Discord bots** and a **web server** built from scratch.
- `examples/` — sample programs.
- `docs/guide.html` — beginner tutorial.

## Status
Working core: variables, functions, conditions, loops, lists, math, strings, 2D drawing.
See `ROADMAP.md` for what's next, and `CONTRIBUTING.md` to jump in.

## License
MIT — see `LICENSE`.

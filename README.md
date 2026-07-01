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
drawing: `background` `color` `rect` `circle` `line` `dot` `text` `font` `width` `height` ·
events: `on_click` (calls your function with the click x, y)

## Project layout
- `src/amkawa.js` — the language (lexer → parser → interpreter), in JavaScript. This is the canonical implementation.
- `playground/index.html` — browser IDE with a canvas. Self-contained.
- `vscode-extension/` — syntax highlighting + Run button (pure JS, no Python).
- `reference-python/` — alternate implementation in Python, with **Discord bots** and a **web server** built from scratch.
- `implementations/` — the same core language in other languages: **Java**, **C**, **Rust** (console only, no graphics). See below.
- `examples/` — sample programs.
- `docs/guide.html` — beginner tutorial.

## Implementations
The core language runs in several languages. The browser/VSCode path uses the
JavaScript one; the others are for running `.amkawa` from a terminal.

| Language   | Folder                    | How to run                                  | Tested |
|------------|---------------------------|---------------------------------------------|--------|
| JavaScript | `src/amkawa.js`           | `node src/amkawa.js file.amkawa`            | ✅ |
| Python     | `reference-python/`       | `python3 amkawa.py file.amkawa`             | ✅ |
| Java       | `implementations/java/`   | `java Amkawa.java file.amkawa` (JDK 11+)    | ✅ |
| C          | `implementations/c/`      | `gcc -O2 -o amkawa amkawa.c -lm` then run   | ✅ |
| Rust       | `implementations/rust/`   | `rustc -O amkawa.rs` then run               | ⚠️ not yet compiled — see its README |

Drawing (`background`, `circle`, `on_click`, …) and Discord only exist in the
JavaScript and Python versions. The Java/C/Rust ports cover the language core:
variables, `tyan` functions, `moshi/while/for`, lists, math, strings, and
`nya/len/num/str/ask/range/push/random`.

## Status
Working core: variables, functions, conditions, loops, lists, math, strings, 2D drawing.
See `ROADMAP.md` for what's next, and `CONTRIBUTING.md` to jump in.

## License
MIT — see `LICENSE`.

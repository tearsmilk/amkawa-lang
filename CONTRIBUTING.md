# Contributing

Thanks for helping grow Aminakawa! The whole language is small and readable.

## How the code is organized
`src/amkawa.js` is the entire language, in three stages:
1. **lex(src)** — turns text into tokens.
2. **Parser** — turns tokens into a tree (AST).
3. **Interp** — walks the tree and runs it. Built-in functions live in `Interp._installBuiltins`.

## Add a new built-in function (easiest)
Open `src/amkawa.js`, find `_installBuiltins`, and add one line. Example — a `sqrt`:
```js
g.define("sqrt", (x) => { if (typeof x !== "number") throw new AmkError("sqrt() needs a number"); return Math.sqrt(x); });
```
That's it — `sqrt(9)` now works. Add the same to `reference-python/amkawa.py` if you want parity.

## Add a new keyword / syntax (bigger)
Touch three places: `KEYWORDS` (lexer), the `Parser` (how it's parsed), and `Interp` (what it does).

## Test
```
node src/amkawa.js examples/hello.amkawa
```
Add your own file under `examples/` to show the feature.

## Playground
It embeds a copy of the interpreter. After changing `src/amkawa.js`, paste the updated
code into `playground/index.html` (the first `<script>` block, everything before the DOM glue).

## PRs
Small, focused PRs are best. Keep the language simple and beginner-friendly — that's the point.

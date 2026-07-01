# Aminakawa — Java implementation

A tree-walking interpreter for the core Aminakawa language, written in a single
Java file. Supports variables, `tyan` functions, `moshi/else`, `while`, `for ... in`,
lists, math, strings and the console built-ins (`nya`, `len`, `num`, `str`, `ask`,
`range`, `push`, `random`). Graphics and Discord are **not** part of this port —
those live in the JavaScript and Python implementations.

## Run (no build step needed)

Needs a JDK 11 or newer. Thanks to single-file source-code mode you don't even
need `javac`:

```bash
java Amkawa.java hello.amkawa
```

## Or compile first

```bash
javac Amkawa.java
java Amkawa hello.amkawa
```

## Notes

- Output and input are forced to UTF-8, so Cyrillic (and any Unicode) prints and
  reads correctly.
- Uses Java 21 features (sealed interfaces, records, pattern-matching `switch`),
  so build with JDK 21+.
- Values map to Java types: numbers → `Double`, text → `String`, lists →
  `ArrayList`, `hai/iie` → `Boolean`, `mu` → `null`.

Tested against `hello.amkawa`, `basics.amkawa` and `calc.amkawa`.

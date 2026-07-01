# Aminakawa — C implementation

A small tree-walking interpreter for the core Aminakawa language, in a single C
file (C99). Supports variables, `tyan` functions, `moshi/else`, `while`,
`for ... in`, lists, math, strings and the console built-ins (`nya`, `len`,
`num`, `str`, `ask`, `range`, `push`, `random`). No graphics/Discord — those are
in the JavaScript and Python implementations.

## Build

```bash
gcc -O2 -o amkawa amkawa.c -lm
```

(`clang` works too: `clang -O2 -o amkawa amkawa.c -lm`.)

## Run

```bash
./amkawa hello.amkawa
```

## Notes

- Cyrillic / Unicode works: identifiers accept UTF-8 letters, and output is
  written as raw UTF-8 bytes, so your terminal shows them correctly.
- Errors use `setjmp`/`longjmp`; `back` (return) uses a small flag that unwinds
  the current function.
- For simplicity the interpreter **never frees memory** — programs are
  short-lived, so this is fine for a reference implementation. If you want to run
  huge/long-lived scripts, add an arena or a GC.
- Values are a tagged union (`number`, `text`, `bool`, `mu`, `list`, function).

Compiles cleanly with `-Wall` and was tested against `hello.amkawa`,
`basics.amkawa` and `calc.amkawa`.

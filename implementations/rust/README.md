# Aminakawa — Rust implementation

A tree-walking interpreter for the core Aminakawa language, in a single Rust
file (no external crates — std only). Supports variables, `tyan` functions,
`moshi/else`, `while`, `for ... in`, lists, math, strings and the console
built-ins (`nya`, `len`, `num`, `str`, `ask`, `range`, `push`, `random`).
No graphics/Discord — those are in the JavaScript and Python implementations.

## Build

```bash
rustc -O amkawa.rs
```

## Run

```bash
./amkawa hello.amkawa
```

## ⚠️ Status

Unlike the JS, Python, Java and C implementations, this Rust port was **not
compiled or tested** in the environment where it was written (no Rust toolchain
there). It was written carefully and reviewed by hand, but there may be small
compile errors. If `rustc` complains, the fixes should be minor — please open an
issue or send a patch.

## Notes

- Values are an `enum` (`Num`, `Str`, `Bool`, `Nil`, `List`, `Func`, `Builtin`).
- Lists use `Rc<RefCell<Vec<Value>>>` so they behave as shared references, like
  in the other implementations.
- Environments are `Rc<RefCell<Env>>` with a parent chain; closures capture their
  defining environment.
- Errors and `back` (return) are modelled with a `Result<Value, Ctrl>` where
  `Ctrl` is either an error or a return value.
- Unicode works out of the box: identifiers use `char::is_alphabetic`, strings
  iterate by `char`.

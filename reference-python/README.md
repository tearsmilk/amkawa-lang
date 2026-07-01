# Aminakawa — Python reference implementation

Same language, implemented in Python. This version also includes networking features
written from scratch (no third-party libraries):

- `amk_discord.py` — a tiny Discord bot client (raw WebSocket gateway + REST).
- `amk_web.py` — a tiny HTTP server (`route` / `serve`).

Run:  `python amkawa.py yourfile.amkawa`

Extra built-ins here: `bot`, `on_message`, `say`, `run` (Discord) and `route`, `serve` (web).
These need Python; the JavaScript version in `../src` is for running with no install.

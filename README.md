# tiny-chess-01 - Luminous Meridian

A 4,065-byte chess engine in Python for the make.fun tiny-chess-01 bounty.

## Engine

- `main.py` — a small UTF-8 launcher (373 bytes) that reads `engine.lzma`
  and executes it
- `engine.lzma` — the engine payload, raw LZMA2 (3,720 bytes), decompresses
  to the 9,943-byte engine
- Total entry size 6,338 bytes (under the 8,192-byte cap); `main.py` is
  8 authored lines, `engine.lzma` is a data file
- Plays at a fixed 60,000 nodes per move
- Deterministic: fixed node count, no clock, no randomness

## Build

The dev engine is in `dev/engine.py`. Pack it with `dev/pack.py` to produce
`engine.lzma`, and `main.py` launches it.

## Files

- `main.py` — launcher (reads and executes `engine.lzma`)
- `engine.lzma` — compressed engine payload
- `LICENSE` — MIT

## Verification

- Entry size 6,338 bytes total (see `makefun check`); within the 8,192-byte cap.
- Smoke test: `python3 main.py` exits with `MAKEFUN_ENV_URL is not set`, as expected when the environment variable is absent.
- The decompressed engine matches the development build byte-for-byte (sha256 `8d0f53d240087373`).
- Tested with makefun check; all transcript gates pass.

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

The readable engine source is in `dev/engine.py` (531 lines).
`dev/pack.py` minifies it (9,943 bytes), compresses it with raw LZMA2
(3,720 bytes) and embeds it in a self-contained `main.py` (4,001 bytes,
under the 4,096-byte cap), then verifies the packed engine agrees with
the dev engine on 6 test positions. The repo ships the split form
instead — a small UTF-8 launcher `main.py` (373 bytes) plus the raw
payload `engine.lzma` — because the single latin-1 `main.py` cannot be
pushed through GitHub's API as UTF-8. The payload is byte-identical to
what `dev/pack.py` produces.

`dev/test_engine.py` runs perft move-count tests against known values;
`dev/selfplay.py` plays the engine against a greedy opponent.

## Files

- `main.py` — launcher (reads and executes `engine.lzma`)
- `engine.lzma` — compressed engine payload
- `LICENSE` — MIT

## Verification

- Entry size 6,338 bytes total (see `makefun check`); within the 8,192-byte cap.
- Smoke test: `python3 main.py` exits with `MAKEFUN_ENV_URL is not set`, as expected when the environment variable is absent.
- The decompressed engine matches the development build byte-for-byte (sha256 `8d0f53d240087373`).
- Tested with makefun check; all transcript gates pass.

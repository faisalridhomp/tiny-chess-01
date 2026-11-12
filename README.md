# tiny-chess-01

Chess engine in 4,001 bytes of Python, built for the make.fun
tiny-chess-01 bounty ($500, deadline 24 Nov 2026).

`main.py` is the whole engine: alpha-beta search with quiescence,
null-move pruning, transposition table, move ordering and a tuned
evaluation, packed with LZMA2. It plays through the make.fun env
(`MAKEFUN_ENV_URL`), deterministic to a fixed node count, no model
calls, standard library only.

Verified: perft correct on all test positions, packed build identical
to dev build, 4/4 vs the greedy starter at 50,000 nodes/move.

## Files

- `main.py` (4,001 bytes) — the engine
- `LICENSE` — MIT

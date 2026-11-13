import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E

def test_perft():
    cases = [
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
         [20, 400, 8902, 197281]),
        ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
         [48, 2039, 97862, 4085603]),
        ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
         [14, 191, 2812, 43238]),
        ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
         [6, 264, 9467, 422333]),
        ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
         [44, 1486, 62379, 2103487]),
    ]
    ok = True
    for fen, expect in cases:
        E.parse_fen(fen)
        for d, want in enumerate(expect, 1):
            t0 = time.time()
            got = E.perft(d)
            dt = time.time() - t0
            mark = "OK " if got == want else "FAIL"
            if got != want: ok = False
            print(f"{mark} perft({d}) {fen[:30]:32s} got {got:>8} want {want:>8} ({dt:.2f}s)")
            if got != want: break
    print("PERFT", "ALL OK" if ok else "FAILED")
    return ok

def test_search():
    # mate in 1: white Qxf7# style; position: r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1 -> Qxf7#
    E.parse_fen("r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
    m = E.best_move(20000)
    print("mate-in-1 test: best =", E.move_uci(m), "expect h5f7")
    # startpos: best move should be a sensible developing move, check nodes/time
    E.parse_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    for lim in (10000, 60000):
        t0 = time.time()
        m = E.best_move(lim)
        dt = time.time() - t0
        print(f"startpos nodes={lim}: best={E.move_uci(m)} time={dt:.2f}s "
              f"nps={E.nodes / max(dt, 1e-9):.0f} nodes_used={E.nodes}")

if __name__ == "__main__":
    ok = test_perft()
    if ok:
        test_search()

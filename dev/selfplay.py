import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E

VALUE = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 100}

def greedy_uci():
    # starter logic: capture most valuable, tie-break promo / cheaper mover / UCI order
    legal = E.legal_moves()
    if not legal: return None
    bd = E.bd
    def board_of():
        b = {}
        for s in range(128):
            if s & 0x88: continue
            p = bd[s]
            if p: b[E.sq_name(s)] = "PNBRQK"[abs(p)-1] if p > 0 else "pnbrqk"[abs(p)-1]
        return b
    board = board_of()
    def rank(m):
        u = E.move_uci(m)
        mover = board[u[:2]].lower()
        victim = board.get(u[2:4])
        if victim is None and mover == "p" and u[0] != u[2]:
            victim = "p"
        taken = VALUE[victim.lower()] if victim else 0
        promo = VALUE[u[4]] if len(u) == 5 else 0
        return (-taken, -promo, VALUE[mover], u)
    return E.move_uci(min(legal, key=rank))

def play_game(opening_moves, engine_white, nodes):
    """engine_white: True if our engine plays white. Returns 1/0.5/0 from engine side."""
    E.parse_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    for u in opening_moves:
        # apply UCI move via gen
        found = None
        for m in E.legal_moves():
            if E.move_uci(m) == u:
                found = m; break
        assert found is not None, f"opening move not legal: {u}"
        E.make(found)
        E.stack.clear()  # game moves are the new root; stack is only for search undo
    plies = len(opening_moves)
    t_engine = 0.0
    while plies < 200:
        legal = E.legal_moves()
        if not legal:
            if E.in_check(E.sd):
                # side to move is checkmated; the other side won
                white_won = E.sd < 0
                return (1.0 if white_won == engine_white else 0.0), plies, t_engine
            return 0.5, plies, t_engine
        engine_turn = (E.sd > 0) == engine_white
        if engine_turn:
            t0 = time.time()
            m = E.best_move(nodes)
            t_engine += time.time() - t0
            u = E.move_uci(m)
        else:
            u = greedy_uci()
        found = None
        for m in E.legal_moves():
            if E.move_uci(m) == u:
                found = m; break
        assert found is not None, f"move not legal: {u}"
        E.make(found)
        E.stack.clear()  # game moves are the new root; stack is only for search undo
        plies += 1
    # adjudication by material
    mat = sum(E.VAL[abs(E.bd[s])] for s in range(128) if not s & 0x88 and abs(E.bd[s]) != 6)
    # material diff white-black in pawn units approx: use VAL
    w = sum(E.VAL[E.bd[s]] for s in range(128) if not s & 0x88 and E.bd[s] > 0)
    b = sum(E.VAL[-E.bd[s]] for s in range(128) if not s & 0x88 and E.bd[s] < 0)
    diff = (w - b) / 100.0
    if diff >= 5: res = 1.0 if engine_white else 0.0
    elif diff <= -5: res = 0.0 if engine_white else 1.0
    else: res = 0.5
    return res, plies, t_engine

OPENINGS = [
    ["d2d4","d7d5","c2c4","c7c6","b1c3","g8f6","e2e3","e7e6"],  # semi-slav
    ["e2e4","c7c5","g1f3","d7d6","d2d4","c5d4","f3d4","g8f6"],  # sicilian najdorf
]

if __name__ == "__main__":
    nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    tot = 0.0; n = 0; ttot = 0.0
    for op in OPENINGS:
        for ew in (True, False):
            t0 = time.time()
            r, plies, te = play_game(op, ew, nodes)
            tot += r; n += 1; ttot += te
            print(f"opening={op[0]} engine={'white' if ew else 'black'}: "
                  f"result={r} plies={plies} engine_time={te:.1f}s wall={time.time()-t0:.1f}s")
    print(f"ENGINE vs GREEDY STARTER: {tot}/{n}  avg engine time/game={ttot/n:.1f}s")

# tiny-chess-01 dev engine v1 (readable; will be lzma-packed to <=4096 bytes)
# 0x88 board, negamax + PVS, TT, null-move, LMR, killers, QS, PeSTO-style
# simplified PSTs (chessprogramming.org), fixed node budget (deterministic).
import json, os, sys, urllib.request

# ---------- constants ----------
# pieces: 1 P, 2 N, 3 B, 4 R, 5 Q, 6 K ; sign = colour (+ white)
VAL = [0, 100, 320, 330, 500, 900, 0]
MATE = 100000
# PSTs, a8 first (index 0 = a8), white perspective
PAWN = [0,0,0,0,0,0,0,0, 50,50,50,50,50,50,50,50, 10,10,20,30,30,20,10,10,
        5,5,10,25,25,10,5,5, 0,0,0,20,20,0,0,0, 5,-5,-10,0,0,-10,-5,5,
        5,10,10,-20,-20,10,10,5, 0,0,0,0,0,0,0,0]
KNIGHT = [-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,0,0,0,-20,-40,
          -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30, -30,0,15,20,20,15,0,-30,
          -30,5,10,15,15,10,5,-30, -40,-20,0,5,5,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50]
BISHOP = [-20,-10,-10,-10,-10,-10,-10,-20, -10,0,0,0,0,0,0,-10,
          -10,0,5,10,10,5,0,-10, -10,5,5,10,10,5,5,-10, -10,0,10,10,10,10,0,-10,
          -10,10,10,10,10,10,10,-10, -10,5,0,0,0,0,5,-10, -20,-10,-10,-10,-10,-10,-10,-20]
ROOK = [0,0,0,0,0,0,0,0, 5,10,10,10,10,10,10,5, -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
        -5,0,0,0,0,0,0,-5, 0,0,0,5,5,0,0,0]
QUEEN = [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,0,0,0,0,0,-10,
         -10,0,5,5,5,5,0,-10, -5,0,5,5,5,5,0,-5, 0,0,5,5,5,5,0,-5,
         -10,5,5,5,5,5,0,-10, -10,0,5,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20]
KING_MG = [-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
           -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
           -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10,
           20,20,0,0,0,0,20,20, 20,30,10,0,0,10,30,20]
KING_EG = [-50,-40,-30,-20,-20,-30,-40,-50, -30,-20,-10,0,0,-10,-20,-30,
           -30,-10,20,30,30,20,-10,-30, -30,-10,30,40,40,30,-10,-30,
           -30,-10,30,40,40,30,-10,-30, -30,-10,20,30,30,20,-10,-30,
           -30,-30,0,0,0,0,-30,-30, -50,-30,-30,-30,-30,-30,-30,-50]
PST = [None, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING_MG]
# knight/king offsets, bishop/rook directions
KN_OFF = (14, 18, 31, 33, -14, -18, -31, -33)
KI_OFF = (1, 15, 16, 17, -1, -15, -16, -17)
DIAG = (15, 17, -15, -17)
ORTH = (1, 16, -1, -16)

# ---------- zobrist (fixed LCG, deterministic) ----------
_seed = 0x9E3779B97F4A7C15
def _rnd():
    global _seed
    _seed = (_seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    return _seed
ZOB = [[_rnd() for _ in range(128)] for _ in range(12)]
Z_SIDE = _rnd()
Z_CAST = [_rnd() for _ in range(16)]

# ---------- mutable game state (globals for speed) ----------
bd = [0] * 128          # board
sd = 1                  # side to move: 1 white, -1 black
ca = 0                  # castling rights: 1 WK 2 WQ 4 BK 8 BQ
ep = -1                 # en passant square or -1
hm = 0                  # halfmove clock
key = 0                 # zobrist key
stack = []              # undo info
nodes = 0
LIMIT = 60000           # fixed node budget per move (tune after NPS test)
TT = {}
KILL = [[0, 0] for _ in range(256)]
PATH = []               # search-path keys (repetition)
ROOT_HIST = {}          # position keys seen at root in this game

class Abort(Exception):
    pass

def sq_name(s):
    return "abcdefgh"[s & 7] + str((s >> 4) + 1)

def move_uci(m):
    f, t = m & 127, (m >> 7) & 127
    p = (m >> 14) & 7
    return sq_name(f) + sq_name(t) + ("nbrq"[p - 2] if p else "")

def parse_fen(fen):
    global bd, sd, ca, ep, hm, key
    parts = fen.split()
    bd = [0] * 128
    r = 7
    f = 0
    mp = "pnbrqk"
    for ch in parts[0]:
        if ch == "/":
            r -= 1; f = 0
        elif ch.isdigit():
            f += int(ch)
        else:
            bd[f + r * 16] = (mp.find(ch.lower()) + 1) * (1 if ch.isupper() else -1)
            f += 1
    sd = 1 if parts[1] == "w" else -1
    ca = 0
    if len(parts) > 2:
        if "K" in parts[2]: ca |= 1
        if "Q" in parts[2]: ca |= 2
        if "k" in parts[2]: ca |= 4
        if "q" in parts[2]: ca |= 8
    ep = -1
    if len(parts) > 3 and parts[3] != "-":
        ep = "abcdefgh".index(parts[3][0]) + (int(parts[3][1]) - 1) * 16
    hm = int(parts[4]) if len(parts) > 4 else 0
    key = 0
    for s in range(128):
        p = bd[s]
        if p:
            key ^= ZOB[(p - 1) if p > 0 else (5 - p)][s]
    if sd < 0:
        key ^= Z_SIDE
    key ^= Z_CAST[ca]

def attacked(s, by):
    for d in (15, 17):
        t = s - d * by
        if not t & 0x88 and bd[t] == by: return True
    for d in KN_OFF:
        t = s + d
        if not t & 0x88 and bd[t] == 2 * by: return True
    for d in KI_OFF:
        t = s + d
        if not t & 0x88 and bd[t] == 6 * by: return True
    for d in DIAG:
        t = s + d
        while not t & 0x88:
            p = bd[t]
            if p:
                if p == 3 * by or p == 5 * by: return True
                break
            t += d
    for d in ORTH:
        t = s + d
        while not t & 0x88:
            p = bd[t]
            if p:
                if p == 4 * by or p == 5 * by: return True
                break
            t += d
    return False

def king_sq(side):
    for s in range(128):
        if bd[s] == 6 * side:
            return s
    return -1

def in_check(side):
    k = king_sq(side)
    return k >= 0 and attacked(k, -side)

def gen_moves(caps_only=False):
    """Pseudo-legal moves for side to move. Move int: f | t<<7 | promo<<14."""
    global sd
    mv = []
    us = sd
    for s in range(128):
        if s & 0x88: continue
        p = bd[s]
        if p == 0 or (p > 0) != (us > 0): continue
        a = abs(p)
        if a == 1:  # pawn
            d = 16 if us > 0 else -16
            start = 1 if us > 0 else 6
            last = 6 if us > 0 else 1
            r = s >> 4
            t = s + d
            if not t & 0x88 and bd[t] == 0:
                if r == last:
                    for pr in (5, 4, 3, 2):
                        mv.append(s | (t << 7) | (pr << 14))
                elif not caps_only:
                    mv.append(s | (t << 7))
                    if r == start:
                        t2 = s + 2 * d
                        if bd[t2] == 0:
                            mv.append(s | (t2 << 7))
            for df in (-1, 1):
                t = s + d + df
                if t & 0x88: continue
                q = bd[t]
                if q and (q > 0) != (us > 0):
                    if r == last:
                        for pr in (5, 4, 3, 2):
                            mv.append(s | (t << 7) | (pr << 14))
                    else:
                        mv.append(s | (t << 7))
                elif t == ep and ep >= 0:
                    mv.append(s | (t << 7))
        elif a == 2 or a == 6:
            offs = KN_OFF if a == 2 else KI_OFF
            for d in offs:
                t = s + d
                if t & 0x88: continue
                q = bd[t]
                if q == 0:
                    if not caps_only: mv.append(s | (t << 7))
                elif (q > 0) != (us > 0):
                    mv.append(s | (t << 7))
        else:
            dirs = DIAG if a == 3 else ORTH if a == 4 else DIAG + ORTH
            for d in dirs:
                t = s + d
                while not t & 0x88:
                    q = bd[t]
                    if q == 0:
                        if not caps_only: mv.append(s | (t << 7))
                    else:
                        if (q > 0) != (us > 0):
                            mv.append(s | (t << 7))
                        break
                    t += d
    if not caps_only:
        # castling: (rights bit, king sq, empty sqs, rook sq, king dest)
        entries = ((1, 4, (5, 6), 7, 6), (2, 4, (3, 2, 1), 0, 2)) if us > 0 else \
                  ((4, 116, (117, 118), 119, 118), (8, 116, (115, 114, 113), 112, 114))
        for bit, k, empt, rk, dest in entries:
            if ca & bit and bd[rk] == 4 * us and all(bd[s] == 0 for s in empt) and \
               not attacked(k, -us) and not attacked(empt[0], -us) and not attacked(dest, -us):
                mv.append(k | (dest << 7))
    return mv

def make(m):
    global sd, ca, ep, hm, key
    f, t = m & 127, (m >> 7) & 127
    pr = (m >> 14) & 7
    p = bd[f]
    cap = bd[t]
    old_ca, old_ep, old_hm, old_key = ca, ep, hm, key
    # hash out old castling
    key ^= Z_CAST[ca]
    ep = -1
    # castling rights lost by king/rook move or rook capture
    if p == 6: ca &= ~3
    elif p == -6: ca &= ~12
    if f == 0 or t == 0: ca &= ~2
    if f == 7 or t == 7: ca &= ~1
    if f == 112 or t == 112: ca &= ~8
    if f == 119 or t == 119: ca &= ~4
    hm += 1
    if abs(p) == 1:
        hm = 0
        if t - f == 32 or f - t == 32:
            ep = (f + t) // 2
    if cap:
        hm = 0
    # en passant capture
    epcap = -1
    if abs(p) == 1 and t == old_ep and cap == 0:
        epcap = t - 16 if sd > 0 else t + 16
        cap = bd[epcap]
        bd[epcap] = 0
        key ^= ZOB[(cap - 1) if cap > 0 else (5 - cap)][epcap]
    # move piece
    key ^= ZOB[(p - 1) if p > 0 else (5 - p)][f]
    bd[f] = 0
    np = pr * (1 if sd > 0 else -1) if pr else p
    bd[t] = np
    key ^= ZOB[(np - 1) if np > 0 else (5 - np)][t]
    if cap and epcap < 0:
        key ^= ZOB[(cap - 1) if cap > 0 else (5 - cap)][t]
    # castling rook: from = t+1 (kingside) or t-2 (queenside), to = t-1 / t+1
    if abs(p) == 6 and abs(t - f) == 2:
        rf = t + 1 if t in (6, 118) else t - 2
        rt = t - 1 if t in (6, 118) else t + 1
        bd[rt] = bd[rf]; bd[rf] = 0
        r = 3 if sd > 0 else 9
        key ^= ZOB[r][rf] ^ ZOB[r][rt]
    key ^= Z_CAST[ca]
    key ^= Z_SIDE
    sd = -sd
    stack.append((m, cap, epcap, old_ca, old_ep, old_hm, old_key))

def unmake():
    global sd, ca, ep, hm, key
    top = stack.pop()
    if top[0] == "null":
        _, old_ep, old_key = top
        sd = -sd
        ep, key = old_ep, old_key
        return
    m, cap, epcap, old_ca, old_ep, old_hm, old_key = top
    f, t = m & 127, (m >> 7) & 127
    pr = (m >> 14) & 7
    p = bd[t]
    bd[t] = 0
    # restore mover: promotion restores a pawn, else the moved piece
    bd[f] = (1 if p > 0 else -1) * (1 if pr else abs(p))
    if epcap >= 0:
        bd[epcap] = cap
    elif cap:
        bd[t] = cap
    if abs(bd[f]) == 6 and abs(t - f) == 2:
        rf = t + 1 if t in (6, 118) else t - 2
        rt = t - 1 if t in (6, 118) else t + 1
        bd[rf] = 4 if bd[f] > 0 else -4; bd[rt] = 0
    ca, ep, hm, key = old_ca, old_ep, old_hm, old_key
    sd = -sd

def legal_moves(caps_only=False):
    out = []
    for m in gen_moves(caps_only):
        make(m)
        if not in_check(-sd):
            out.append(m)
        unmake()
    return out

# ---------- evaluation (white perspective) ----------
def evaluate():
    score = 0
    phase = 0
    wk = bk = 0
    for s in range(128):
        if s & 0x88: continue
        p = bd[s]
        if not p: continue
        a = abs(p)
        r, f = s >> 4, s & 7
        if p > 0:
            idx = (7 - r) * 8 + f
            score += VAL[a] + PST[a][idx]
            if a == 6: wk = idx
        else:
            idx = r * 8 + f
            score -= VAL[a] + PST[a][idx]
            if a == 6: bk = idx
        if a in (2, 3): phase += 1
        elif a == 4: phase += 2
        elif a == 5: phase += 4
    # endgame king table blend
    if phase <= 6:
        score += KING_EG[wk] - KING_MG[wk] - KING_EG[bk] + KING_MG[bk]
    return score if sd > 0 else -score

# ---------- search ----------
def order(moves, tt_move, ply):
    def sc(m):
        t = (m >> 7) & 127
        v = bd[t]
        s = 0
        if m == tt_move: s = 1000000
        elif v:
            s = 10000 + VAL[abs(v)] * 10 - VAL[abs(bd[m & 127])] // 10
        elif m == KILL[ply][0]: s = 5000
        elif m == KILL[ply][1]: s = 4000
        return -s
    moves.sort(key=sc)
    return moves

def qs(alpha, beta, ply):
    global nodes
    nodes += 1
    if nodes > LIMIT: raise Abort()
    if key in PATH: return 0
    stand = evaluate()
    if stand >= beta: return beta
    if stand > alpha: alpha = stand
    chk = in_check(sd)
    if chk:
        moves = legal_moves()
    else:
        moves = legal_moves(caps_only=True)
        # delta pruning: skip captures far below alpha
        moves = [m for m in moves if VAL[abs(bd[(m >> 7) & 127])] + 200 > alpha - stand
                 or ((m >> 14) & 7) or bd[(m >> 7) & 127] == 0]
    order(moves, 0, ply)
    for m in moves:
        PATH.append(key)
        make(m)
        s = -qs(-beta, -alpha, ply + 1)
        unmake()
        PATH.pop()
        if s >= beta: return beta
        if s > alpha: alpha = s
    return alpha

def search(depth, alpha, beta, ply, do_null=True):
    global nodes
    nodes += 1
    if nodes > LIMIT: raise Abort()
    if hm >= 100: return 0
    if key in PATH: return 0
    if depth <= 0:
        return qs(alpha, beta, ply)
    # mate-distance pruning
    alpha = max(alpha, -MATE + ply)
    beta = min(beta, MATE - ply)
    if alpha >= beta: return alpha
    chk = in_check(sd)
    # TT probe
    tt = TT.get(key)
    tt_move = 0
    if tt and tt[0] >= depth:
        _, flag, sc, mv = tt
        if flag == 0: return sc
        if flag == 1: alpha = max(alpha, sc)
        elif flag == 2: beta = min(beta, sc)
        if alpha >= beta: return sc
        tt_move = mv
    if not chk and do_null and depth >= 3 and evaluate() >= beta + 50:
        # null move (undo info lives on the stack, so an Abort unwinds it too)
        PATH.append(key)
        make_null()
        s = -search(depth - 1 - (3 if depth > 6 else 2), -beta, -beta + 1, ply + 1, False)
        unmake()
        PATH.pop()
        if s >= beta:
            return beta
    moves = legal_moves()
    if not moves:
        return -MATE + ply if chk else 0
    order(moves, tt_move, ply)
    best = -MATE
    best_m = moves[0]
    flag = 2
    for i, m in enumerate(moves):
        is_cap = bd[(m >> 7) & 127] != 0 or ((m >> 14) & 7)
        PATH.append(key)
        make(m)
        if i == 0:
            s = -search(depth - 1, -beta, -alpha, ply + 1)
        else:
            # PVS null window
            red = 0
            if depth >= 3 and i >= 4 and not is_cap and not chk:
                red = 1
            s = -search(depth - 1 - red, -alpha - 1, -alpha, ply + 1)
            if s > alpha and (red or s < beta):
                s = -search(depth - 1, -beta, -alpha, ply + 1)
        unmake()
        PATH.pop()
        if s > best:
            best = s; best_m = m
        if s > alpha:
            alpha = s; flag = 0
            if alpha >= beta:
                if not is_cap:
                    if m != KILL[ply][0]:
                        KILL[ply][1] = KILL[ply][0]
                        KILL[ply][0] = m
                flag = 1
                break
    if len(TT) > 300000: TT.clear()
    TT[key] = (depth, flag, best, best_m)
    return best

def make_null():
    global sd, ep, key
    stack.append(("null", ep, key))
    ep = -1
    key ^= Z_SIDE
    sd = -sd

def best_move(node_limit):
    global nodes, LIMIT
    LIMIT = node_limit
    nodes = 0
    PATH.clear()
    stack_base = len(stack)
    root = legal_moves()
    if not root: return 0
    if len(root) == 1: return root[0]
    best_m, best_s = root[0], -MATE
    depth = 1
    try:
        while depth <= 64:
            alpha = -MATE; beta = MATE
            cur_best, cur_s = best_m, -MATE
            # order root: previous best first
            root.sort(key=lambda m: 0 if m == best_m else 1)
            for i, m in enumerate(root):
                PATH.append(key)
                make(m)
                if i == 0:
                    s = -search(depth - 1, -beta, -alpha, 1)
                else:
                    s = -search(depth - 1, -alpha - 1, -alpha, 1)
                    if s > alpha:
                        s = -search(depth - 1, -beta, -alpha, 1)
                unmake()
                PATH.pop()
                if s > cur_s:
                    cur_s, cur_best = s, m
                if s > alpha: alpha = s
            best_m, best_s = cur_best, cur_s
            depth += 1
    except Abort:
        # search aborted mid-tree: unwind only the makes this call added
        while len(stack) > stack_base:
            unmake()
        PATH.clear()
        pass
    return best_m

# ---------- perft (testing) ----------
def perft(d):
    if d == 0: return 1
    n = 0
    for m in legal_moves():
        make(m)
        n += perft(d - 1)
        unmake()
    return n

# ---------- env driver ----------
def post(url, path, body):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req) as res:
        return json.load(res)

def main():
    env = os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")
    node_limit = int(os.environ.get("TC_NODES", "60000"))
    while True:
        g = post(env, "/game", {})
        if g["status"] == "done":
            break
        while g["status"] == "your_move":
            parse_fen(g["fen"])
            ROOT_HIST[key] = ROOT_HIST.get(key, 0) + 1
            PATH.clear()
            m = best_move(node_limit)
            legal = g["legal_moves"]
            u = move_uci(m) if m else None
            if u not in legal:
                # safety: should never happen (move gen is perft-verified)
                u = legal[0]
            g = post(env, "/move", {"game": g["game"], "move": u})

if __name__ == "__main__":
    main()

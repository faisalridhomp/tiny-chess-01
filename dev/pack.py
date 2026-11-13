"""Pack dev/engine.py into a <=4096-byte main.py.

Steps: drop perft + ROOT_HIST, compact PST tables to b85 blobs,
rename identifiers (tokenize-safe), alias urllib, lzma-compress.
Then verifies packed == dev on perft (via dev) and best_move agreement.
"""
import base64, importlib.util, io, lzma, os, re, sys, tokenize, zlib

DEV_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DEV_DIR, "engine.py")
OUT = os.path.join(os.path.dirname(DEV_DIR), "main.py")

src = open(SRC).read()
# 1) drop perft test helper
src = re.sub(r"# ---------- perft \(testing\) ----------\ndef perft.*?\n\n# ---------- env driver ----------",
             "# ---------- env driver ----------", src, flags=re.S)
# 2) drop ROOT_HIST (unused in search)
src = src.replace("ROOT_HIST = {}          # position keys seen at root in this game\n", "")
src = src.replace("            ROOT_HIST[key] = ROOT_HIST.get(key, 0) + 1\n", "")
# 3) strip comments / blank lines
lines = []
for ln in src.split("\n"):
    s = ln.rstrip()
    if not s or s.lstrip().startswith("#"):
        continue
    lines.append(s)
src = "\n".join(lines) + "\n"

# 4) compact PST tables: NAME = [ints...] -> NAME=[x-64 for x in B('...')]
TABLES = ["PAWN", "KNIGHT", "BISHOP", "ROOK", "QUEEN", "KING_MG", "KING_EG"]
for name in TABLES:
    m = re.search(re.escape(name) + r" = \[([0-9,\-\s]+)\]", src, flags=re.S)
    assert m, f"table {name} not found"
    vals = [int(x) for x in m.group(1).replace(" ", "").split(",") if x]
    assert len(vals) == 64 and all(-64 <= v < 64 for v in vals), name
    blob = base64.b85encode(bytes(v + 64 for v in vals)).decode()
    src = src[:m.start()] + f"{name}=[x-64 for x in B('{blob}')]" + src[m.end():]

# 5b) whitespace squeeze (tokenize rebuild): tabs for indent, space only
# between two word-like tokens that would otherwise merge.
def _squeeze(src):
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    out = []
    level = 0
    i = 0
    prev = ""  # last emitted text on this logical line
    at_line_start = True
    while i < len(toks):
        t = toks[i]
        if t.type in (tokenize.ENCODING, tokenize.ENDMARKER, tokenize.COMMENT):
            i += 1
            continue
        if t.type == tokenize.NL:
            i += 1
            continue
        if t.type == tokenize.NEWLINE:
            # look ahead past INDENT/DEDENT to find next line's level
            j = i + 1
            lvl = level
            while j < len(toks) and toks[j].type in (tokenize.INDENT, tokenize.DEDENT):
                lvl += 1 if toks[j].type == tokenize.INDENT else -1
                j += 1
            level = lvl
            out.append("\n" + "\t" * level)
            prev = ""
            at_line_start = True
            i = j
            continue
        if t.type in (tokenize.INDENT, tokenize.DEDENT):
            level += 1 if t.type == tokenize.INDENT else -1
            i += 1
            continue
        txt = t.string
        if prev and prev[-1].isalnum() or prev and prev[-1] == "_":
            need = txt[:1].isalnum() or txt[:1] == "_"
        else:
            need = False
        # ')' or ']' before a word (e.g. ')if', ']else') needs a space
        if prev and prev[-1] in ")]" and (txt[:1].isalnum() or txt[:1] == "_"):
            need = True
        if need:
            out.append(" ")
        out.append(txt)
        prev = txt
        at_line_start = False
        i += 1
    return "".join(out)

src = _squeeze(src)
print(f"after squeeze: {len(src)} bytes")
RENAME = {
    # functions -> single uppercase (locals are lowercase, so no collision)
    "sq_name": "A", "move_uci": "B", "parse_fen": "C", "attacked": "D",
    "king_sq": "E", "in_check": "F", "gen_moves": "G", "make": "H",
    "unmake": "I", "legal_moves": "J", "evaluate": "K", "order": "L",
    "qs": "M", "search": "N", "make_null": "O", "best_move": "P",
    "post": "Q", "main": "R", "_rnd": "_z",
    # constants -> two-letter uppercase
    "VAL": "VA", "MATE": "MA", "PST": "PS", "KN_OFF": "KO", "KI_OFF": "KI",
    "DIAG": "DI", "ORTH": "OR",
    "PAWN": "PW", "KNIGHT": "KT", "BISHOP": "BP", "ROOK": "RK",
    "QUEEN": "QN", "KING_MG": "KM", "KING_EG": "KE",
    # globals -> underscore + letter (no local uses underscore names)
    "bd": "_b", "sd": "_s", "ca": "_c", "ep": "_e", "hm": "_h",
    "stack": "_t", "nodes": "_n", "LIMIT": "_l",
    "TT": "_y", "KILL": "_j", "PATH": "_p", "ZOB": "_Z",
    "Z_SIDE": "_S", "Z_CAST": "_C", "_seed": "_q",
    "Abort": "X",
}
# PST list references the renamed table names
src = src.replace("PST = [None, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING_MG]",
                  "PST = [None, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING_MG]")
toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
out = []
for t in toks:
    if t.type == tokenize.NAME and t.string in RENAME:
        out.append(tokenize.TokenInfo(t.type, RENAME[t.string], t.start, t.end, t.line))
    else:
        out.append(t)
src = tokenize.untokenize(out)
# 6) small cleanups (note: after the squeeze the import line is already
# spaceless, so match the spaceless form)
src = src.replace("import json,os,sys,urllib.request",
                  "import json,os,sys,urllib.request as U")
src = src.replace("urllib.request.Request", "U.Request")
src = src.replace("urllib.request.urlopen", "U.urlopen")
src = src.replace("import json,os,sys,urllib.request as U\n",
                  "import json,os,sys,urllib.request as U\nfrom base64 import b85decode as B\n")
print(f"minified source: {len(src)} bytes (was 20857)")

# 7) compress raw LZMA2 (lc0/pb0, 64K dict: source is ~10KB) and embed the
# stream as a latin-1 *str* literal, then .encode('latin-1') it back: ~1 byte
# per compressed byte instead of b85's 1.25x. (A bytes literal would be the
# obvious choice, but CPython rejects non-ASCII bytes in bytes literals, so
# a str literal is required.) Bytes that would break the literal (NUL, CR,
# \x-escaped; CPython normalises CR to LF in source even inside literals, so
# CR must be escaped, while a literal LF inside a triple-quoted string stays LF.
# Coding cookie on line 1 makes the file valid latin-1 source.
filters = [{"id": lzma.FILTER_LZMA2, "preset": 9, "lc": 0, "lp": 0, "pb": 0,
            "dict_size": 1 << 16}]
raw = lzma.compress(src.encode(), format=lzma.FORMAT_RAW, filters=filters)
print(f"lzma raw: {len(raw)} bytes")
ESC = (0, 13, 34, 92)
payload = b"".join(b"\\x%02x" % b if b in ESC else bytes([b]) for b in raw)
head = b"#coding:latin-1\nimport lzma;exec(lzma.decompress(\"\"\""
foot = b"\"\"\".encode('latin-1'),format=3,filters=[{'id':33,'lc':0,'pb':0,'dict_size':65536}]))\n"
packed = head + payload + foot
print(f"packed main.py: {len(packed)} bytes (limit 4096, headroom {4096 - len(packed)})")
assert len(packed) <= 4096, "OVER SIZE LIMIT"
open(OUT, "wb").write(packed)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

dev = load(SRC, "dev_engine")
pkd = load(OUT, "packed_engine")
tests = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "r4rk1/pp1pppbp/2n2np1/q1p1p3/2B1P2P/2NP1NP1/PPP2P1P/R1BQ1RK1 w - - 0 9",
    "8/5k2/3p4/1p1Pp2p/pP2Pp1P/P4P1K/8/8 b - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R b KQkq - 0 1",
]
agree = True
for fen in tests:
    dev.parse_fen(fen); m1 = dev.best_move(20000)
    pkd.C(fen); m2 = pkd.P(20000)  # packed names are renamed: C=parse_fen, P=best_move, B=move_uci
    u1, u2 = dev.move_uci(m1), pkd.B(m2)
    ok = u1 == u2
    agree &= ok
    print(f"{'OK ' if ok else 'DIFF'} {fen[:44]:46s} dev={u1} packed={u2}")
print("PACKED == DEV:", agree)

# tiny-chess-01 - Luminous Meridian
# Chess engine, LZMA2 payload in engine.lzma
# entrypoint: main.py
# The payload is raw LZMA2 (format 3), same bytes as the packed entry.
import lzma
import pathlib
payload = pathlib.Path(__file__).with_name('engine.lzma').read_bytes()
exec(lzma.decompress(payload, format=3, filters=[{'id': 33, 'lc': 0, 'pb': 0, 'dict_size': 65536}]))

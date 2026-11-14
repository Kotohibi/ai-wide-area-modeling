"""Zoomed route-unwrapped map for one section (reads unwrap.py's projection logic on the leveled sparse cloud).

usage: python unwrap_zoom.py <scratch_dir> <s0> <s1> <lat0> <lat1> <px_per_unit> <zlo> <zhi> <out.png>
Horizontal axis = route distance s, vertical = lateral offset (top = +lat, right of travel).
Points with zlo < z' < zhi are drawn in their own colour, brighter = denser. Ticks every 5 (long every 10) units.
"""
import sys, os, json, zlib, struct, numpy as np
SP = sys.argv[1]; S0, S1, LAT0, LAT1, SC, ZLO, ZHI = [float(v) for v in sys.argv[2:9]]; OUT = sys.argv[9]
SH = os.environ.get("BLENDER_SHARED", "")
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
L = np.load(SP + r"\lP.npy"); C = np.load(SP + r"\lC.npy")
Pp = np.array(json.load(open(SH + r"\path_level.json"))["path"])
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
m = (L[:, 2] > ZLO) & (L[:, 2] < ZHI); L = L[m]; C = C[m]
sel = (Pp[:, 0] > S0 - 10) & (Pp[:, 0] < S1 + 10); Q = Pp[sel]; tq = t[sel]; nq = nr[sel]
box = (L[:, 0] > Q[:, 1].min() - 45) & (L[:, 0] < Q[:, 1].max() + 45) & (L[:, 1] > Q[:, 2].min() - 45) & (L[:, 1] < Q[:, 2].max() + 45)
L = L[box]; C = C[box]
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(Q)):
    d2 = (L[:, 0] - Q[i, 1]) ** 2 + (L[:, 1] - Q[i, 2]) ** 2
    mm = d2 < best; best[mm] = d2[mm]; idx[mm] = i
lat = (L[:, 0] - Q[idx, 1]) * nq[idx, 0] + (L[:, 1] - Q[idx, 2]) * nq[idx, 1]
al = (L[:, 0] - Q[idx, 1]) * tq[idx, 0] + (L[:, 1] - Q[idx, 2]) * tq[idx, 1]
sv = Q[idx, 0] - al
ok = (sv > S0) & (sv < S1) & (lat > LAT0) & (lat < LAT1); sv, lat, C, z = sv[ok], lat[ok], C[ok], L[ok, 2]
W = int((S1 - S0) * SC); H = int((LAT1 - LAT0) * SC)
img = np.zeros((H, W, 3), np.uint8)
o = np.argsort(z)
ix = ((sv[o] - S0) * SC).astype(int).clip(0, W - 1); iy = ((LAT1 - lat[o]) * SC).astype(int).clip(0, H - 1)
img[iy, ix] = C[o]
for v in np.arange(np.ceil(S0 / 5) * 5, S1, 5):
    x = int((v - S0) * SC); img[0:(18 if v % 10 == 0 else 8), x] = (255, 255, 255)
for v in np.arange(np.ceil(LAT0 / 5) * 5, LAT1, 5):
    y = min(H - 1, int((LAT1 - v) * SC)); img[y, 0:(18 if v % 10 == 0 else 8)] = (255, 255, 0)
y0 = int(LAT1 * SC)
if 0 <= y0 < H: img[y0, ::5] = (0, 140, 255)
save_png(OUT, np.ascontiguousarray(img)); print("unwrap_zoom", W, H, "points", int(ok.sum()))

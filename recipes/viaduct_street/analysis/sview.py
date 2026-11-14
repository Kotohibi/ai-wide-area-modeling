# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, zlib, struct, numpy as np
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
# usage: sview.py SP kind slab_lo slab_hi u0 u1 v0 v1 S out [minop]
#   cross: slab on y(forward),  horizontal x, vertical h
#   long : slab on x,           horizontal y, vertical h
#   top  : slab on h,           horizontal x, vertical y
SP, kind = sys.argv[1], sys.argv[2]
s0, s1, u0, u1, v0, v1, S = [float(v) for v in sys.argv[3:10]]
out = sys.argv[10]; minop = float(sys.argv[11]) if len(sys.argv) > 11 else 0.0
import os
PF = os.environ.get("PFX", "s")
P = np.load(SP + "\\" + PF + "P.npy"); C = np.load(SP + "\\" + PF + "C.npy"); O = np.load(SP + "\\" + PF + "O.npy")
x, y, h = P[:, 0], P[:, 1], P[:, 2]
if kind == "cross": slab, hz, vt = y, x, h
elif kind == "long": slab, hz, vt = x, y, h
else: slab, hz, vt = h, x, y
m = (slab > s0) & (slab < s1) & (hz > u0) & (hz < u1) & (vt > v0) & (vt < v1) & (O >= minop)
W = int((u1 - u0) * S); H = int((v1 - v0) * S)
img = np.zeros((H, W, 3), np.uint8) + 25
hz, vt, cc, sl = hz[m], vt[m], C[m], slab[m]
order = np.argsort(-sl) if kind != "top" else np.argsort(sl)
ix = ((hz[order] - u0) * S).astype(int).clip(0, W - 1); iy = ((v1 - vt[order]) * S).astype(int).clip(0, H - 1)
img[iy, ix] = cc[order]
for t in range(int(np.ceil(u0)), int(u1) + 1):
    px = int((t - u0) * S)
    if 0 <= px < W: img[0:(16 if t % 5 == 0 else 6), px] = (0, 255, 0)
for t in range(int(np.ceil(v0)), int(v1) + 1):
    py = int((v1 - t) * S)
    if 0 <= py < H: img[py, 0:(16 if t % 5 == 0 else 6)] = (0, 255, 0)
save_png(out, np.ascontiguousarray(img)); print("pts", int(m.sum()), "img", W, H)

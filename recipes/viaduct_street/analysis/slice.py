import sys, zlib, struct, numpy as np
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
SP = sys.argv[1]
kind = sys.argv[2]                    # cross | long | top
a0, a1 = float(sys.argv[3]), float(sys.argv[4])   # slab range on the third axis
u0, u1 = float(sys.argv[5]), float(sys.argv[6])   # horizontal range
S = float(sys.argv[7]); hmax = float(sys.argv[8])
out = sys.argv[9]
M = np.array([[0.965509831905365, 0.26036858558654785, 0], [0.26036858558654785, -0.965509831905365, 0], [0, 0, -1]], np.float32)
pw = np.load(SP + r"\near_p.npy"); c = np.load(SP + r"\near_c.npy")
p = pw @ M.T
g = np.load(SP + r"\ground.npy"); n = g[0:3]; cen = g[3:6]; cam = g[6:9]
up = -n
fwd = np.array([0, 0, 1.0]); fwd = fwd - (fwd @ up) * up; fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, up); right /= np.linalg.norm(right)
rel = p - cam
x = rel @ right; y = rel @ fwd; h = rel @ up + ((cam - cen) @ up)
np.save(SP + r"\basis.npy", np.concatenate([right, fwd, up]))
if kind == "cross":   # slab on y, horizontal = x
    m = (y > a0) & (y < a1) & (x > u0) & (x < u1) & (h > -0.5) & (h < hmax); hz = x; dep = y
elif kind == "long":  # slab on x, horizontal = y
    m = (x > a0) & (x < a1) & (y > u0) & (y < u1) & (h > -0.5) & (h < hmax); hz = y; dep = x
else:                 # top view, slab on h, horizontal = x, vertical = y
    m = (h > a0) & (h < a1) & (x > u0) & (x < u1) & (y > float(sys.argv[10])) & (y < float(sys.argv[11])); hz = x; dep = h
Wp = int((u1 - u0) * S)
if kind == "top":
    y0, y1 = float(sys.argv[10]), float(sys.argv[11])
    Hp = int((y1 - y0) * S); vv = y; vlo, vhi = y0, y1
else:
    Hp = int((hmax + 0.5) * S); vv = h; vlo, vhi = -0.5, hmax
img = np.zeros((Hp, Wp, 3), np.uint8) + 25
hz, vv, cc, dep = hz[m], vv[m], c[m], dep[m]
order = np.argsort(-dep)             # nearest slab depth drawn last
ix = ((hz[order] - u0) * S).astype(int).clip(0, Wp - 1)
iy = ((vhi - vv[order]) * S).astype(int).clip(0, Hp - 1)
img[iy, ix] = cc[order]
for t in range(int(np.ceil(u0)), int(u1) + 1):
    px = int((t - u0) * S)
    if 0 <= px < Wp: img[0:(14 if t % 5 == 0 else 6), px] = (0, 255, 0)
for t in range(int(np.ceil(vlo)), int(vhi) + 1):
    py = int((vhi - t) * S)
    if 0 <= py < Hp: img[py, 0:(14 if t % 5 == 0 else 6)] = (0, 255, 0)
save_png(out, np.ascontiguousarray(img)); print("pts", int(m.sum()), "img", Wp, Hp)

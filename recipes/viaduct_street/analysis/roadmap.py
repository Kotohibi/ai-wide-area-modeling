import sys, zlib, struct, numpy as np
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
SP = sys.argv[1]
R = float(sys.argv[2]); S = float(sys.argv[3])   # radius (units), px per unit
mode = sys.argv[4]                                # "ground" or "under"
M = np.array([[0.965509831905365, 0.26036858558654785, 0], [0.26036858558654785, -0.965509831905365, 0], [0, 0, -1]], np.float32)
pw = np.load(SP + r"\near_p.npy"); c = np.load(SP + r"\near_c.npy")
p = pw @ M.T
g = np.load(SP + r"\ground.npy"); n = g[0:3]; cen = g[3:6]; cam = g[6:9]
up = -n
# plane basis: ex along camera forward projected on plane (raw camera looks -Z-ish), ey = right
fwd = np.array([0, 0, -1.0]); fwd = fwd - (fwd @ up) * up; fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, up); right /= np.linalg.norm(right)
rel = p - cam
x = rel @ right; y = rel @ fwd; h = rel @ up + ((cam - cen) @ up)   # h = height above ground
np.save(SP + r"\basis.npy", np.concatenate([right, fwd, up]))
if mode == "ground":
    m = (np.abs(h) < 0.12) & (np.abs(x) < R) & (np.abs(y) < R)
else:
    lo, hi = float(sys.argv[5]), float(sys.argv[6])
    m = (h > lo) & (h < hi) & (np.abs(x) < R) & (np.abs(y) < R)
x, y, h, cc = x[m], y[m], h[m], c[m]
W = int(2 * R * S)
img = np.zeros((W, W, 3), np.uint8) + 25
order = np.argsort(h) if mode == "ground" else np.argsort(-h)
ix = ((x[order] + R) * S).astype(int).clip(0, W - 1)
iy = ((R - y[order]) * S).astype(int).clip(0, W - 1)   # forward = up in the image
img[iy, ix] = cc[order]
cx = int(R * S); cy = int(R * S)
img[cy-3:cy+4, cx-3:cx+4] = (255, 0, 0)
# 5-unit grid ticks on the border
for t in range(-int(R) // 5 * 5, int(R) + 1, 5):
    px = int((t + R) * S)
    if 0 <= px < W:
        img[0:8, px] = (0, 255, 0); img[W-8:W, px] = (0, 255, 0); img[px, 0:8] = (0, 255, 0); img[px, W-8:W] = (0, 255, 0)
save_png(SP + r"\map_%s.png" % mode, np.ascontiguousarray(img))
print("pts", len(x), "img", W)

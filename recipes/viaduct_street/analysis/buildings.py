# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, json, zlib, struct, numpy as np
SP = sys.argv[1]
import os; SHARED = os.environ.get("BLENDER_SHARED", "")
CELL = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
THR = int(sys.argv[3]) if len(sys.argv) > 3 else 10
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
L = np.load(SP + r"\lP.npy"); C = np.load(SP + r"\lC.npy")
pl = json.load(open(SHARED + r"\path_level.json"))["path"]; Pp = np.array(pl)
# path frame
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
# keep a working window around the route
lo = Pp[:, 1:3].min(0) - 90; hi = Pp[:, 1:3].max(0) + 90
w = (L[:, 0] > lo[0]) & (L[:, 0] < hi[0]) & (L[:, 1] > lo[1]) & (L[:, 1] < hi[1]) & (L[:, 2] > 2.5) & (L[:, 2] < 45)
L = L[w]; C = C[w]
# drop vegetation (greener than red/blue)
veg = (C[:, 1].astype(int) > C[:, 0].astype(int) + 12) & (C[:, 1].astype(int) > C[:, 2].astype(int) + 6)
L = L[~veg]; C = C[~veg]
# viaduct corridor mask by nearest path station
lat = np.empty(len(L), np.float32); dist = np.full(len(L), 1e9, np.float32)
for i in range(len(Pp)):
    d2 = (L[:, 0] - Pp[i, 1]) ** 2 + (L[:, 1] - Pp[i, 2]) ** 2
    m = d2 < dist
    dist[m] = d2[m]; lat[m] = ((L[m, 0] - Pp[i, 1]) * nr[i, 0] + (L[m, 1] - Pp[i, 2]) * nr[i, 1])
dist = np.sqrt(dist)
viad = (lat > -5) & (lat < 20) & (dist < 24) & (L[:, 2] < 9.8)
L = L[~viad]; C = C[~viad]
print("candidate building points", len(L))
# occupancy grid
x0, y0 = lo; W = int((hi[0] - x0) / CELL) + 1; H = int((hi[1] - y0) / CELL) + 1
ix = ((L[:, 0] - x0) / CELL).astype(int); iy = ((L[:, 1] - y0) / CELL).astype(int)
cnt = np.zeros((H, W), np.int32); np.add.at(cnt, (iy, ix), 1)
occ = cnt >= THR
# connected components (8-neighbour flood fill)
lab = np.zeros((H, W), np.int32); k = 0
for yy in range(H):
    for xx in range(W):
        if occ[yy, xx] and lab[yy, xx] == 0:
            k += 1; stack = [(yy, xx)]; lab[yy, xx] = k
            while stack:
                cy, cx = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and occ[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = k; stack.append((ny, nx))
pl_lab = lab[iy, ix]
boxes = []
for q in range(1, k + 1):
    m = (pl_lab == q)
    if m.sum() < 200: continue
    pts0 = L[m]; xy0 = pts0[:, :2]
    ctr0 = xy0.mean(0); u0, s0, vt0 = np.linalg.svd(xy0 - ctr0, full_matrices=False)
    ext = np.ptp((xy0 - ctr0) @ vt0[0])
    nchunk = max(1, int(np.ceil(ext / 40.0)))               # split long components along their main axis
    pa_all = (xy0 - ctr0) @ vt0[0]; edges = np.linspace(pa_all.min() - 1e-3, pa_all.max() + 1e-3, nchunk + 1)
    for ci in range(nchunk):
        mm = (pa_all >= edges[ci]) & (pa_all < edges[ci + 1])
        if mm.sum() < 150: continue
        pts = pts0[mm]; xy = pts[:, :2]
        ctr = xy.mean(0); u, s, vt = np.linalg.svd(xy - ctr, full_matrices=False)
        ax = vt[0]; ay = vt[1]
        pa = (xy - ctr) @ ax; pb = (xy - ctr) @ ay
        a0, a1 = np.percentile(pa, [2, 98]); b0, b1 = np.percentile(pb, [2, 98])
        wd, dp = a1 - a0, b1 - b0
        ht = float(np.percentile(pts[:, 2], 92))
        if max(wd, dp) < 8 or ht < 6: continue
        cen = ctr + ax * (a0 + a1) / 2 + ay * (b0 + b1) / 2
        ang = float(np.arctan2(ax[1], ax[0]))
        ratio = max(wd, dp) / max(1e-6, min(wd, dp))
        boxes.append(dict(cx=float(cen[0]), cy=float(cen[1]), w=float(wd), d=float(dp), ang=ang, h=ht, n=int(mm.sum()), ratio=float(ratio)))
boxes.sort(key=lambda b: -b["n"])
boxes = boxes[:40]
json.dump(boxes, open(SHARED + r"\buildings.json", "w"))
print("buildings", len(boxes))
for b in boxes[:30]:
    print(f"  c=({b['cx']:7.1f},{b['cy']:7.1f}) w={b['w']:5.1f} d={b['d']:5.1f} h={b['h']:5.1f} ang={np.degrees(b['ang']):6.1f} n={b['n']:6d} ratio={b['ratio']:.1f}")
# overlay image
S = 3.0
Wp = int((hi[0] - lo[0]) * S); Hp = int((hi[1] - lo[1]) * S)
img = np.zeros((Hp, Wp, 3), np.uint8) + 20
o = np.argsort(L[:, 2]); px = ((L[o, 0] - lo[0]) * S).astype(int).clip(0, Wp - 1); py = ((hi[1] - L[o, 1]) * S).astype(int).clip(0, Hp - 1)
img[py, px] = C[o]
for b in boxes:
    ca, sa = np.cos(b["ang"]), np.sin(b["ang"])
    for tt in np.linspace(0, 1, 60):
        for (u_, v_) in ((tt, 0), (tt, 1), (0, tt), (1, tt)):
            lx = (u_ - 0.5) * b["w"]; ly = (v_ - 0.5) * b["d"]
            X = b["cx"] + lx * ca - ly * sa; Y = b["cy"] + lx * sa + ly * ca
            qx = int((X - lo[0]) * S); qy = int((hi[1] - Y) * S)
            if 0 <= qx < Wp and 0 <= qy < Hp: img[qy, qx] = (255, 40, 40)
for i in range(0, len(Pp), 1):
    qx = int((Pp[i, 1] - lo[0]) * S); qy = int((hi[1] - Pp[i, 2]) * S)
    if 0 <= qx < Wp and 0 <= qy < Hp: img[max(qy-1,0):qy+2, max(qx-1,0):qx+2] = (0, 255, 0)
save_png(SP + r"\bld_overlay.png", np.ascontiguousarray(img)); print("overlay", Wp, Hp)

import sys, json, zlib, struct, math, numpy as np
SP = sys.argv[1]; import os; SH = os.environ.get("BLENDER_SHARED", "")
m = json.load(open(SH + r"\ortho_photo_meta.json")); P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
cls = np.load(SP + r"\cls.npy").copy(); H2, W2 = cls.shape; R2 = m["res"] * 2
def box(a, r):
    c = np.pad(a.astype(np.float32), ((r + 1, r), (r + 1, r)), mode="edge").astype(np.float64).cumsum(0).cumsum(1)
    n = 2 * r + 1
    return ((c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)).astype(np.float32)
def comps_filter(mask, minsize):
    ys, xs = np.nonzero(mask); idx = {(y, x): i for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist()))}
    lab = -np.ones(len(ys), np.int32); keep = np.zeros(mask.shape, bool)
    for i in range(len(ys)):
        if lab[i] >= 0: continue
        st = [i]; lab[i] = i; mem = [i]
        while st:
            j = st.pop(); y, x = ys[j], xs[j]
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = idx.get((y + dy, x + dx))
                if q is not None and lab[q] < 0: lab[q] = i; st.append(q); mem.append(q)
        if len(mem) >= minsize: keep[ys[mem], xs[mem]] = True
    return keep
# buildings: no ground classes under them
blds = json.load(open(SH + r"\buildings_final2.json"))
gx = m["x0"] + (np.arange(W2) + 0.5) * R2; gy = m["y1"] - (np.arange(H2) + 0.5) * R2
under = np.zeros((H2, W2), bool)
for b in blds:
    ca, sa = math.cos(b["ang"]), math.sin(b["ang"])
    ext = max(b["w"], b["d"]) / 2 + 2
    ix0 = max(0, int((b["cx"] - ext - m["x0"]) / R2)); ix1 = min(W2, int((b["cx"] + ext - m["x0"]) / R2) + 1)
    iy0 = max(0, int((m["y1"] - (b["cy"] + ext)) / R2)); iy1 = min(H2, int((m["y1"] - (b["cy"] - ext)) / R2) + 1)
    xx, yy = np.meshgrid(gx[ix0:ix1], gy[iy0:iy1]); dx, dy = xx - b["cx"], yy - b["cy"]
    lx = dx * ca + dy * sa; ly = -dx * sa + dy * ca
    under[iy0:iy1, ix0:ix1] |= (np.abs(lx) < b["w"] / 2 + 0.5) & (np.abs(ly) < b["d"] / 2 + 0.5)
cls[under] = 0
road = box(cls == 1, 2) > 0.5                                     # smooth
road = comps_filter(road, 350)
road = box(box(road, 2) > 0.5, 2) > 0.5                           # open/close
near = box(road, 20) > 0.001                                      # within ~5 units of road
sw = (cls == 2) & ~road & near
sw = comps_filter(box(sw, 1) > 0.5, 120) & ~road
grass = comps_filter((cls == 3) & ~road & ~sw & (box(road, 60) > 0.001), 80)
print("road cells", int(road.sum()), "sidewalk", int(sw.sum()), "grass", int(grass.sum()))
def runs_to_quads(mask, z):
    V, F, UV = [], [], []
    for y in range(H2):
        row = mask[y]; x = 0
        while x < W2:
            if row[x]:
                x0 = x
                while x < W2 and row[x]: x += 1
                xa = m["x0"] + x0 * R2; xb = m["x0"] + x * R2; ya = m["y1"] - (y + 1) * R2; yb = m["y1"] - y * R2
                n = len(V)
                V += [(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)]
                UV += [((xa - m["x0"]) / (m["x1"] - m["x0"]), (ya - m["y0"]) / (m["y1"] - m["y0"])), ((xb - m["x0"]) / (m["x1"] - m["x0"]), (ya - m["y0"]) / (m["y1"] - m["y0"])),
                       ((xb - m["x0"]) / (m["x1"] - m["x0"]), (yb - m["y0"]) / (m["y1"] - m["y0"])), ((xa - m["x0"]) / (m["x1"] - m["x0"]), (yb - m["y0"]) / (m["y1"] - m["y0"]))]
                F.append((n, n + 1, n + 2, n + 3))
            else: x += 1
    return np.array(V, np.float32), np.array(F, np.int32), np.array(UV, np.float32)
rv, rf, ruv = runs_to_quads(road, 0.0)
sv_, sf, suv = runs_to_quads(sw, 0.10)
gv, gf, guv = runs_to_quads(grass, -0.01)
# curb walls: sidewalk cell run edges touching road
cv, cf = [], []
for y in range(1, H2 - 1):
    for x in range(1, W2 - 1):
        if sw[y, x]:
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if road[y + dy, x + dx]:
                    xa = m["x0"] + x * R2; ya = m["y1"] - (y + 1) * R2
                    if dx == 1: pts = [(xa + R2, ya, 0), (xa + R2, ya + R2, 0), (xa + R2, ya + R2, 0.1), (xa + R2, ya, 0.1)]
                    elif dx == -1: pts = [(xa, ya + R2, 0), (xa, ya, 0), (xa, ya, 0.1), (xa, ya + R2, 0.1)]
                    elif dy == 1: pts = [(xa, ya, 0), (xa + R2, ya, 0), (xa + R2, ya, 0.1), (xa, ya, 0.1)]
                    else: pts = [(xa + R2, ya + R2, 0), (xa, ya + R2, 0), (xa, ya + R2, 0.1), (xa + R2, ya + R2, 0.1)]
                    n = len(cv); cv += pts; cf.append((n, n + 1, n + 2, n + 3))
np.savez(SH + r"\ground_mesh.npz", rv=rv, rf=rf, ruv=ruv, sv=sv_, sf=sf, suv=suv, gv=gv, gf=gf, guv=guv, cv=np.array(cv, np.float32), cf=np.array(cf, np.int32))
print("quads: road", len(rf), "sidewalk", len(sf), "grass", len(gf), "curb", len(cf))
pal = np.array([[30, 32, 30], [60, 62, 68], [170, 160, 140], [70, 120, 60]], np.uint8)
out = np.zeros((H2, W2), np.uint8); out[grass] = 3; out[sw] = 2; out[road] = 1
def save_png(path, a):
    h, w, c = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        cc = struct.pack(">I", len(d)) + t + d
        return cc + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
save_png(SP + r"\ground_cls.png", np.ascontiguousarray(pal[out]))

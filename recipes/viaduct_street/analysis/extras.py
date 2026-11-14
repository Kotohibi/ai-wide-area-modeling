# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Detect transmission towers, utility poles and trees from the leveled sparse cloud (lP.npy / lC.npy).

usage: python extras.py <scratch_dir>
Writes $BLENDER_SHARED/extras.json = {"towers": [...], "poles": [...], "trees": [...]} in leveled units.
- towers : clusters reaching z' > 12 with a footprint < 9 units (lattice steel towers seen in the photos)
- poles  : very thin columns 5.5 < height < 12 (utility poles); street-furniture poles stay in poles.py
- trees  : connected clusters of green points above 1.2 units -> trunk + crown size
Excludes the viaduct corridor (lat -5..18 near the route below 9.8) and building outlines (auto + manual).
"""
import sys, os, json, math, numpy as np
SP = sys.argv[1]; SH = os.environ.get("BLENDER_SHARED", "")
L = np.load(SP + r"\lP.npy"); C = np.load(SP + r"\lC.npy").astype(int)
Pp = np.array(json.load(open(SH + r"\path_level.json"))["path"])
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
lo = Pp[:, 1:3].min(0) - 60; hi = Pp[:, 1:3].max(0) + 60
w = (L[:, 0] > lo[0]) & (L[:, 0] < hi[0]) & (L[:, 1] > lo[1]) & (L[:, 1] < hi[1]) & (L[:, 2] > 0.4) & (L[:, 2] < 60)
L = L[w]; C = C[w]
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(Pp)):
    d2 = (L[:, 0] - Pp[i, 1]) ** 2 + (L[:, 1] - Pp[i, 2]) ** 2; m = d2 < best; best[m] = d2[m]; idx[m] = i
lat = (L[:, 0] - Pp[idx, 1]) * nr[idx, 0] + (L[:, 1] - Pp[idx, 2]) * nr[idx, 1]
keep = ~((lat > -5) & (lat < 18) & (np.sqrt(best) < 25) & (L[:, 2] < 9.8))
def inside_buildings(X, Y, pad=1.5):
    m = np.zeros(len(X), bool)
    for fn in ("buildings_final2.json", "buildings_manual.json"):
        if not os.path.exists(SH + "\\" + fn): continue
        for b in json.load(open(SH + "\\" + fn)):
            if b.get("kind") == "cyl":
                m |= (X - b["cx"]) ** 2 + (Y - b["cy"]) ** 2 < (b["r"] + pad) ** 2; continue
            ca, sa = math.cos(b["ang"]), math.sin(b["ang"]); dx, dy = X - b["cx"], Y - b["cy"]
            m |= (np.abs(dx * ca + dy * sa) < b["w"] / 2 + pad) & (np.abs(-dx * sa + dy * ca) < b["d"] / 2 + pad)
    return m
keep &= ~inside_buildings(L[:, 0], L[:, 1])
L = L[keep]; C = C[keep]
green = (C[:, 1] > C[:, 0] + 10) & (C[:, 1] > C[:, 2] + 5)
def components(mask2d):
    ys, xs = np.nonzero(mask2d); lab = {}; comps = []
    for y, x in zip(ys.tolist(), xs.tolist()):
        if (y, x) in lab: continue
        st = [(y, x)]; lab[(y, x)] = len(comps); mem = [(y, x)]
        while st:
            cy, cx = st.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = (cy + dy, cx + dx)
                    if 0 <= q[0] < mask2d.shape[0] and 0 <= q[1] < mask2d.shape[1] and mask2d[q] and q not in lab:
                        lab[q] = len(comps); st.append(q); mem.append(q)
        comps.append(mem)
    return comps
def grid(Lsel, cell):
    W = int((hi[0] - lo[0]) / cell) + 1; H = int((hi[1] - lo[1]) / cell) + 1
    ix = ((Lsel[:, 0] - lo[0]) / cell).astype(int); iy = ((Lsel[:, 1] - lo[1]) / cell).astype(int)
    cnt = np.zeros((H, W), np.int32); np.add.at(cnt, (iy, ix), 1)
    zmax = np.full((H, W), -1.0, np.float32); np.maximum.at(zmax, (iy, ix), Lsel[:, 2])
    zmin = np.full((H, W), 99.0, np.float32); np.minimum.at(zmin, (iy, ix), Lsel[:, 2])
    return cnt, zmax, zmin, ix, iy
# ---- towers and utility poles (non-green)
NG = L[~green]
cnt, zmax, zmin, ix, iy = grid(NG, 1.0)
towers, poles = [], []
for mem in components((cnt >= 3) & (zmax > 5.5)):
    ys = np.array([m[0] for m in mem]); xs = np.array([m[1] for m in mem])
    ext = max(np.ptp(xs), np.ptp(ys)) + 1
    top = float(zmax[ys, xs].max()); bot = float(zmin[ys, xs].min()); n = int(cnt[ys, xs].sum())
    cxw = lo[0] + (xs.mean() + 0.5); cyw = lo[1] + (ys.mean() + 0.5)
    if top > 12 and ext <= 9 and n > 60:
        towers.append(dict(x=float(cxw), y=float(cyw), h=top, base=float(ext), n=n))
    elif 5.5 < top <= 12 and ext <= 2 and n >= 12 and bot < 3:
        poles.append(dict(x=float(cxw), y=float(cyw), h=top, n=n))
# ---- trees (green)
G = L[green & (L[:, 2] > 1.2)]
cnt, zmax, zmin, ix, iy = grid(G, 1.5)
trees = []
for mem in components(cnt >= 4):
    ys = np.array([m[0] for m in mem]); xs = np.array([m[1] for m in mem])
    n = int(cnt[ys, xs].sum())
    if n < 80 or float(zmax[ys, xs].max()) < 3.0: continue        # green fences, hedges and grass are not trees
    ext = (max(np.ptp(xs), np.ptp(ys)) + 1) * 1.5
    if ext > 14:                                   # hedges / tree rows: split into ~6-unit crowns
        pts = np.c_[xs, ys] * 1.5 + lo + 0.75
        k = max(1, int(ext / 6))
        c0 = pts.mean(0); u_, s_, vt = np.linalg.svd(pts - c0, full_matrices=False); pa = (pts - c0) @ vt[0]
        for e in np.linspace(pa.min(), pa.max(), k):
            cxy = c0 + vt[0] * e; trees.append(dict(x=float(cxy[0]), y=float(cxy[1]), h=float(zmax[ys, xs].max()), r=3.0))
    else:
        trees.append(dict(x=float(lo[0] + (xs.mean() + 0.5) * 1.5), y=float(lo[1] + (ys.mean() + 0.5) * 1.5), h=float(zmax[ys, xs].max()), r=float(max(1.2, ext / 2))))
# nothing stands on the surveyed walking path: drop trees / poles within 2.5 units of the route
def off_route(o, r=2.5):
    return np.min((Pp[:, 1] - o["x"]) ** 2 + (Pp[:, 2] - o["y"]) ** 2) > (r + o.get("r", 0)) ** 2
trees = [t for t in trees if off_route(t)]; poles = [p for p in poles if off_route(p, 1.5)]
# no trees under the viaduct decks (their 'height' is the deck picked up by the cluster)
def lat_of(o):
    i = int(np.argmin((Pp[:, 1] - o["x"]) ** 2 + (Pp[:, 2] - o["y"]) ** 2))
    return float((o["x"] - Pp[i, 1]) * nr[i, 0] + (o["y"] - Pp[i, 2]) * nr[i, 1]), float(np.hypot(o["x"] - Pp[i, 1], o["y"] - Pp[i, 2]))
trees = [t for t in trees if not (-4 < lat_of(t)[0] < 22 and lat_of(t)[1] < 24)]
json.dump(dict(towers=towers, poles=poles, trees=trees), open(SH + r"\extras.json", "w"))
print("towers", len(towers), "utility poles", len(poles), "trees", len(trees))
for tw in towers: print("  tower", {k: round(v, 1) for k, v in tw.items()})

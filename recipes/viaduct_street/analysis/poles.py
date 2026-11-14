import sys, json, math, numpy as np
SP = sys.argv[1]; import os; SH = os.environ.get("BLENDER_SHARED", "")
L = np.load(SP + r"\lP.npy"); C = np.load(SP + r"\lC.npy")
Pp = np.array(json.load(open(SH + r"\path_level.json"))["path"])
blds = json.load(open(SH + r"\buildings_final2.json"))
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
w = (L[:, 2] > 0.35) & (L[:, 2] < 9.5)
L = L[w]; C = C[w].astype(int)
lo = Pp[:, 1:3].min(0) - 45; hi = Pp[:, 1:3].max(0) + 45
w = (L[:, 0] > lo[0]) & (L[:, 0] < hi[0]) & (L[:, 1] > lo[1]) & (L[:, 1] < hi[1]); L = L[w]; C = C[w]
# nearest station: distance and lateral
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(Pp)):
    d2 = (L[:, 0] - Pp[i, 1]) ** 2 + (L[:, 1] - Pp[i, 2]) ** 2
    mm = d2 < best; best[mm] = d2[mm]; idx[mm] = i
dist = np.sqrt(best); lat = (L[:, 0] - Pp[idx, 1]) * nr[idx, 0] + (L[:, 1] - Pp[idx, 2]) * nr[idx, 1]
keep = (dist < 38) & ~((lat > -3) & (lat < 17.5) & (L[:, 2] > 2.8))        # not the viaduct body
veg = (C[:, 1] > C[:, 0] + 12) & (C[:, 1] > C[:, 2] + 6)
keep &= ~veg
# not inside buildings
for b in blds:
    ca, sa = math.cos(b["ang"]), math.sin(b["ang"]); dx, dy = L[:, 0] - b["cx"], L[:, 1] - b["cy"]
    lx = dx * ca + dy * sa; ly = -dx * sa + dy * ca
    keep &= ~((np.abs(lx) < b["w"] / 2 + 1.5) & (np.abs(ly) < b["d"] / 2 + 1.5))
L = L[keep]; C = C[keep]
print("points considered", len(L))
CELL = 0.4
x0, y0 = lo; W = int((hi[0] - x0) / CELL) + 1; H = int((hi[1] - y0) / CELL) + 1
ix = ((L[:, 0] - x0) / CELL).astype(int); iy = ((L[:, 1] - y0) / CELL).astype(int)
cnt = np.zeros((H, W), np.int32); np.add.at(cnt, (iy, ix), 1)
zmin = np.full((H, W), 99, np.float32); zmax = np.full((H, W), -99, np.float32)
np.minimum.at(zmin, (iy, ix), L[:, 2]); np.maximum.at(zmax, (iy, ix), L[:, 2])
def boxsum(a, r):
    c = np.pad(a.astype(np.float64), ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1); n = 2 * r + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n])
nb = boxsum(cnt, 3)
cand = (cnt >= 4) & ((zmax - zmin) >= 1.5) & (zmin < 2.2) & (nb <= 3.2 * cnt + 6)
ys, xs = np.nonzero(cand)
print("candidate cells", len(ys))
seen = {}
for y, x in zip(ys.tolist(), xs.tolist()): seen[(y, x)] = -1
poles = []; k = 0
for (y, x) in list(seen.keys()):
    if seen[(y, x)] >= 0: continue
    st = [(y, x)]; seen[(y, x)] = k; mem = [(y, x)]
    while st:
        cy, cx = st.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = (cy + dy, cx + dx)
                if q in seen and seen[q] < 0: seen[q] = k; st.append(q); mem.append(q)
    k += 1
    if len(mem) > 9: continue                                   # too wide to be a pole
    sel = np.zeros(len(L), bool)
    for (cy, cx) in mem: sel |= (iy == cy) & (ix == cx)
    pts = L[sel]; cols = C[sel]
    cxy = pts[:, :2].mean(0); z0, z1 = float(pts[:, 2].min()), float(pts[:, 2].max())
    # head: points near the top within 1.5 units horizontally
    hm = ((L[:, 0] - cxy[0]) ** 2 + (L[:, 1] - cxy[1]) ** 2 < 1.5 ** 2) & (L[:, 2] > z1 - 1.3)
    hc = C[hm]
    blue = float(((hc[:, 2] > hc[:, 0] + 25) & (hc[:, 2] > hc[:, 1] + 5)).mean()) if len(hc) else 0
    red = float(((hc[:, 0] > hc[:, 1] + 55) & (hc[:, 0] > hc[:, 2] + 55)).mean()) if len(hc) else 0
    sat = float(((hc.max(1) - hc.min(1)) > 110).mean()) if len(hc) else 0
    poles.append(dict(x=float(cxy[0]), y=float(cxy[1]), z0=z0, z1=z1, n=int(sel.sum()), blue=blue, red=red, sat=sat, nh=int(hm.sum())))
print("poles", len(poles))
poles.sort(key=lambda p: -(p["z1"] - p["z0"]) * min(p["n"], 60))
for p in poles[:40]:
    print(f"  ({p['x']:7.1f},{p['y']:7.1f}) z {p['z0']:.1f}-{p['z1']:.1f} n={p['n']:4d} blue={p['blue']:.2f} red={p['red']:.2f} sat={p['sat']:.2f}")
json.dump(poles, open(SH + r"\poles.json", "w"))

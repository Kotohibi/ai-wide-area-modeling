# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
r"""Find thin dark vertical poles (traffic-signal / sign posts) in the dense 3DGS, which the sparse SfM cloud misses.

usage: python dark_poles.py <scratch_dir> <s0> <s1> <lat0> <lat1> [max_lum=0.33]
Streams model_sh0.ply, transforms to the leveled frame (same chain as ortho_photo.py), keeps small opaque dark
splats in 0.5 < z < 4.5 inside the route window, bins them on a 0.25-unit grid and keeps columns whose points
span >= 1.8 units in height with a small footprint. Appends new poles (not within 1.0 of an existing one) to
<scratch_dir>/pole_index.json with "src": "3dgs" so sign_views.py / overlay_poles.py / make_furniture_spec.py see them.
"""
import sys, os, json, numpy as np
SP = sys.argv[1]; S0, S1, LAT0, LAT1 = [float(v) for v in sys.argv[2:6]]; MAXL = float(sys.argv[6]) if len(sys.argv) > 6 else 0.33
SMAX = float(sys.argv[7]) if len(sys.argv) > 7 else 0.3; SPAN = float(sys.argv[8]) if len(sys.argv) > 8 else 1.4
SH = os.environ.get("BLENDER_SHARED", "")
N = 15000000
off = open(SP + r"\model_sh0.ply", "rb").read(3000).find(b"end_header") + 11
a = np.memmap(SP + r"\model_sh0.ply", dtype=np.float32, mode="r", offset=off, shape=(N, 17))
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"], np.float32); c0 = lv["c"]
P = np.array(lv["path"]); u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(S0 - 5, S1 + 5, 0.25); U = (ss - 266.0) / 180.0
px, py = np.polyval(cx, U), np.polyval(cy, U); dx, dy = np.polyval(np.polyder(cx), U), np.polyval(np.polyder(cy), U); nn = np.hypot(dx, dy)
xlo, xhi = px.min() + min(LAT0, -LAT1) - 5, px.max() + max(LAT1, -LAT0) + 5
ylo, yhi = py.min() - max(abs(LAT0), abs(LAT1)) - 5, py.max() + max(abs(LAT0), abs(LAT1)) + 5
M3 = (Rt @ Rm).astype(np.float32)
pts = []
for i in range(0, N, 1000000):
    blk = np.asarray(a[i:i + 1000000])
    q = ((blk[:, 0:3] - cam0) @ Rm.T + np.array([0, 0, h0]) - np.array([0, 0, c0])) @ Rt.T
    op = 1 / (1 + np.exp(-blk[:, 9])); smax = np.exp(blk[:, 10:13]).max(1)
    col = np.clip(0.5 + 0.28209479 * blk[:, 6:9], 0, 1); lum = col.mean(1)
    m = (q[:, 0] > xlo) & (q[:, 0] < xhi) & (q[:, 1] > ylo) & (q[:, 1] < yhi) & (q[:, 2] > 0.5) & (q[:, 2] < 4.5) & (op > 0.3) & (smax < SMAX) & (lum < MAXL)
    if m.any(): pts.append(q[m])
Q = np.concatenate(pts); print("dark thin splats in window", len(Q))
best = np.full(len(Q), 1e9); idx = np.zeros(len(Q), int)
for k in range(len(ss)):
    d2 = (Q[:, 0] - px[k]) ** 2 + (Q[:, 1] - py[k]) ** 2; mm = d2 < best; best[mm] = d2[mm]; idx[mm] = k
lat = (Q[:, 0] - px[idx]) * (dy[idx] / nn[idx]) - (Q[:, 1] - py[idx]) * (dx[idx] / nn[idx])
sv = ss[idx]
ok = (sv >= S0) & (sv <= S1) & (lat >= LAT0) & (lat <= LAT1); Q = Q[ok]; sv = sv[ok]; lat = lat[ok]
C = 0.35; ix = np.floor(Q[:, 0] / C).astype(int); iy = np.floor(Q[:, 1] / C).astype(int)
keys = ix * 100000 + iy; uk, inv, cnt = np.unique(keys, return_inverse=True, return_counts=True)
print("cells", len(uk), "cells with >=6 pts", int((cnt >= 6).sum()))
cand = []
order = np.argsort(inv); bounds = np.r_[0, np.cumsum(cnt)]
for k in range(len(uk)):
    if cnt[k] < 6: continue
    sel = order[bounds[k]:bounds[k + 1]]; z = Q[sel, 2]
    if np.ptp(z) < SPAN: continue
    hist, _ = np.histogram(z, bins=np.arange(z.min(), z.max() + 0.3, 0.3))
    if (hist > 0).mean() < 0.5: continue                         # continuous column, not two blobs
    if z.min() > 1.3: continue                                   # must reach the ground (else: deck / girder underside)
    m = sel
    cand.append(dict(x=float(Q[m, 0].mean()), y=float(Q[m, 1].mean()), z0=float(z.min()), z1=float(z.max()), n=int(len(m)),
                     s=float(sv[m].mean()), lat=float(lat[m].mean())))
cand.sort(key=lambda c: -c["n"]); merged = []
for c in cand:
    if all((c["x"] - o["x"]) ** 2 + (c["y"] - o["y"]) ** 2 > 0.8 ** 2 for o in merged): merged.append(c)
idxf = SP + r"\pole_index.json"; index = json.load(open(idxf)); nid = max(p["id"] for p in index) + 1; added = []
for c in merged:
    if all((c["x"] - p["x"]) ** 2 + (c["y"] - p["y"]) ** 2 > 1.0 ** 2 for p in index):
        c.update(id=nid, src="3dgs"); index.append(c); added.append(c); nid += 1
json.dump(index, open(idxf, "w"))
print("dark pole columns", len(merged), "new poles added", len(added))
for c in added: print(f"  #{c['id']} s={c['s']:.1f} lat={c['lat']:.1f} z {c['z0']:.1f}-{c['z1']:.1f} n={c['n']}")

# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, numpy as np
SP = sys.argv[1]
# --- trajectory (front cams) in raw -> site frame
rows = [l.strip().split(",") for l in open(SP + r"\cams.csv", encoding="utf-8-sig") if l.strip()]
front = [(int(r[0]), [float(r[1]), float(r[2]), float(r[3])]) for r in rows if r[4].endswith("_front.png")]
T = np.array([p for _, p in front])
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]])
h0 = float((cam0 - cen) @ b[6:9])
Ts = (T - cam0) @ Rm.T; Ts[:, 2] += h0
# arclength param and smoothing
d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Ts[:, :2], axis=0), axis=1))]
k = 9
sm = np.stack([np.convolve(np.pad(Ts[:, i], (k, k), mode="edge"), np.ones(2*k+1)/(2*k+1), "valid") for i in range(3)], 1)
np.save(SP + r"\traj_site.npy", np.c_[sm, d])
P = np.load(SP + r"\fP.npy")
print("traj len", d[-1], "n", len(sm), "start", sm[0], "end", sm[-1])
# stations every 6 units of arclength
step = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
lo, hi = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (0, d[-1])
out = []
for s in np.arange(lo, hi, step):
    i = np.searchsorted(d, s)
    if i < 2 or i >= len(sm) - 2: continue
    t = sm[i + 2, :2] - sm[i - 2, :2]; t /= np.linalg.norm(t)
    nrm = np.array([t[1], -t[0]])                     # right of travel
    rel = P[:, :2] - sm[i, :2]
    al = rel @ t; lat = rel @ nrm
    hr = P[:, 2] - (sm[i, 2] - h0)                    # height above local road
    m = (np.abs(al) < 3) & (np.abs(lat) < 30) & (hr > 3.0) & (hr < 14)
    if m.sum() < 60: continue
    L = lat[m]; H = hr[m]
    # dominant underside: histogram of H, first strong peak above 3
    hh, e = np.histogram(H, bins=np.arange(3, 14.01, 0.25))
    pk = e[np.argmax(hh)]
    out.append((s, sm[i, 0], sm[i, 1], float(np.percentile(L, 5)), float(np.percentile(L, 95)), float(pk), int(m.sum())))
print(" s     x       y     lat5   lat95  underside(h)  n")
for o in out: print(f"{o[0]:6.1f} {o[1]:7.1f} {o[2]:7.1f} {o[3]:6.1f} {o[4]:6.1f} {o[5]:6.2f} {o[6]:6d}")

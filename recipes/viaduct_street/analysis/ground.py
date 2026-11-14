# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, numpy as np
SP = sys.argv[1]
M = np.array([[0.965509831905365, 0.26036858558654785, 0], [0.26036858558654785, -0.965509831905365, 0], [0, 0, -1]], np.float32)
pw = np.load(SP + r"\near_p.npy"); c = np.load(SP + r"\near_c.npy")
p = pw @ M.T          # back to raw (M is its own inverse)
cam = np.array([9.8478, 1.5723, -40.3020])   # dataset camera 1177 (raw)
d = np.linalg.norm(p - cam, axis=1)
below = p[(d < 25) & (p[:, 1] > cam[1] + 0.3) & (p[:, 1] < cam[1] + 6)]
print("candidate ground pts", len(below))
rng = np.random.default_rng(2)
best = None
for _ in range(4000):
    t = below[rng.choice(len(below), 3, replace=False)]
    n = np.cross(t[1] - t[0], t[2] - t[0]); nn = np.linalg.norm(n)
    if nn < 1e-9: continue
    n /= nn
    if abs(n[1]) < 0.9: continue
    cnt = (np.abs((below - t[0]) @ n) < 0.08).sum()
    if best is None or cnt > best[0]: best = (cnt, n.copy(), t[0].copy())
cnt, n, p0 = best
if n[1] < 0: n = -n            # n points to raw +y (down in the real world)
# refine by least squares on inliers
inl = below[np.abs((below - p0) @ n) < 0.08]
cen = inl.mean(0); u, s, vt = np.linalg.svd(inl - cen); n = vt[2] if vt[2][1] > 0 else -vt[2]
print("ground inliers", len(inl), "normal(down)", n, "centroid", cen)
h = (cen - cam) @ n
print("camera height above ground (units):", h)
np.save(SP + r"\ground.npy", np.concatenate([n, cen, cam]))
# heights of everything within the footprint, relative to ground (up positive)
q = p[d < 40]
hh = -((q - cen) @ n)
for lo in np.arange(-0.5, 14, 0.5):
    m = (hh >= lo) & (hh < lo + 0.5)
    print(f"h {lo:5.1f}  n={int(m.sum()):7d}")

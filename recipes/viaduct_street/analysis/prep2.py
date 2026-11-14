# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, numpy as np
SP = sys.argv[1]
N = 15000000
off = open(SP + r"\model_sh0.ply", "rb").read(3000).find(b"end_header") + 11
a = np.memmap(SP + r"\model_sh0.ply", dtype=np.float32, mode="r", offset=off, shape=(N, 17))
cam = np.array([9.87, 0.62, 40.47], np.float32)
M = np.array([[0.965509831905365, 0.26036858558654785, 0.0],
              [0.26036858558654785, -0.965509831905365, 0.0],
              [0.0, 0.0, -1.0]], np.float32)
out_p, out_c, out_s = [], [], []
B = 1000000
for i in range(0, N, B):
    blk = np.asarray(a[i:i+B]).copy()
    blk[:, 0:3] = blk[:, 0:3] @ M.T
    op = 1 / (1 + np.exp(-blk[:, 9]))
    sc = np.exp(blk[:, 10:13]).max(1)
    d = np.linalg.norm(blk[:, 0:3] - cam, axis=1)
    m = (op > 0.4) & (sc < 0.6) & (d < 120)
    out_p.append(blk[m, 0:3]); out_s.append(sc[m])
    out_c.append((np.clip(0.5 + 0.28209479 * blk[m, 6:9], 0, 1) * 255).astype(np.uint8))
p = np.concatenate(out_p); c = np.concatenate(out_c); s = np.concatenate(out_s)
print("points near camera", len(p))
np.save(SP + r"\near_p.npy", p); np.save(SP + r"\near_c.npy", c); np.save(SP + r"\near_s.npy", s)

# RANSAC ground plane using points below the camera, within 40 units
rng = np.random.default_rng(1)
q = p[(np.linalg.norm(p - cam, axis=1) < 40) & (p[:, 1] < cam[1] - 0.3)]
best = None
for _ in range(3000):
    t = q[rng.choice(len(q), 3, replace=False)]
    n = np.cross(t[1] - t[0], t[2] - t[0]); nn = np.linalg.norm(n)
    if nn < 1e-9: continue
    n /= nn
    if abs(n[1]) < 0.7: continue          # roughly horizontal only
    dist = np.abs((q - t[0]) @ n)
    cnt = (dist < 0.15).sum()
    if best is None or cnt > best[0]:
        best = (cnt, n.copy(), t[0].copy())
cnt, n, p0 = best
if n[1] < 0: n = -n
print("plane inliers", cnt, "of", len(q), "normal", n, "point", p0)
print("camera height above plane (units):", (cam - p0) @ n)
np.save(SP + r"\plane.npy", np.concatenate([n, p0]))

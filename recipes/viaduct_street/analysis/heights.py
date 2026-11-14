import sys, json, numpy as np
SP = sys.argv[1]
import os; SHARED = os.environ.get("BLENDER_SHARED", "")
L = np.load(SP + r"\lP.npy"); Pp = np.array(json.load(open(SHARED + r"\path_level.json"))["path"])
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
w = (L[:, 2] > 0.5) & (L[:, 2] < 14); L = L[w]
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(Pp)):
    d2 = (L[:, 0] - Pp[i, 1]) ** 2 + (L[:, 1] - Pp[i, 2]) ** 2
    m = d2 < best; best[m] = d2[m]; idx[m] = i
lat = (L[:, 0] - Pp[idx, 1]) * nr[idx, 0] + (L[:, 1] - Pp[idx, 2]) * nr[idx, 1]
al = (L[:, 0] - Pp[idx, 1]) * t[idx, 0] + (L[:, 1] - Pp[idx, 2]) * t[idx, 1]
sv = Pp[idx, 0] - al
for (s0, s1) in [(100, 130), (130, 165), (165, 200), (200, 235), (240, 270), (275, 305), (315, 345), (355, 385), (400, 430)]:
    m = (sv > s0) & (sv < s1) & (lat > 0) & (lat < 14) & (best < 400)
    z = L[m, 2]
    h, e = np.histogram(z, bins=np.arange(0.5, 14.01, 0.5))
    top = np.argsort(-h)[:4]
    print(f"s {s0}-{s1} n={m.sum():6d}  densest z' bins:", sorted(round(float(e[k] + 0.25), 2) for k in top),
          " p5/p50:", round(float(np.percentile(z, 5)), 2) if len(z) else None, round(float(np.percentile(z, 50)), 2) if len(z) else None)

import sys, numpy as np
SP = sys.argv[1]
dt = np.dtype([("p", "<f8", 3), ("n", "<f8", 3), ("c", "u1", 3)])
raw = open(__import__("os").path.join(__import__("os").environ.get("SFM_DIR", "."), "points3D.ply"), "rb").read()
off = raw.find(b"end_header") + 11
a = np.frombuffer(raw, dtype=dt, offset=off)
print("sparse points", len(a), "raw bounds", a["p"].min(0), a["p"].max(0))
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam = g[6:9]
b = np.load(SP + r"\basis.npy"); right, fwd, up = b[0:3], b[3:6], b[6:9]
Rm = np.stack([right, fwd, up])
h0 = float((cam - cen) @ up)
q = (a["p"] - cam) @ Rm.T; q[:, 2] += h0
nrm = a["n"] @ Rm.T
d = np.linalg.norm(q[:, :2], axis=1)
print("points within 20 horizontally of camera:", int((d < 20).sum()))
print("their h pct", np.percentile(q[d < 20, 2], [1, 5, 25, 50, 75, 95, 99]))
np.save(SP + r"\fP.npy", q.astype(np.float32)); np.save(SP + r"\fC.npy", a["c"])
m = (np.abs(q[:, 0]) < 90) & (q[:, 1] > -50) & (q[:, 1] < 140) & (q[:, 2] > -2) & (q[:, 2] < 25)
np.save(SP + r"\pP.npy", q[m].astype(np.float32)); np.save(SP + r"\pC.npy", a["c"][m])
np.save(SP + r"\pN.npy", nrm[m].astype(np.float32)); np.save(SP + r"\pO.npy", np.ones(m.sum(), np.float32))
print("kept in site box", int(m.sum()))

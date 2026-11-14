import sys, json, numpy as np
SP = sys.argv[1]
import os; SHARED = os.environ.get("BLENDER_SHARED", "")
S = 1.15
pj = json.load(open(SP + r"\viaduct_path.json"))["path"]
P = np.array(pj); s_, x_, y_, g_ = P.T
# --- plane z = a x + b y + c through the route's road level
A = np.c_[x_, y_, np.ones_like(x_)]
(a, b, c), *_ = np.linalg.lstsq(A, g_, rcond=None)
n = np.array([-a, -b, 1.0]); n /= np.linalg.norm(n)
ax = np.cross(n, [0, 0, 1.0]); sn = np.linalg.norm(ax); cs = n[2]
K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]]) / sn
Rt = np.eye(3) + K * sn + K @ K * (1 - cs)           # Rodrigues: rotates n onto +z
print("plane a,b,c", a, b, c, "tilt deg", np.degrees(np.arccos(cs)))
def level(p): return (np.asarray(p) - np.array([0, 0, c])) @ Rt.T
Pl = level(np.c_[x_, y_, g_])
print("leveled ground residual (units): min/max", Pl[:, 2].min(), Pl[:, 2].max())
json.dump({"path": [[float(s_[i]), float(Pl[i, 0]), float(Pl[i, 1]), float(Pl[i, 2])] for i in range(len(s_))],
           "Rt": Rt.tolist(), "c": float(c)}, open(SHARED + r"\path_level.json", "w"))
# --- poses
poses = json.load(open(SP + r"\poses.json"))
for o in poses:
    loc = level(np.array(o["loc"]) / S) * S
    o["loc"] = loc.tolist(); o["rot"] = (Rt @ np.array(o["rot"])).tolist()
json.dump(poses, open(SHARED + r"\poses_level.json", "w"))
# --- points
F = np.load(SP + r"\fP.npy"); C = np.load(SP + r"\fC.npy")
Fl = level(F).astype(np.float32)
np.save(SP + r"\lP.npy", Fl); np.save(SP + r"\lC.npy", C)
print("leveled points", len(Fl))

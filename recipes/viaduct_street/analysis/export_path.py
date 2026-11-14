# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, json, numpy as np
SP = sys.argv[1]
tr = np.load(SP + r"\traj_site.npy"); d = tr[:, 3]
h0 = 1.0815199170913725
k = 6                                   # extra smoothing for the sweep path
sm = np.stack([np.convolve(np.pad(tr[:, i], (k, k), mode="edge"), np.ones(2*k+1)/(2*k+1), "valid") for i in range(3)], 1)
ss = np.arange(88, 448, 3.0)
pts = [[float(s), float(np.interp(s, d, sm[:, 0])), float(np.interp(s, d, sm[:, 1])), float(np.interp(s, d, sm[:, 2]) - h0)] for s in ss]
# arclength of the origin camera (dataset index of uid 1177 -> front frame 196)
json.dump({"path": pts, "s_origin": float(d[196]), "h0": h0}, open(SP + r"\viaduct_path.json", "w"))
print(len(pts), "stations; s_origin", d[196])
print("ground h range", min(p[3] for p in pts), max(p[3] for p in pts))

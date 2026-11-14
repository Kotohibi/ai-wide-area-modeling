# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, numpy as np
SP = sys.argv[1]
rows = [l.strip().split(",") for l in open(SP + r"\cams.csv", encoding="utf-8-sig") if l.strip()]
uid = np.array([int(r[0]) for r in rows]); P = np.array([[float(r[1]), float(r[2]), float(r[3])] for r in rows])
names = [r[4] for r in rows]
front = np.array([n.endswith("_front.png") for n in names])
T = P[front]
print("n positions", len(T), "bounds", T.min(0), T.max(0))
M = np.array([[0.965509831905365, 0.26036858558654785, 0], [0.26036858558654785, -0.965509831905365, 0], [0, 0, -1]])
eye_w = np.array([9.874671936035156, 0.6242412328720093, 40.473976135253906])
eye_r = M @ eye_w
for label, e in (("eye as-is(raw)", eye_w), ("eye M@world", eye_r)):
    d = np.linalg.norm(T - e, axis=1)
    print(label, e, "nearest cam dist", d.min(), "uid", uid[front][d.argmin()], T[d.argmin()])
# trajectory plane fit (SVD): smallest-variance direction
c = T.mean(0)
u, s, vt = np.linalg.svd(T - c, full_matrices=False)
print("traj centroid", c, "sing", s, "plane normal(last)", vt[2])
# spacing between consecutive frames
step = np.linalg.norm(np.diff(T, axis=0), axis=1)
print("median step", np.median(step), "total length", step.sum())

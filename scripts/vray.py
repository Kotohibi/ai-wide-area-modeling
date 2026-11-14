"""Triangulate model-frame points from pixels picked in a view set (LFS viewport captures or photos with fov_v).
usage: python vray.py <project_dir> <set> "<idx>:<u>:<v>:<label>[:z=<h>]" ...
  2+ picks of a label -> closest point of the rays; 1 pick with z=h -> intersection with plane z=h.
Pixels are full-resolution pixels of the capture (views/<set>/lfs_LFS_view_XX.png)."""
import sys, os, json, numpy as np
d, s = sys.argv[1], sys.argv[2]
cams = json.load(open(os.path.join(d, "views", s + ".json"), encoding="utf-8"))
def ray(i, u, v):
    c = cams[i]; R = np.array(c["rot"]); w, h = c["w"], c["h"]
    f = (h / 2) / np.tan(np.radians(c["fov_v_deg"]) / 2)
    dc = np.array([(u - w / 2) / f, -(v - h / 2) / f, -1.0]); dw = R @ dc
    return np.array(c["loc"], float), dw / np.linalg.norm(dw)
G = {}
for a in sys.argv[3:]:
    f = a.split(":"); z = None
    if f[-1].startswith("z="): z = float(f.pop()[2:])
    G.setdefault(f[3], []).append((int(f[0]), float(f[1]), float(f[2]), z))
out = {}
for lab, picks in G.items():
    rays = [ray(i, u, v) for i, u, v, _ in picks]
    if len(rays) >= 2:
        A = np.zeros((3, 3)); b = np.zeros(3)
        for C, dd in rays:
            M = np.eye(3) - np.outer(dd, dd); A += M; b += M @ C
        X = np.linalg.solve(A, b)
        miss = max(np.linalg.norm((np.eye(3) - np.outer(dd, dd)) @ (X - C)) for C, dd in rays)
        ang = max(np.degrees(np.arccos(np.clip(abs(r1[1] @ r2[1]), -1, 1))) for r1 in rays for r2 in rays)
        print("%-12s %s  miss %.2f m  angle %.1f deg" % (lab, np.round(X, 2).tolist(), miss, ang))
    else:
        C, dd = rays[0]; h = picks[0][3] or 0.0; t = (h - C[2]) / dd[2]; X = C + t * dd
        print("%-12s %s  (plane z=%.2f)" % (lab, np.round(X, 2).tolist(), h))
    out[lab] = X.tolist()
p = os.path.join(d, "vpicks.json"); old = json.load(open(p)) if os.path.exists(p) else {}
old.update(out); json.dump(old, open(p, "w"), indent=1)

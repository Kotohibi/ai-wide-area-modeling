r"""3D positions (model frame, metres) from pixels picked in training photos - for things the point clouds miss
(thin posts, wires, glass, edges of smooth surfaces) and for measuring known dimensions to fix the scale.

usage: python pick3d.py <project.json> "<image>:<u>:<v>:<label>[:z=<h>]" ...
  (u, v) are full-resolution pixels of the photo (open it from images_dir; find_views / views.py find helps).
  - A label picked in 2+ photos is TRIANGULATED (closest point of the rays). Use photos from clearly different
    positions; the reported ray miss distance says how well they agree.
  - A label picked once is intersected with the horizontal plane z = h (default 0 = ground of the model frame),
    e.g. the foot of a post.
  - Distances between all labels are printed: pick both ends of something of known size (door 2.0 m high,
    lane 3.5 m wide, ...) and rescale with  setup_project.py <dir> --rescale <new m_per_unit> "<reason>"
    (new = old * known_m / measured_m).
Results also go to <project_dir>\picks.json (label -> xyz).
"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project

P = Project(sys.argv[1]); groups = {}
for a in sys.argv[2:]:
    f = a.split(":")
    # image names can contain ':' only on non-Windows systems; take the last fields as numbers
    z = None
    if f[-1].startswith("z="): z = float(f.pop()[2:])
    name, u, v, lab = ":".join(f[:-3]), float(f[-3]), float(f[-2]), f[-1]
    C, d = P.pixel_ray_model(name, u, v); groups.setdefault(lab, []).append((name, C, d, z))
res = {}
for lab, rays in groups.items():
    if len(rays) >= 2:
        A = np.zeros((3, 3)); b = np.zeros(3)
        for _, C, d, _ in rays:
            K = np.eye(3) - np.outer(d, d); A += K; b += K @ C
        X = np.linalg.solve(A, b)
        miss = [np.linalg.norm((np.eye(3) - np.outer(d, d)) @ (X - C)) for _, C, d, _ in rays]
        ang = max(np.degrees(np.arccos(np.clip(abs(r1[2] @ r2[2]), 0, 1))) for r1 in rays for r2 in rays)
        base = max(np.linalg.norm(r1[1] - r2[1]) for r1 in rays for r2 in rays)
        warn = "  (NO DEPTH: photos taken from the same spot, e.g. views of one 360 rig frame)" if base < 0.3 else \
               "  (WEAK: rays nearly parallel)" if ang < 5 else \
               "  (INCONSISTENT: the picks are probably not the same physical point)" if max(miss) > 0.5 else ""
        print("%-12s triangulated from %d photos: x=%.2f y=%.2f z=%.2f m   ray miss max %.2f m, baseline %.1f m, max ray angle %.0f deg%s"
              % (lab, len(rays), *X, max(miss), base, ang, warn))
    else:
        name, C, d, z = rays[0]; h = 0.0 if z is None else z
        if abs(d[2]) < 1e-6 or (h - C[2]) / d[2] <= 0: print(lab, ": ray does not hit z =", h); continue
        X = C + d * (h - C[2]) / d[2]
        print("%-12s on plane z=%.2f from %s: x=%.2f y=%.2f z=%.2f m (range %.1f m)" % (lab, h, name[-30:], *X, np.linalg.norm(X - C)))
    res[lab] = X.tolist()
labs = list(res)
for i in range(len(labs)):
    for j in range(i + 1, len(labs)):
        print("  |%s - %s| = %.3f m  (%.3f units)" % (labs[i], labs[j], np.linalg.norm(np.subtract(res[labs[i]], res[labs[j]])),
                                                       np.linalg.norm(np.subtract(res[labs[i]], res[labs[j]])) / P.S))
pp = os.path.join(P.dir, "picks.json"); old = json.load(open(pp)) if os.path.exists(pp) else {}
old.update(res); json.dump(old, open(pp, "w"), indent=1)

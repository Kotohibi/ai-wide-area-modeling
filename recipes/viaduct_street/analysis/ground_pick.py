# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
r"""Locate objects the point clouds miss (thin signal posts, sign posts) from pixels picked in training photos.

usage: python ground_pick.py <scratch_dir> "<image>:<u>:<v>[:<label>]" ...
(u, v) = full-resolution pixel (1920x1920) where the object touches the ground. The ray from the COLMAP camera is
intersected with the leveled road plane z = 0 and reported as leveled (x, y) and route (s, lat). Pick the same post in
two or three photos from different positions: if the results agree within ~0.5 unit the position is reliable.
Also: "<image>:<u>:<v>:<label>:h=<z>" intersects with the horizontal plane z instead (e.g. a sign plate centre seen
from below when the base is hidden; less reliable).
"""
import sys, os, json, numpy as np
SP = sys.argv[1]; SH = os.environ.get("BLENDER_SHARED", ""); SFM = os.environ.get("SFM_DIR", ".")
picks = [a.split(":") for a in sys.argv[2:]]
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"]); c0 = lv["c"]
P = np.array(lv["path"]); u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(40, 480, 0.1); U = (ss - 266.0) / 180.0
px, py = np.polyval(cx, U), np.polyval(cy, U); dx, dy = np.polyval(np.polyder(cx), U), np.polyval(np.polyder(cy), U); nn = np.hypot(dx, dy)
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
want = {p[0] for p in picks}; poses = {}
lines = [l for l in open(SFM + r"\images.txt", encoding="utf-8") if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    t = lines[i].split()
    if len(t) >= 10 and t[9] in want:
        R = qmat(np.array([float(v) for v in t[1:5]])); C = -R.T @ np.array([float(v) for v in t[5:8]])
        poses[t[9]] = ((Rm @ (C - cam0) + np.array([0, 0, h0]) - np.array([0, 0, c0])) @ Rt.T, (Rt @ Rm) @ R.T)
out = []
for p in picks:
    name, uu, vv = p[0], float(p[1]), float(p[2]); lab = p[3] if len(p) > 3 else ""
    hz = float(p[4][2:]) if len(p) > 4 and p[4].startswith("h=") else 0.0
    C, A = poses[name]
    ray = A @ np.array([(uu - 960) / 960, (vv - 960) / 960, 1.0])          # leveled-frame ray direction
    if abs(ray[2]) < 1e-6 or (hz - C[2]) / ray[2] <= 0: print(name, "ray does not hit the plane"); continue
    X = C + ray * (hz - C[2]) / ray[2]
    i = int(np.argmin((px - X[0]) ** 2 + (py - X[1]) ** 2))
    lat = (X[0] - px[i]) * dy[i] / nn[i] - (X[1] - py[i]) * dx[i] / nn[i]
    j = int(np.argmin((px - C[0]) ** 2 + (py - C[1]) ** 2))
    clat = (C[0] - px[j]) * dy[j] / nn[j] - (C[1] - py[j]) * dx[j] / nn[j]
    # bearing (route frame: 0 = +s, 90 = +lat) from the object to this camera: a sign / signal face seen frontally
    # in this photo faces roughly this bearing -> use it as "face" in street_furniture review
    bear = float(np.degrees(np.arctan2(clat - lat, ss[j] - ss[i])))
    out.append(dict(label=lab, image=name, x=float(X[0]), y=float(X[1]), s=float(ss[i]), lat=float(lat), dist=float(np.linalg.norm(X - C)),
                    cam_s=float(ss[j]), cam_lat=float(clat), bearing_to_cam=bear))
    print(f"{lab:10s} {name[-22:]:22s} -> x={X[0]:7.2f} y={X[1]:7.2f}  s={ss[i]:6.1f} lat={lat:6.2f}  (dist {np.linalg.norm(X - C):.1f})"
          f"  camera s={ss[j]:.1f} lat={clat:.2f}  bearing obj->cam {bear:.0f}")
json.dump(out, open(SP + r"\ground_picks.json", "w"), indent=1)

import sys, json, numpy as np
SP = sys.argv[1]
views = sys.argv[2].split(",")                      # e.g. right,front
stations = [float(v) for v in sys.argv[3].split(",")]
S = 1.15
# COLMAP images.txt -> pose per image name
poses = {}
with open(__import__("os").path.join(__import__("os").environ.get("SFM_DIR", "."), "images.txt"), encoding="utf-8") as f:
    lines = [l for l in f if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    t = lines[i].split()
    if len(t) < 10: continue
    q = np.array([float(v) for v in t[1:5]]); tv = np.array([float(v) for v in t[5:8]]); poses[t[9]] = (q, tv)
print("poses", len(poses))
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
rows = [l.strip().split(",") for l in open(SP + r"\cams.csv", encoding="utf-8-sig") if l.strip()]
front = [r[4] for r in rows if r[4].endswith("_front.png")]
d = np.load(SP + r"\traj_site.npy")[:, 3]
out = []
for s in stations:
    i = min(int(np.searchsorted(d, s)), len(front) - 1)
    for v in views:
        name = front[i].replace("_front.png", f"_{v}.png")
        if name not in poses: print("missing", name); continue
        q, tv = poses[name]; R = qmat(q)
        C = -R.T @ tv                                   # camera centre (raw)
        axes = R.T                                      # columns: cam x(right), y(down), z(fwd) in raw
        site_c = Rm @ (C - cam0); site_c[2] += h0
        cx, cy, cz = Rm @ axes[:, 0], Rm @ axes[:, 1], Rm @ axes[:, 2]
        # Blender camera: x right, y up, looks along -z
        M3 = np.stack([cx, -cy, -cz], 1)
        out.append(dict(name=name, s=s, view=v, loc=[float(v_) * S for v_ in site_c], rot=M3.tolist()))
json.dump(out, open(SP + r"\poses.json", "w"))
for o in out: print(o["name"], [round(x, 1) for x in o["loc"]])

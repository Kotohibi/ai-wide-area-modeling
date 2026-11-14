# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Project the training photos onto a horizontal plane using the COLMAP poses (images.txt).

usage: python ortho_photo.py <scratch_dir> <frame_step> <res> <max_dist> [plane_z=0] [views=front,back,left,right,bottom] [name=ortho_photo]
  plane_z = 0      -> road-surface orthophoto (default)
  plane_z = 4.3, views=top, name=underside -> the viaduct seen from below: sky (blue) vs deck tells the deck outline,
                     twin-deck gaps and pier caps far better than the sparse cloud does.
SfM folder: env SFM_DIR (required) with images.txt and images\\.
"""
import sys, json, time, zlib, struct, numpy as np
from PIL import Image
SP = sys.argv[1]
import os; SH = os.environ.get("BLENDER_SHARED", "")
SFM = os.environ.get("SFM_DIR", ".")
STEP = int(sys.argv[2]); RES = float(sys.argv[3]); RMAX = float(sys.argv[4])
PLANE_Z = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
VIEWS = tuple(sys.argv[6].split(",")) if len(sys.argv) > 6 else ("front", "back", "left", "right", "bottom")
NAME = sys.argv[7] if len(sys.argv) > 7 else "ortho_photo"
def save_png(path, a):
    h, w, c = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        cc = struct.pack(">I", len(d)) + t + d
        return cc + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
# ---- frame transform (raw -> site -> leveled)
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"]); c0 = lv["c"]
Pp = np.array(lv["path"])
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
poses = {}
lines = [l for l in open(SFM + r"\images.txt", encoding="utf-8") if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    t = lines[i].split()
    if len(t) < 10: continue
    q = np.array([float(v) for v in t[1:5]]); tv = np.array([float(v) for v in t[5:8]])
    R = qmat(q); C = -R.T @ tv; ax = R.T
    Cl = (Rm @ (C - cam0) + np.array([0, 0, h0]) - np.array([0, 0, c0])) @ Rt.T
    Ax = (Rt @ Rm) @ ax                                  # columns: cam x(right), y(down), z(forward) in leveled frame
    poses[t[9]] = (Cl, Ax)
print("poses", len(poses), flush=True)
# ---- grid
X0, X1, Y0, Y1 = -140.0, 60.0, -275.0, 125.0
W = int((X1 - X0) / RES); H = int((Y1 - Y0) / RES)
acc = np.zeros((H, W, 3), np.float32); wsum = np.zeros((H, W), np.float32)
# region mask: cells within 40 units of the route
gx = X0 + (np.arange(W) + 0.5) * RES; gy = Y1 - (np.arange(H) + 0.5) * RES
mask = np.zeros((H, W), bool)
for p in Pp[::2]:
    ix0 = max(0, int((p[1] - 40 - X0) / RES)); ix1 = min(W, int((p[1] + 40 - X0) / RES)); iy0 = max(0, int((Y1 - (p[2] + 40)) / RES)); iy1 = min(H, int((Y1 - (p[2] - 40)) / RES))
    xx, yy = np.meshgrid(gx[ix0:ix1], gy[iy0:iy1])
    mask[iy0:iy1, ix0:ix1] |= ((xx - p[1]) ** 2 + (yy - p[2]) ** 2) < 40 ** 2
print("mask cells", int(mask.sum()), flush=True)
names = sorted(poses.keys())
frames = sorted(set(n.rsplit("_", 1)[0] for n in names))[::STEP]
t0 = time.time(); used = 0
for fi, fr in enumerate(frames):
    for v in VIEWS:
        nm = fr + "_" + v + ".png"
        if nm not in poses: continue
        Cl, Ax = poses[nm]
        # only frames near the route corridor
        if np.min((Pp[:, 1] - Cl[0]) ** 2 + (Pp[:, 2] - Cl[1]) ** 2) > 45 ** 2: continue
        ix0 = max(0, int((Cl[0] - RMAX - X0) / RES)); ix1 = min(W, int((Cl[0] + RMAX - X0) / RES))
        iy0 = max(0, int((Y1 - (Cl[1] + RMAX)) / RES)); iy1 = min(H, int((Y1 - (Cl[1] - RMAX)) / RES))
        if ix1 <= ix0 or iy1 <= iy0: continue
        xx, yy = np.meshgrid(gx[ix0:ix1], gy[iy0:iy1])
        sub = mask[iy0:iy1, ix0:ix1] & ((xx - Cl[0]) ** 2 + (yy - Cl[1]) ** 2 < RMAX ** 2)
        if not sub.any(): continue
        P3 = np.stack([xx[sub], yy[sub], np.full(sub.sum(), PLANE_Z)], 1) - Cl
        pc = P3 @ Ax                                        # camera coords (x right, y down, z fwd)
        z = pc[:, 2]; ok = z > 0.3
        u = 960 + 960 * pc[:, 0] / np.where(ok, z, 1); vv = 960 + 960 * pc[:, 1] / np.where(ok, z, 1)
        ok &= (u > 4) & (u < 1916) & (vv > 4) & (vv < 1916)
        if not ok.any(): continue
        try: im = np.asarray(Image.open(SFM + r"\images" + "\\" + nm).convert("RGB"))
        except Exception: continue
        col = im[vv[ok].astype(int), u[ok].astype(int)].astype(np.float32)
        d = np.linalg.norm(P3[ok], axis=1); wgt = (abs(Cl[2] - PLANE_Z) / np.maximum(d, 0.5)) ** 2 * (1.0 / (1 + (d / 6.0) ** 2))
        ys, xs = np.nonzero(sub); ys = ys[ok] + iy0; xs = xs[ok] + ix0
        np.add.at(acc, (ys, xs), col * wgt[:, None]); np.add.at(wsum, (ys, xs), wgt)
        used += 1
    if fi % 20 == 0: print(f"frame {fi}/{len(frames)} used {used} t={time.time()-t0:.0f}s", flush=True)
valid = wsum > 1e-3
img = np.zeros((H, W, 3), np.uint8); img[valid] = np.clip(acc[valid] / wsum[valid, None], 0, 255).astype(np.uint8)
img[~valid] = (40, 42, 40)
save_png(SP + "\\" + NAME + ".png", np.ascontiguousarray(img)); save_png(SH + "\\" + NAME + ".png", np.ascontiguousarray(img))
np.save(SP + "\\" + NAME + "_valid.npy", valid)
json.dump({"x0": X0, "x1": X1, "y0": Y0, "y1": Y1, "res": RES, "w": W, "h": H, "plane_z": PLANE_Z}, open(SH + "\\" + NAME + "_meta.json", "w"))
print("done", W, H, "coverage in mask", float(valid[mask].mean()), "images used", used, flush=True)

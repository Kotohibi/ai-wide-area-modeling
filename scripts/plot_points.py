r"""Orthographic images of a model-frame point cloud with a metre grid - for reading positions and dimensions.

usage: python plot_points.py <project.json> <points name> --view top|front|side [--box=x0,y0,z0,x1,y1,z1]
                             [--res 0.05] [--mode density|color|height] [--out file.png] [--cams]
  points name : sfm / gs / ... (points_<name>.npz from export_points.py)
  top   = looking down -Z (x right, y up)      front = looking along +Y (x right, z up)
  side  = looking along -X (y right, z up)
  density : log point count per pixel (structure edges, walls, poles stand out)
  color   : mean point colour       height : highest z per pixel (top view only; floors vs roofs)
  --cams  : draw training camera positions (blue) - the capture path; space there is free
Grid lines every 1 m (thin) and 10 m (labelled). Thin slices (e.g. --box with z 0.5..1.5 for a floor plan at waist
height, or a 1 m thick y-slab for a cross-section) are far easier to read than the whole cloud.
"""
import sys, os, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("name"); ap.add_argument("--view", default="top")
ap.add_argument("--box"); ap.add_argument("--res", type=float, default=0.05); ap.add_argument("--mode", default="density")
ap.add_argument("--out"); ap.add_argument("--cams", action="store_true"); ap.add_argument("--maxpx", type=int, default=4000)
a = ap.parse_args(); P = Project(a.project)
d = np.load(os.path.join(P.dir, "points_%s.npz" % a.name)); X = d["xyz"].astype(float); C = d["rgb"]
if a.box:
    b = [float(v) for v in a.box.split(",")]; m = np.all((X >= b[:3]) & (X <= b[3:]), axis=1); X, C = X[m], C[m]
ax = {"top": (0, 1, 2), "front": (0, 2, 1), "side": (1, 2, 0)}[a.view]
U, V = X[:, ax[0]], X[:, ax[1]]
u0, u1, v0, v1 = U.min(), U.max(), V.min(), V.max()
res = max(a.res, (u1 - u0) / a.maxpx, (v1 - v0) / a.maxpx)
W, H = int((u1 - u0) / res) + 1, int((v1 - v0) / res) + 1
iu = ((U - u0) / res).astype(int); iv = (H - 1 - (V - v0) / res).astype(int); k = iv * W + iu
if a.mode == "color":
    n = np.bincount(k, minlength=W * H); img = np.zeros((W * H, 3))
    for c in range(3): img[:, c] = np.bincount(k, C[:, c], minlength=W * H) / np.maximum(n, 1)
    img = img.reshape(H, W, 3).astype(np.uint8)
elif a.mode == "height":
    z = np.full(W * H, -np.inf); np.maximum.at(z, k, X[:, ax[2]]); z = z.reshape(H, W); ok = np.isfinite(z)
    t = np.zeros_like(z); t[ok] = (z[ok] - z[ok].min()) / (np.ptp(z[ok]) + 1e-9)
    img = np.zeros((H, W, 3), np.uint8); img[..., 0] = (255 * t).astype(np.uint8); img[..., 1] = (255 * (1 - abs(2 * t - 1))).astype(np.uint8)
    img[..., 2] = (255 * (1 - t)).astype(np.uint8); img[~ok] = 0
else:
    n = np.bincount(k, minlength=W * H).reshape(H, W); g = np.log1p(n); g = (255 * g / (g.max() + 1e-9)).astype(np.uint8)
    img = np.stack([g] * 3, -1)
im = Image.fromarray(img); dr = ImageDraw.Draw(im)
for step, col in ((1, (45, 45, 70)), (10, (90, 90, 150))):
    if (u1 - u0) / step > 400: continue
    for g in np.arange(np.ceil(u0 / step) * step, u1, step):
        x = (g - u0) / res; dr.line([(x, 0), (x, H)], fill=col)
        if step == 10: dr.text((x + 2, 2), "%g" % g, fill=(200, 200, 255))
    for g in np.arange(np.ceil(v0 / step) * step, v1, step):
        y = H - 1 - (g - v0) / res; dr.line([(0, y), (W, y)], fill=col)
        if step == 10: dr.text((2, y + 2), "%g" % g, fill=(200, 200, 255))
if a.cams:
    _, Cm, _ = P.all_centers()
    for c in Cm[:: max(1, len(Cm) // 3000)]:
        x, y = (c[ax[0]] - u0) / res, H - 1 - (c[ax[1]] - v0) / res
        if 0 <= x < W and 0 <= y < H: dr.point((x, y), fill=(60, 140, 255))
out = a.out or os.path.join(P.dir, "plot_%s_%s.png" % (a.name, a.view)); im.save(out)
print(out, "%dx%d px, %.3f m/px, %s %.1f..%.1f  %s %.1f..%.1f" % (W, H, res, "xyz"[ax[0]], u0, u1, "xyz"[ax[1]], v0, v1))

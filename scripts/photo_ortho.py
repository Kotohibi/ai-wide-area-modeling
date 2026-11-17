r"""Photo orthomosaic of the ground: every cell of a plan grid takes its colour from the nearest training photo (cubemap
face) that sees it. Paving joints, gravel / lawn / planting edges and curbs read far better than in point colours, which
carry the capture's shadows and blur. Use it only to read positions - never as a texture on the model.

usage: python photo_ortho.py <project.json> <out.png> --box a0,b0,a1,b1 [--res 0.04] [--z 0.0 | --zgrid terrain.npz]
                             [--frame ox,oy,deg] [--maxdist 14] [--faces front,back,left,right,bottom]
  --box     region in metres: model x/y, or with --frame the rotated frame (a along deg, b to its left)
  --z       ground height of the model frame (constant); --zgrid: npz with Z (rows = y), lo = (x0, y0) and res,
            the ground height per cell (heights matter: a 0.3 m error shifts the colour by ~0.1-0.3 m)
  --frame   align the output to a site grid (origin ox,oy, first axis deg from +x; write --frame=ox,oy,deg when a value is
            negative): rectangular beds become
            axis-aligned and their edges can be read off the grid
  --faces   which cubemap faces to use (face suffix of the image name; others are skipped); default all but "top"
Writes <out.png> (plain), <out>_grid.png (0.5 m / 1 m / 5 m grid with labels) and <out>.json (mapping, for overlays).
Edges read at 2-3x zoom are good to about 0.1-0.2 m near the capture path. Things standing on the ground (tables,
people) smear away from the camera that coloured them; shadows stay in the colours, so judge by texture.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project

ap = argparse.ArgumentParser()
ap.add_argument("project"); ap.add_argument("out"); ap.add_argument("--box", required=True)
ap.add_argument("--res", type=float, default=0.04); ap.add_argument("--z", type=float, default=0.0); ap.add_argument("--zgrid")
ap.add_argument("--frame"); ap.add_argument("--maxdist", type=float, default=14.0); ap.add_argument("--faces")
A = ap.parse_args()
P = Project(A.project)
a0, b0, a1, b1 = [float(v) for v in A.box.split(",")]
if A.frame:
    ox, oy, deg = [float(v) for v in A.frame.split(",")]; th = np.radians(deg)
else:
    ox, oy, th = 0.0, 0.0, 0.0
U = np.array([np.cos(th), np.sin(th)]); V = np.array([-U[1], U[0]]); O = np.array([ox, oy])
W, H = int(round((a1 - a0) / A.res)), int(round((b1 - b0) / A.res))
aa = a0 + (np.arange(W) + 0.5) * A.res; bb = b1 - (np.arange(H) + 0.5) * A.res
AA, BB = np.meshgrid(aa, bb)
XY = O + AA[..., None] * U + BB[..., None] * V
if A.zgrid:
    g = np.load(A.zgrid); Z = g["Z"]; lo = g["lo"]; r = float(g["res"])
    ii = np.clip(((XY[..., 1] - lo[1]) / r).astype(int), 0, Z.shape[0] - 1); jj = np.clip(((XY[..., 0] - lo[0]) / r).astype(int), 0, Z.shape[1] - 1)
    ZZ = Z[ii, jj] + 0.02
else:
    ZZ = np.full(AA.shape, A.z + 0.02)
pts = np.c_[XY[..., 0].ravel(), XY[..., 1].ravel(), ZZ.ravel()]
cx_, cy_ = XY[..., 0].mean(), XY[..., 1].mean(); rad = 0.5 * np.hypot(a1 - a0, b1 - b0) + A.maxdist
faces = set(A.faces.split(",")) if A.faces else None
names = []
for n in sorted(P.imgs):
    stem = os.path.splitext(n)[0]; face = stem.rsplit("_", 1)[-1]
    if faces is not None and face not in faces: continue
    if faces is None and face == "top": continue
    loc = np.array(P.camera(n)["loc"])
    if np.hypot(loc[0] - cx_, loc[1] - cy_) < rad: names.append(n)
print("faces", len(names), "cells", len(pts))
import cv2
best = np.full(len(pts), np.inf, np.float32); col = np.zeros((len(pts), 3), np.uint8)
for k, n in enumerate(names):
    c = P.camera(n); loc = np.array(c["loc"])
    dist = np.linalg.norm(pts - loc, axis=1).astype(np.float32)
    cand = dist < np.minimum(best, A.maxdist)
    if not cand.any(): continue
    uv, dep = P.project_model(n, pts[cand]); w, h = c["w"], c["h"]
    ok = (dep > 0.3) & (uv[:, 0] > 8) & (uv[:, 0] < w - 8) & (uv[:, 1] > 8) & (uv[:, 1] < h - 8)    # off the face seams
    if not ok.any(): continue
    img = cv2.imread(P.photo_path(n)); idx = np.where(cand)[0][ok]; u = uv[ok]
    col[idx] = img[u[:, 1].astype(int), u[:, 0].astype(int)][:, ::-1]; best[idx] = dist[idx]
    if k % 100 == 0: print(k, n, int(np.isfinite(best).sum()))
out = col.reshape(H, W, 3); out[~np.isfinite(best).reshape(H, W)] = 20
from PIL import Image, ImageDraw
Image.fromarray(out).save(A.out)
im = Image.fromarray(out); dr = ImageDraw.Draw(im, "RGBA")
for g in np.arange(np.ceil(a0 * 2) / 2, a1 + 1e-6, 0.5):
    x = (g - a0) / A.res; major = abs(g - round(g)) < 1e-6
    dr.line([(x, 0), (x, H)], fill=(255, 255, 0, (130 if round(g) % 5 == 0 else 70) if major else 30))
    if major and round(g) % 5 == 0: dr.text((x + 2, H - 14), "%d" % round(g), fill=(255, 255, 0))
for g in np.arange(np.ceil(b0 * 2) / 2, b1 + 1e-6, 0.5):
    y = (b1 - g) / A.res; major = abs(g - round(g)) < 1e-6
    dr.line([(0, y), (W, y)], fill=(0, 255, 255, (130 if round(g) % 5 == 0 else 70) if major else 30))
    if major and round(g) % 5 == 0: dr.text((2, y - 13), "%d" % round(g), fill=(0, 255, 255))
stem = os.path.splitext(A.out)[0]; im.save(stem + "_grid.png")
json.dump(dict(box=[a0, b0, a1, b1], res=A.res, frame=[ox, oy, float(np.degrees(th))], W=W, H=H,
               note="pixel (i, j) = frame point (a0 + (i+0.5) res, b1 - (j+0.5) res); model = origin + a*u + b*v"),
          open(stem + ".json", "w"), indent=1)
print("done", W, H, A.out)

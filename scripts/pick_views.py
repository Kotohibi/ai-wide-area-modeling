r"""Photos that show a model point near the image centre, from a distance band, spread over azimuth.
usage: python pick_views.py <project.json> <set> x,y,z --dmin 8 --dmax 30 [--n 8] [--center 0.3] [--bins 8] [--perbin 1] [--sheet out.png]
Writes the set like views.py select (also into the Blender shared folder) and an optional contact sheet."""
import sys, os, argparse, numpy as np
SK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SK)
from project import Project
import colmap_io, views
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("set"); ap.add_argument("point")
ap.add_argument("--dmin", type=float, default=8); ap.add_argument("--dmax", type=float, default=30)
ap.add_argument("--n", type=int, default=8); ap.add_argument("--center", type=float, default=0.3)
ap.add_argument("--sheet"); ap.add_argument("--bins", type=int, default=8); ap.add_argument("--perbin", type=int, default=1)
a = ap.parse_args(views.coords_first(sys.argv[1:]))  # points may be negative
P = Project(a.project); X = np.array([float(v) for v in a.point.split(",")])
Xr = P.to_raw(X[None])[0]; cands = []
for n, im in P.imgs.items():
    cam = P.cams[im["camera_id"]]
    (u, v), z = (lambda r: (r[0][0], r[1][0]))(colmap_io.project(cam, im, Xr[None]))
    if z <= 0: continue
    w, h = cam["width"], cam["height"]; du, dv = abs(u / w - 0.5), abs(v / h - 0.5)
    if du > a.center or dv > a.center: continue
    C = P.to_model(colmap_io.cam_center(im)[None])[0]; d = np.linalg.norm(C[:2] - X[:2])
    if not (a.dmin <= d <= a.dmax): continue
    az = np.degrees(np.arctan2(C[1] - X[1], C[0] - X[0])) % 360
    cands.append((du + dv, d, n, az))
cands.sort(); pick = []; used = {}; frames = set()
for c in cands:                                   # best-centred first, at most --perbin per azimuth bin, one per frame
    b = int(c[3] // (360 / a.bins)); fr = c[2].rsplit("_", 1)[0]
    if used.get(b, 0) < a.perbin and fr not in frames: pick.append(c); used[b] = used.get(b, 0) + 1; frames.add(fr)
    if len(pick) >= a.n: break
cams = [P.camera(c[2]) for c in pick]
sh = P.cfg.get("shared_dir")
if sh and os.path.isdir(sh):
    od = os.path.join(sh, "views", a.set); os.makedirs(od, exist_ok=True)
    for c in cams:
        q = os.path.join(od, "photo_" + os.path.splitext(c["name"])[0] + ".jpg")
        im = Image.open(c["photo"]).convert("RGB"); im.thumbnail((1280, 1280)); im.save(q, quality=90); c["photo_shared"] = q
print(views.write_set(P, a.set, cams))
for c, k in zip(cams, pick): print("  %-34s az %5.1f d %5.1f loc %s" % (c["name"], k[3], k[1], np.round(c["loc"], 1).tolist()))
if a.sheet:
    T = 480; cols = 4; rows = (len(cams) + cols - 1) // cols; S = Image.new("RGB", (cols * T, rows * T))
    for i, (c, k) in enumerate(zip(cams, pick)):
        im = Image.open(c["photo"]).convert("RGB"); im.thumbnail((T, T)); S.paste(im, ((i % cols) * T, (i // cols) * T))
        ImageDraw.Draw(S).text(((i % cols) * T + 4, (i // cols) * T + 4), "%s az%.0f d%.0f" % (c["name"][13:-4], k[3], k[1]), fill=(255, 255, 0))
    S.save(a.sheet); print(a.sheet)

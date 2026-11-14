r"""Pick the training photos (raw cubemap faces or any COLMAP images) that show each comparison target best.

usage: python cmp_select.py <project.json> <targets.json> [--out DIR] [--n 5] [--skip _bottom.png] [--every 1.5]
  targets.json: [{"key": "P2_sign", "xyz": [x, y, z], "dist": [10, 26], "note": "guide sign, front"}, ...]   (model frame, metres)
Score per photo = how central the target is + how far from the middle of the distance range - sharpness - dark area.
Photos closer than --every metres (camera centre) to an already kept one are skipped, so the candidates differ.
Writes <out>/cmp_cands.json and <out>/cmp_cands_XX.jpg (top --n per target, target circled). Look at the sheets and pick by eye:
the score cannot tell whether the object is hidden behind a tree, a truck or a pole.
A face that shows a sign from the front is often not among the top: project the sign into the faces of the frames that pass in front
of it (Project.project_model) and add that face by hand.
"""
import os, sys, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project
import colmap_io
from PIL import Image, ImageDraw, ImageFilter, ImageStat

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("targets"); ap.add_argument("--out"); ap.add_argument("--n", type=int, default=5)
ap.add_argument("--skip", default="_bottom.png", help="image-name suffix to ignore (cubemap floor faces)"); ap.add_argument("--every", type=float, default=1.5)
ap.add_argument("--pool", type=int, default=30, help="candidates per target that get the (slow) sharpness test")
a = ap.parse_args(); P = Project(a.project); out = a.out or os.path.join(P.dir, "compare"); os.makedirs(out, exist_ok=True)
T = json.load(open(a.targets, encoding="utf-8"))
names = sorted(P.imgs); C = np.array([colmap_io.cam_center(P.imgs[n]) for n in names]); Cm = P.to_model(C)

def sharp_dark(path):
    im = Image.open(path).convert("L"); im.thumbnail((640, 640))
    lap = im.filter(ImageFilter.Kernel((3, 3), (0, 1, 0, 1, -4, 1, 0, 1, 0), 1, 128))
    v = np.asarray(lap, float); g = np.asarray(im, float); return float(v.var()), float((g < 25).mean())

res = {}; sheets = []
for t in T:
    X = np.asarray(t["xyz"], float); Xr = P.to_raw(X[None])[0]; d0, d1 = t.get("dist", [5, 40]); cand = []
    for n, c in zip(names, Cm):
        if a.skip and n.endswith(a.skip): continue
        d = float(np.linalg.norm(c - X))
        if not d0 <= d <= d1: continue
        im = P.imgs[n]; cam = P.cams[im["camera_id"]]; (u, v), z = (lambda r: (r[0][0], r[1][0]))(colmap_io.project(cam, im, Xr[None]))
        W, H = cam["width"], cam["height"]
        if z <= 0 or not (.16 * W <= u <= .84 * W and .14 * H <= v <= .86 * H): continue
        cen = np.hypot((u - W / 2) / (W / 2), (v - H / 2) / (H / 2))
        cand.append((cen + .25 * abs(d - (d0 + d1) / 2) / (d1 - d0), n, float(u), float(v), d))
    cand.sort(); kept = []
    for c in cand:
        p = Cm[names.index(c[1])]
        if any(np.linalg.norm(p - Cm[names.index(k[1])]) < a.every for k in kept): continue
        kept.append(c)
        if len(kept) >= a.pool: break
    scored = []
    for c in kept:
        sh, dk = sharp_dark(P.photo_path(c[1])); scored.append((c[0] - .00012 * sh + .8 * dk, c[1], c[2], c[3], c[4], sh))
    scored.sort()
    res[t["key"]] = dict(note=t.get("note", ""), xyz=list(X), cands=[dict(name=s[1], u=s[2], v=s[3], dist=round(s[4], 1), sharp=round(s[5])) for s in scored[:a.n]])
    row = Image.new("RGB", (384 * a.n, 384))
    for i, s in enumerate(scored[:a.n]):
        im = Image.open(P.photo_path(s[1])).convert("RGB"); k = 384 / im.width; im = im.resize((384, int(im.height * k)))
        dr = ImageDraw.Draw(im); x, y = s[2] * k, s[3] * k; dr.ellipse([x - 10, y - 10, x + 10, y + 10], outline=(255, 255, 0), width=3)
        dr.rectangle([0, 0, 384, 30], fill=(0, 0, 0)); dr.text((4, 2), "%s #%d d%.0fm" % (t["key"], i, s[4]), fill=(255, 255, 0)); dr.text((4, 16), s[1][-40:], fill=(255, 255, 0))
        row.paste(im, (384 * i, 0))
    sheets.append(row); print(t["key"], len(cand), "->", [s[1] for s in scored[:3]])
json.dump(res, open(os.path.join(out, "cmp_cands.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for i in range(0, len(sheets), 5):
    rows = sheets[i:i + 5]; S = Image.new("RGB", (rows[0].width, 384 * len(rows)))
    for j, r in enumerate(rows): S.paste(r, (0, 384 * j))
    S.save(os.path.join(out, "cmp_cands_%02d.jpg" % (i // 5)), quality=86)
print("wrote", out)

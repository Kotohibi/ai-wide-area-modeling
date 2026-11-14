r"""Side-by-side check of the model against the photos: photo | 3DGS (same training camera) | Blender | overlay.

usage: python compare_sheet.py <project.json> <set> [--tile 360] [--out sheet.png] [--r 4]

Inputs (all pixel-aligned, same pose and intrinsics):
  photo     the training photo (or the LichtFeld viewport capture for `views.py viewport` sets)
  3DGS      <project_dir>\views\<set>\lfs_<stem>.png      (views.py lfs <set>)
  Blender   <shared>\views\<set>\bl_<stem>.png            (bl_views.py, transparent where there is no geometry)
  overlay   the photo, darkened, with the model's outline (silhouette + crease edges) in red and its surfaces tinted
"edge match" = share of model outline pixels that lie within --r pixels of a strong photo edge. It is a rough,
relative number (textures and shadows also make edges): use it to compare iterations of the SAME view, not as an
absolute score. Judge with your eyes: what is missing, what is offset, what faces the wrong way.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project
from PIL import Image, ImageDraw, ImageFilter

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("set"); ap.add_argument("--tile", type=int, default=360)
ap.add_argument("--out"); ap.add_argument("--r", type=int, default=4); ap.add_argument("--names")
a = ap.parse_args(); P = Project(a.project)
cams = json.load(open(os.path.join(P.dir, "views", a.set + ".json"), encoding="utf-8"))
if a.names: cams = [c for c in cams if c["name"] in a.names.split(",")]
sh = P.cfg.get("shared_dir", ""); T = a.tile

def edges(gray, frac):
    g = np.asarray(gray, float); gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1])); gy = np.abs(np.diff(g, axis=0, prepend=g[:1]))
    m = gx + gy; return m > np.percentile(m, 100 - frac) if m.max() > 0 else np.zeros_like(m, bool)

def dilate(b, r):
    out = b.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(b, dy, 0), dx, 1)
    return out

rows, report = [], []
for c in cams:
    stem = os.path.splitext(c["name"])[0]
    lfs_p = os.path.join(P.dir, "views", a.set, "lfs_" + stem + ".png"); bl_p = os.path.join(sh, "views", a.set, "bl_" + stem + ".png")
    W = T; H = max(1, round(T * c["h"] / c["w"]))
    def load(p, mode="RGB"):
        try: return Image.open(p).convert(mode).resize((W, H))
        except Exception: return None
    photo = load(c.get("photo", "")); gs = load(lfs_p); bl = load(bl_p, "RGBA")
    blank = Image.new("RGB", (W, H), (70, 20, 20))
    tiles = [photo or blank, gs or blank]
    score = None
    if bl:
        bg = Image.new("RGBA", (W, H), (150, 180, 215, 255)); tiles.append(Image.alpha_composite(bg, bl).convert("RGB"))
        alpha = np.asarray(bl)[:, :, 3] > 8
        lum = np.asarray(bl.convert("L"), float); lum[~alpha] = 0
        eroded = np.asarray(Image.fromarray(alpha.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3))) > 0
        sil = alpha & ~eroded
        crease = edges(lum, 6) & alpha
        model_e = sil | crease
        base = photo or gs or blank
        ov = (np.asarray(base, float) * 0.7).astype(np.uint8)
        ov[alpha] = (0.85 * ov[alpha] + 0.15 * np.array([90, 160, 255])).astype(np.uint8)
        ov[model_e] = [255, 40, 40]
        tiles.append(Image.fromarray(ov))
        if photo is not None and model_e.any():
            pe = dilate(edges(photo.convert("L"), 12), a.r); score = float((pe & model_e).sum() / model_e.sum())
        cover = float(alpha.mean())
    else:
        tiles += [blank, blank]; cover = None
    labs = ["photo " + stem[-26:], "3DGS (LichtFeld)", "Blender model", "overlay" + ("  edge match %.0f%%" % (100 * score) if score is not None else "")]
    for t, l in zip(tiles, labs): ImageDraw.Draw(t).text((5, 5), l, fill=(255, 255, 0))
    rows.append(tiles); report.append(dict(name=c["name"], edge_match=score, model_coverage=cover))
    print("%-50s edge match %s  model covers %s of the frame" % (c["name"], "%.2f" % score if score is not None else "-", "%.0f%%" % (100 * cover) if cover is not None else "-"))
Wmax = max(r[0].size[0] for r in rows); sheet = Image.new("RGB", (4 * Wmax, sum(r[0].size[1] for r in rows)), (20, 20, 20)); y = 0
for r in rows:
    for i, t in enumerate(r): sheet.paste(t, (i * Wmax, y))
    y += r[0].size[1]
out = a.out or os.path.join(P.dir, "views", a.set + "_sheet.png"); sheet.save(out)
json.dump(report, open(os.path.join(P.dir, "views", a.set + "_scores.json"), "w"), indent=1); print(out)

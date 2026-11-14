"""Contact sheet of a view set's photos/captures with eye position and look direction.
usage: python set_sheet.py <project_dir> <set> [--tile 400] [--cols 6] [--out sheet.jpg]"""
import sys, os, json, argparse, numpy as np
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("set"); ap.add_argument("--tile", type=int, default=400)
ap.add_argument("--cols", type=int, default=6); ap.add_argument("--out")
a = ap.parse_args()
cams = json.load(open(os.path.join(a.dir, "views", a.set + ".json"), encoding="utf-8"))
T = a.tile; tiles = []
for i, c in enumerate(cams):
    im = Image.open(c["photo"]).convert("RGB"); im.thumbnail((T, T * 2)); tiles.append((c, im))
H = max(im.size[1] for _, im in tiles); cols = min(a.cols, len(tiles)); rows = (len(tiles) + cols - 1) // cols
S = Image.new("RGB", (cols * T, rows * H))
for i, (c, im) in enumerate(tiles):
    x, y = (i % cols) * T, (i // cols) * H; S.paste(im, (x, y))
    R = np.array(c["rot"]); f = -R[:, 2] if "rot" in c else None       # camera looks along -Z of its rotation
    lab = "%d eye %s" % (i, np.round(c["loc"], 1).tolist())
    if f is not None: lab += " az %.0f" % (np.degrees(np.arctan2(f[1], f[0])) % 360)
    ImageDraw.Draw(S).text((x + 4, y + 4), lab, fill=(255, 255, 0))
out = a.out or os.path.join(a.dir, "views", a.set + "_contact.jpg"); S.save(out, quality=88); print(out)

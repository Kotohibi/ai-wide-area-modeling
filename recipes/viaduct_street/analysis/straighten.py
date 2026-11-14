# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Resample a projected photo mosaic (ortho_photo / underside) into a route-straightened strip.

usage: python straighten.py <scratch_dir> <mosaic_name> <s0> <s1> <lat0> <lat1> <px_per_unit> <out.png>
x axis = route distance s (left -> right), y axis = lateral offset (top = +lat = right of travel).
Uses the SAME smoothed route as build_v3.py (degree-4 polynomial in s), so lateral values read here
can be typed straight into PARAMS["deck"] / pier c1, c2. Ticks: white every 5 s (long 10), yellow every 5 lat, cyan = lat 0.
"""
import sys, os, json, numpy as np
from PIL import Image, ImageDraw
SP = sys.argv[1]; NAME = sys.argv[2]
S0, S1, LAT0, LAT1, SC = [float(v) for v in sys.argv[3:8]]; OUT = sys.argv[8]
SH = os.environ.get("BLENDER_SHARED", "")
m = json.load(open(SH + "\\" + NAME + "_meta.json"))
img = np.asarray(Image.open(SH + "\\" + NAME + ".png").convert("RGB"))
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
s_, x_, y_ = P[:, 0], P[:, 1], P[:, 2]
u = (s_ - 266.0) / 180.0
cx = np.polyfit(u, x_, 4); cy = np.polyfit(u, y_, 4)
ss = np.arange(S0, S1, 1.0 / SC); ll = np.arange(LAT1, LAT0, -1.0 / SC)
uu = (ss - 266.0) / 180.0
px, py = np.polyval(cx, uu), np.polyval(cy, uu)
dx, dy = np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)
nrm = np.hypot(dx, dy); tx, ty = dx / nrm, dy / nrm; nx, ny = ty, -tx           # right of travel
X = px[None, :] + ll[:, None] * nx[None, :]; Y = py[None, :] + ll[:, None] * ny[None, :]
ix = ((X - m["x0"]) / m["res"]).astype(int); iy = ((m["y1"] - Y) / m["res"]).astype(int)
ok = (ix >= 0) & (ix < img.shape[1]) & (iy >= 0) & (iy < img.shape[0])
out = np.zeros((len(ll), len(ss), 3), np.uint8)
out[ok] = img[iy[ok], ix[ok]]
im = Image.fromarray(out); d = ImageDraw.Draw(im)
for v in np.arange(np.ceil(S0 / 5) * 5, S1, 5):
    x = int((v - S0) * SC); d.line([(x, 0), (x, 14 if v % 10 == 0 else 6)], fill=(255, 255, 255))
    if v % 20 == 0: d.text((x + 2, 2), str(int(v)), fill=(255, 255, 255))
for v in np.arange(np.ceil(LAT0 / 5) * 5, LAT1, 5):
    y = int((LAT1 - v) * SC); d.line([(0, y), (14 if v % 10 == 0 else 6, y)], fill=(255, 255, 0))
    d.text((16, y - 5), str(int(v)), fill=(255, 255, 0))
y0 = int(LAT1 * SC); d.line([(0, y0), (im.width, y0)], fill=(0, 200, 255))
im.save(OUT); print("straightened", im.size)

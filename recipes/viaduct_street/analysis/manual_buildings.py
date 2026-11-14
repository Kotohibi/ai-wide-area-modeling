"""Turn hand-picked building outlines (pixels on bld_overlay.png from buildings.py) into building records.

usage: python manual_buildings.py <scratch_dir> <spec.json> [scale_px_per_unit=3]
spec.json: [{"name": "...", "type": "box", "pts": [[px,py],...]}   # >=3 outline corners (any order; min-area rectangle is fitted)
            {"name": "...", "type": "cyl", "c": [px,py], "r": px}]  # round building
            optional "h": height in units (otherwise 92th percentile of leveled sparse points inside the outline)
Writes $BLENDER_SHARED/buildings_manual.json (boxes: cx,cy,w,d,ang,h ; cylinders: cx,cy,r,h) and
<scratch_dir>/bld_manual_check.png (outlines drawn on bld_overlay.png) to verify the picks.
Pixel -> leveled frame uses buildings.py's overlay convention: lo = route min - 45... see LO/HI below (must match buildings.py).
"""
import sys, os, json, math, numpy as np
from PIL import Image, ImageDraw
SP = sys.argv[1]; spec = json.load(open(sys.argv[2])); SC = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
SH = os.environ.get("BLENDER_SHARED", "")
Pp = np.array(json.load(open(SH + r"\path_level.json"))["path"])
lo = Pp[:, 1:3].min(0) - 90; hi = Pp[:, 1:3].max(0) + 90          # same as buildings.py overlay
def to_world(px, py): return np.array([lo[0] + px / SC, hi[1] - py / SC])
L = np.load(SP + r"\lP.npy")
out = []; im = Image.open(SP + r"\bld_overlay.png").convert("RGB"); d = ImageDraw.Draw(im)
for b in spec:
    if b["type"] == "cyl":
        c = to_world(*b["c"]); r = b["r"] / SC
        inside = (L[:, 0] - c[0]) ** 2 + (L[:, 1] - c[1]) ** 2 < (r + 1) ** 2
        h = b.get("h") or float(np.percentile(L[inside & (L[:, 2] > 1), 2], 92)) if (inside & (L[:, 2] > 1)).sum() > 20 else b.get("h", 10.0)
        out.append(dict(name=b["name"], kind="cyl", cx=float(c[0]), cy=float(c[1]), r=float(r), h=float(h)))
        d.ellipse([b["c"][0] - b["r"], b["c"][1] - b["r"], b["c"][0] + b["r"], b["c"][1] + b["r"]], outline=(0, 255, 255), width=2)
    else:
        P = np.array([to_world(*p) for p in b["pts"]])
        best = None
        for k in range(len(P)):                      # min-area rectangle over the hull edge directions of the picks
            e = P[(k + 1) % len(P)] - P[k]; a = math.atan2(e[1], e[0]); ca, sa = math.cos(a), math.sin(a)
            q = np.c_[P[:, 0] * ca + P[:, 1] * sa, -P[:, 0] * sa + P[:, 1] * ca]
            w, dd = np.ptp(q[:, 0]), np.ptp(q[:, 1])
            if best is None or w * dd < best[0]:
                mid = np.array([(q[:, 0].min() + q[:, 0].max()) / 2, (q[:, 1].min() + q[:, 1].max()) / 2])
                best = (w * dd, a, w, dd, np.array([mid[0] * ca - mid[1] * sa, mid[0] * sa + mid[1] * ca]))
        _, a, w, dd, c = best
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = L[:, 0] - c[0], L[:, 1] - c[1]; lx = dx * ca + dy * sa; ly = -dx * sa + dy * ca
        inside = (np.abs(lx) < w / 2 + 1) & (np.abs(ly) < dd / 2 + 1) & (L[:, 2] > 1)
        h = b.get("h") or (float(np.percentile(L[inside, 2], 92)) if inside.sum() > 20 else 10.0)
        out.append(dict(name=b["name"], kind="box", cx=float(c[0]), cy=float(c[1]), w=float(w), d=float(dd), ang=float(a), h=float(h)))
        cs = [(c + np.array([sx * w / 2 * ca - sy * dd / 2 * sa, sx * w / 2 * sa + sy * dd / 2 * ca])) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        pix = [((p[0] - lo[0]) * SC, (hi[1] - p[1]) * SC) for p in cs]
        d.polygon(pix, outline=(0, 255, 255))
    d.text((b.get("c", b.get("pts", [[0, 0]])[0])[0] + 4, b.get("c", b.get("pts", [[0, 0]])[0])[1]), b["name"], fill=(0, 255, 255))
json.dump(out, open(SH + r"\buildings_manual.json", "w"))
im.save(SP + r"\bld_manual_check.png")
for o in out: print(o)

# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
r"""Crop every detected pole (poles.json) out of the training photos, seen from both directions along the route.

usage: python sign_views.py <scratch_dir> <out_prefix> [per_sheet=16] [tile=220] [ids=3,18,28] [quad]
  ids  : only these pole ids (from a first full run)
  quad : four views per pole, from the cameras whose bearing (pole -> camera) is nearest to +s, +lat, -s, -lat
         (larger crops around the head). The view in which the coloured face is seen tells the facing.
For each pole (merged like build_ground.py) it picks the best photo looking along +s at it (camera before the pole)
and the best photo looking along -s (camera after the pole), projects the pole head with the COLMAP pose, and crops.
A sign whose coloured face shows in the '+s view' faces -s (towards traffic coming along +s) and vice versa;
a grey back plate means it faces the other way; nothing there means a false pole.
Writes <out_prefix>_N.png sheets and <scratch_dir>\pole_index.json (id, s, lat, x, y, z0, z1).
"""
import sys, os, json, math, numpy as np
from PIL import Image, ImageDraw
SP = sys.argv[1]; OUT = sys.argv[2]; PER = int(sys.argv[3]) if len(sys.argv) > 3 else 16; T = int(sys.argv[4]) if len(sys.argv) > 4 else 220
ONLY = [int(v) for v in sys.argv[5].split(",")] if len(sys.argv) > 5 and sys.argv[5] not in ("", "all") else None
QUAD = len(sys.argv) > 6 and sys.argv[6] == "quad"
SH = os.environ.get("BLENDER_SHARED", ""); SFM = os.environ.get("SFM_DIR", ".")
# --- poles merged exactly as build_ground.py does
poles = json.load(open(SH + r"\poles.json")); kept = []
for p in sorted(poles, key=lambda q: -(q["z1"] - q["z0"])):
    if all((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2 > 1.2 ** 2 for q in kept): kept.append(p)
kept = [p for p in kept if min(p["z1"], 9.0) - max(0.0, min(p["z0"], 0.6)) >= 1.5]
# --- route (smoothed, same as build_v3)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(60, 470, 0.25); U = (ss - 266.0) / 180.0
px, py = np.polyval(cx, U), np.polyval(cy, U); dx, dy = np.polyval(np.polyder(cx), U), np.polyval(np.polyder(cy), U); nn = np.hypot(dx, dy)
def s_lat(x, y):
    i = int(np.argmin((px - x) ** 2 + (py - y) ** 2)); t = np.array([dx[i], dy[i]]) / nn[i]
    return float(ss[i]), float((x - px[i]) * t[1] - (y - py[i]) * t[0]), t
# --- leveled poses for every image (same transform chain as ortho_photo.py)
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"]); c0 = lv["c"]
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
names, Cs, Axs = [], [], []
lines = [l for l in open(SFM + r"\images.txt", encoding="utf-8") if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    t = lines[i].split()
    if len(t) < 10 or t[9].endswith(("_top.png", "_bottom.png")): continue
    R = qmat(np.array([float(v) for v in t[1:5]])); C = -R.T @ np.array([float(v) for v in t[5:8]])
    names.append(t[9]); Cs.append((Rm @ (C - cam0) + np.array([0, 0, h0]) - np.array([0, 0, c0])) @ Rt.T); Axs.append((Rt @ Rm) @ R.T)
Cs = np.array(Cs); Axs = np.array(Axs)
index = []; tiles = []
for k, p in enumerate(kept):
    s, lat, tdir = s_lat(p["x"], p["y"])
    head = np.array([p["x"], p["y"], min(p["z1"], 9.0) - 0.35])
    rel = head - Cs; pc = np.einsum("nij,ni->nj", Axs, rel)           # camera coords: x right, y down, z forward
    z = pc[:, 2]; ok = (z > 2.0) & (z < 22.0)
    uu = 960 + 960 * pc[:, 0] / np.where(ok, z, 1); vv = 960 + 960 * pc[:, 1] / np.where(ok, z, 1)
    ok &= (np.abs(uu - 960) < 700) & (np.abs(vv - 960) < 760)
    along = (Cs[:, :2] - head[:2]) @ tdir                                 # camera before (<0) / after (>0) the pole along s
    across = (Cs[:, :2] - head[:2]) @ np.array([tdir[1], -tdir[0]])       # camera on the +lat (>0) / -lat side
    bearing = np.degrees(np.arctan2(across, along))                       # 0 = camera at +s of the pole, 90 = at +lat
    row = []
    if ONLY is not None and k not in ONLY:
        index.append(dict(id=k, s=s, lat=lat, x=p["x"], y=p["y"], z0=p["z0"], z1=p["z1"])); tiles.append([None, None]); continue
    sectors = ((0, "cam at +s"), (90, "cam at +lat"), (180, "cam at -s"), (-90, "cam at -lat")) if QUAD else ((180, "+s view"), (0, "-s view"))
    for target, _lab in sectors:
        db = np.abs((bearing - target + 180) % 360 - 180)
        m = ok & (db < (45 if QUAD else 90)) & (np.hypot(along, across) > 1.5)
        if not m.any(): row.append(None); continue
        score = np.where(m, np.abs(z - 7.0) + 0.004 * np.abs(uu - 960) + 0.05 * db, 1e9); j = int(np.argmin(score))
        half = int(np.clip(960 * (2.6 if QUAD else 1.6) / z[j], 60, 520))
        try:
            im = Image.open(SFM + r"\images" + "\\" + names[j]).convert("RGB")
            cr = im.crop((int(uu[j]) - half, int(vv[j]) - half, int(uu[j]) + half, int(vv[j]) + half)).resize((T, T))
        except Exception: cr = None
        row.append((cr, names[j], float(z[j])))
    index.append(dict(id=k, s=s, lat=lat, x=p["x"], y=p["y"], z0=p["z0"], z1=p["z1"], blue=p.get("blue", 0)))
    tiles.append(row)
if ONLY is None: json.dump(index, open(SP + r"\pole_index.json", "w"))
order = sorted([k for k in range(len(index)) if ONLY is None or k in ONLY], key=lambda k: index[k]["s"])
NT = 4 if QUAD else 2; LABS = ("cam at +s", "cam at +lat", "cam at -s", "cam at -lat") if QUAD else ("+s view", "-s view")
for sh in range(0, len(order), PER):
    ks = order[sh:sh + PER]; cols = 2 if QUAD else 4                      # poles per row
    rows = (len(ks) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * NT * T, rows * (T + 16)), (30, 30, 30)); d = ImageDraw.Draw(sheet)
    for n, k in enumerate(ks):
        X = (n % cols) * NT * T; Y = (n // cols) * (T + 16)
        it = index[k]; d.text((X + 4, Y + 2), f"#{k} s={it['s']:.0f} lat={it['lat']:.1f} h={it['z1']:.1f}", fill=(255, 255, 0))
        for c_, side in enumerate(LABS):
            tl = tiles[k][c_] if c_ < len(tiles[k]) else None
            if tl and tl[0] is not None:
                sheet.paste(tl[0], (X + c_ * T, Y + 16)); d.text((X + c_ * T + 4, Y + 18), side, fill=(0, 255, 255))
    sheet.save(f"{OUT}_{sh // PER + 1}.png")
print("poles", len(index), "sheets", (len(order) + PER - 1) // PER)

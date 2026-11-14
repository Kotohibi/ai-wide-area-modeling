"""Cross-section profile of the ground classes along the route (to design a procedural road).

usage: python road_profile.py <scratch_dir> <s0> <s1> <win> <lat0> <lat1>
Straightens cls.npy (classify.py: 1 road, 2 sidewalk/plaza, 3 grass) on the smoothed route and prints, for every
window of <win> units, one character per 0.5 units of lateral offset:  '=' road, '-' sidewalk/plaza, 'g' grass, ' ' unknown.
Read carriageways, medians, sidewalks and side streets from it, then write a road spec for build_road.py.
"""
import sys, os, json, numpy as np
SP = sys.argv[1]; S0, S1, WIN, LAT0, LAT1 = [float(v) for v in sys.argv[2:7]]
SH = os.environ.get("BLENDER_SHARED", "")
m = json.load(open(SH + r"\ortho_photo_meta.json")); R2 = m["res"] * 2
cls = np.load(SP + r"\cls.npy")
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
DL = 0.5
lats = np.arange(LAT0, LAT1, DL) + DL / 2
print(" " * 12 + "".join(("|" if abs(l - round(l / 5) * 5) < DL / 2 else " ") for l in lats))
print(" " * 12 + "".join((f"{int(round(l)):<1d}"[-1] if abs(l - round(l / 5) * 5) < DL / 2 else " ") for l in lats) + "   (lat, |=every 5)")
for s0 in np.arange(S0, S1, WIN):
    ss = np.arange(s0, s0 + WIN, 0.5); uu = (ss - 266.0) / 180.0
    px, py = np.polyval(cx, uu), np.polyval(cy, uu); dx, dy = np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)
    nn = np.hypot(dx, dy); nx, ny = dy / nn, -dx / nn
    X = px[None] + lats[:, None] * nx[None]; Y = py[None] + lats[:, None] * ny[None]
    ix = ((X - m["x0"]) / R2).astype(int).clip(0, cls.shape[1] - 1); iy = ((m["y1"] - Y) / R2).astype(int).clip(0, cls.shape[0] - 1)
    c = cls[iy, ix]                                  # (lat, s)
    row = ""
    for k in range(len(lats)):
        v = np.bincount(c[k], minlength=5)
        lab = int(np.argmax(v[1:4]) + 1) if v[1:4].sum() > 0.4 * c.shape[1] else 0
        row += {0: " ", 1: "=", 2: "-", 3: "g"}[lab]
    print(f"s {s0:4.0f}-{s0 + WIN:4.0f} {row}")

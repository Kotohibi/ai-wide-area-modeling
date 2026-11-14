"""Height layers of the leveled sparse cloud inside lateral bands (one per deck), per route window.

usage: python band_heights.py <scratch_dir> "<lat0>:<lat1>,<lat0>:<lat1>,..." <s0> <s1> <win> [zmax=16]
Lateral is measured from the smoothed route (same as build_v3 / straighten). For each window and band it prints a
compact height profile (0.5-unit bins, '#' dense ... ' ' empty) so different deck levels (twin decks at
different heights, upper / lower ramps) are visible at a glance, plus the lowest dense layer above 2.5 units.
Also prints the route (s, lat) of an LFS viewpoint if env LFS_EYE="x,y,z" (world, from camera_get) is set.
"""
import sys, os, json, numpy as np
SP = sys.argv[1]; SH = os.environ.get("BLENDER_SHARED", "")
bands = [tuple(float(v) for v in b.split(":")) for b in sys.argv[2].split(",")]
S0, S1, WIN = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]); ZMAX = float(sys.argv[6]) if len(sys.argv) > 6 else 16.0
L = np.load(SP + r"\lP.npy")
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(S0 - 20, S1 + 20, 0.5); uu = (ss - 266.0) / 180.0
px, py = np.polyval(cx, uu), np.polyval(cy, uu); dx, dy = np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)
nn = np.hypot(dx, dy); tx, ty = dx / nn, dy / nn
box = (L[:, 0] > px.min() - 40) & (L[:, 0] < px.max() + 40) & (L[:, 1] > py.min() - 40) & (L[:, 1] < py.max() + 40) & (L[:, 2] > 0.3) & (L[:, 2] < ZMAX)
L = L[box]
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(ss)):
    d2 = (L[:, 0] - px[i]) ** 2 + (L[:, 1] - py[i]) ** 2; m = d2 < best; best[m] = d2[m]; idx[m] = i
lat = (L[:, 0] - px[idx]) * ty[idx] - (L[:, 1] - py[idx]) * tx[idx]
sv = ss[idx] + (L[:, 0] - px[idx]) * tx[idx] + (L[:, 1] - py[idx]) * ty[idx]
z = L[:, 2]
bins = np.arange(0, ZMAX + 0.01, 0.5)
print("height bins 0.." + str(ZMAX) + " step 0.5 (left = ground)")
for s0 in np.arange(S0, S1, WIN):
    row = f"s {s0:5.0f}-{s0 + WIN:5.0f} "
    for (a, b) in bands:
        m = (sv >= s0) & (sv < s0 + WIN) & (lat >= a) & (lat < b)
        h, _ = np.histogram(z[m], bins=bins); mx = max(h.max(), 1)
        prof = "".join("#" if v > 0.5 * mx else "+" if v > 0.25 * mx else "." if v > 0.08 * mx else " " for v in h)
        dense = [bins[k] for k in range(len(h)) if bins[k] >= 2.5 and h[k] > 0.35 * mx]
        row += f"| [{a:g},{b:g}] {prof} low={dense[0] if dense else '-'} "
    print(row)
eye = os.environ.get("LFS_EYE")
if eye:
    print("(set LFS_EYE handling in the caller: needs the world->leveled transform)")

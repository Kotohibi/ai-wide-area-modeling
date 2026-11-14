# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Detect longitudinal road markings (solid / dashed lines) on the route-straightened orthophoto.

usage: python detect_lines.py <scratch_dir> <s0> <s1> <lat0> <lat1> [exclude s-ranges like 131-161,376-390]
Writes $BLENDER_SHARED/lines.json = [{"s0","s1","lat","type"}] (lat on the smoothed route used by build_v3)
and <scratch_dir>/lines_check.png (detections drawn over the straightened image; red=solid, yellow=dashed).
Lines run along s in the straightened image, so a marking is a row with many 'brighter than local road' pixels.
"""
import sys, os, json, numpy as np
from PIL import Image, ImageDraw
SP = sys.argv[1]; S0, S1, LAT0, LAT1 = [float(v) for v in sys.argv[2:6]]
EXCL = [tuple(float(x) for x in r.split("-")) for r in sys.argv[6].split(",")] if len(sys.argv) > 6 else []
SH = os.environ.get("BLENDER_SHARED", "")
SC = 10.0
m = json.load(open(SH + r"\ortho_photo_meta.json"))
img = np.asarray(Image.open(SH + r"\ortho_photo.png").convert("RGB")).astype(np.float32)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(S0, S1, 1 / SC); ll = np.arange(LAT1, LAT0, -1 / SC); uu = (ss - 266.0) / 180.0
px, py = np.polyval(cx, uu), np.polyval(cy, uu); dx, dy = np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)
nn = np.hypot(dx, dy); nx, ny = dy / nn, -dx / nn
X = px[None] + ll[:, None] * nx[None]; Y = py[None] + ll[:, None] * ny[None]
ix = ((X - m["x0"]) / m["res"]).astype(int).clip(0, img.shape[1] - 1); iy = ((m["y1"] - Y) / m["res"]).astype(int).clip(0, img.shape[0] - 1)
st = img[iy, ix]
L = 0.299 * st[..., 0] + 0.587 * st[..., 1] + 0.114 * st[..., 2]; sat = st.max(-1) - st.min(-1)
def box(a, ry, rx):
    c = np.pad(a, ((ry + 1, ry), (rx + 1, rx)), mode="edge").astype(np.float64).cumsum(0).cumsum(1)
    return ((c[2 * ry + 1:, 2 * rx + 1:] - c[:-2 * ry - 1, 2 * rx + 1:] - c[2 * ry + 1:, :-2 * rx - 1] + c[:-2 * ry - 1, :-2 * rx - 1]) / ((2 * ry + 1) * (2 * rx + 1)))
bg = box(L, 8, 20)
paint = (L - bg > 20) & (sat < 55) & (bg < 120)          # bright, grey, on a darkish (asphalt) background
# road class from classify.py (res = 2 x ortho res): a lane line must have carriageway on both sides
cls = np.load(SP + r"\cls.npy"); R2 = m["res"] * 2
cix = ((X - m["x0"]) / R2).astype(int).clip(0, cls.shape[1] - 1); ciy = ((m["y1"] - Y) / R2).astype(int).clip(0, cls.shape[0] - 1)
road = cls[ciy, cix] == 1
H, W = paint.shape
OFF = int(0.7 * SC)
road_up = np.vstack([road[OFF:], np.zeros((OFF, W), bool)]); road_dn = np.vstack([np.zeros((OFF, W), bool), road[:-OFF]])
lines = []
WIN = int(15 * SC)
for c0 in range(0, W - WIN + 1, WIN // 2):
    s_mid = S0 + (c0 + WIN / 2) / SC
    if any(a <= s_mid <= b for a, b in EXCL): continue
    cov = paint[:, c0:c0 + WIN].mean(1)
    cov = np.convolve(cov, np.ones(3) / 3, "same")
    both = (road_up[:, c0:c0 + WIN] & road_dn[:, c0:c0 + WIN]).mean(1)       # carriageway on both sides
    r = 1
    while r < H - 1:
        if cov[r] > 0.16 and cov[r] >= cov[r - 1] and cov[r] >= cov[r + 1] and both[r] > 0.6:
            lat = LAT1 - (r + 0.5) / SC
            lines.append(dict(s0=S0 + c0 / SC, s1=S0 + (c0 + WIN) / SC, lat=float(lat), cov=float(cov[r]), type="solid" if cov[r] > 0.55 else "dashed"))
            r += 4
        r += 1
# merge overlapping windows into runs along s
lines.sort(key=lambda d: (round(d["lat"] * 2) / 2, d["s0"]))
runs = []
for d in lines:
    for rr in runs:
        if abs(rr["lat"] - d["lat"]) < 0.45 and d["s0"] <= rr["s1"] + 0.1 and rr["type"] == d["type"]:
            rr["s1"] = max(rr["s1"], d["s1"]); rr["lat"] = 0.7 * rr["lat"] + 0.3 * d["lat"]; break
    else:
        runs.append(dict(d))
runs = [r for r in runs if r["s1"] - r["s0"] >= 15]
json.dump(runs, open(SH + r"\lines.json", "w"))
print("line runs", len(runs))
for r in runs: print(f"  s {r['s0']:6.1f}-{r['s1']:6.1f} lat {r['lat']:5.2f} {r['type']}")
vis = Image.fromarray(np.clip(st, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(vis)
for r in runs:
    y = (LAT1 - r["lat"]) * SC; d.line([((r["s0"] - S0) * SC, y), ((r["s1"] - S0) * SC, y)], fill=(255, 40, 40) if r["type"] == "solid" else (255, 230, 0), width=2)
vis.save(SP + r"\lines_check.png")

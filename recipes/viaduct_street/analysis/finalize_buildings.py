# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
"""Post-process detected building boxes (buildings.py -> buildings_final2.json).

1. Thicken thin boxes (only the facade is reconstructed) away from the route.
2. Drop boxes that sit on the road (a footprint >12% road class = false detection).

usage: python finalize_buildings.py <scratch_dir> [min_depth=14] [max_road_frac=0.12]
Needs: $BLENDER_SHARED/{buildings.json,path_level.json,ortho_photo_meta.json}, <scratch_dir>/cls.npy
"""
import sys, os, json, math, numpy as np
SP = sys.argv[1]
MIN_D = float(sys.argv[2]) if len(sys.argv) > 2 else 14.0
MAX_ROAD = float(sys.argv[3]) if len(sys.argv) > 3 else 0.12
SH = os.environ.get("BLENDER_SHARED", "")
B = json.load(open(SH + r"\buildings.json"))
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
m = json.load(open(SH + r"\ortho_photo_meta.json")); R2 = m["res"] * 2
cls = np.load(SP + r"\cls.npy"); H2, W2 = cls.shape
out = []
for b in B:
    c = np.array([b["cx"], b["cy"]]); d = np.linalg.norm(P[:, 1:3] - c, axis=1); i = d.argmin()
    ax = np.array([math.cos(b["ang"]), math.sin(b["ang"])]); ay = np.array([-ax[1], ax[0]])
    if (c - P[i, 1:3]) @ ay < 0: ay = -ay                    # push away from the route
    if b["d"] < MIN_D:
        c = c + ay * (MIN_D - b["d"]) / 2; b["d"] = MIN_D
    b["w"] = max(b["w"], MIN_D)
    b["cx"], b["cy"] = float(c[0]), float(c[1]); b["dist"] = float(d[i])
    ca, sa = math.cos(b["ang"]), math.sin(b["ang"]); n = r = 0
    for u in np.linspace(-0.5, 0.5, 15):
        for v in np.linspace(-0.5, 0.5, 15):
            X = b["cx"] + u * b["w"] * ca - v * b["d"] * sa; Y = b["cy"] + u * b["w"] * sa + v * b["d"] * ca
            ix = int((X - m["x0"]) / R2); iy = int((m["y1"] - Y) / R2)
            if 0 <= ix < W2 and 0 <= iy < H2: n += 1; r += int(cls[iy, ix] == 1)
    b["road_frac"] = r / max(n, 1)
    if b["dist"] > 6 and b["road_frac"] < MAX_ROAD: out.append(b)
json.dump(out, open(SH + r"\buildings_final2.json", "w"))
print(len(out), "of", len(B), "buildings kept")

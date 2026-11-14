r"""Draw the detected poles (pole_index.json, with ids) and the modelled furniture facing into training photos.

usage: python overlay_poles.py <scratch_dir> <out.png> <tile> name1.png name2.png ...
Each pole is projected with the COLMAP pose as a vertical line (base -> head) labelled '#id'. For poles that are in
street_furniture.json the label also shows the modelled type and an arrow for the face direction (projected 1.5 units
from the head), so you can check directly in the photo whether a sign / signal head really faces that way.
Yellow = light, cyan = sign, magenta = signal, red = not modelled (dropped).
"""
import sys, os, json, math, numpy as np
from PIL import Image, ImageDraw
SP, OUT, T = sys.argv[1], sys.argv[2], int(sys.argv[3]); NAMES = sys.argv[4:]
SH = os.environ.get("BLENDER_SHARED", ""); SFM = os.environ.get("SFM_DIR", ".")
idx = json.load(open(SP + r"\pole_index.json"))
spec = {(round(o["x"], 3), round(o["y"], 3)): o for o in json.load(open(SH + r"\street_furniture.json"))["items"]} if os.path.exists(SH + r"\street_furniture.json") else {}
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"]); c0 = lv["c"]
P = np.array(lv["path"]); u = (P[:, 0] - 266.0) / 180.0; pcx = np.polyfit(u, P[:, 1], 4); pcy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(40, 480, 0.25); U = (ss - 266.0) / 180.0
px, py = np.polyval(pcx, U), np.polyval(pcy, U); dx, dy = np.polyval(np.polyder(pcx), U), np.polyval(np.polyder(pcy), U); nn = np.hypot(dx, dy)
def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
poses = {}
lines = [l for l in open(SFM + r"\images.txt", encoding="utf-8") if not l.startswith("#")]
for i in range(0, len(lines) - 1, 2):
    t = lines[i].split()
    if len(t) >= 10 and t[9] in NAMES:
        R = qmat(np.array([float(v) for v in t[1:5]])); C = -R.T @ np.array([float(v) for v in t[5:8]])
        poses[t[9]] = ((Rm @ (C - cam0) + np.array([0, 0, h0]) - np.array([0, 0, c0])) @ Rt.T, (Rt @ Rm) @ R.T)
def proj(X, C, A):
    pc = A.T @ (np.asarray(X) - C)
    if pc[2] < 0.5: return None
    return (960 + 960 * pc[0] / pc[2], 960 + 960 * pc[1] / pc[2])
tiles = []
for n in NAMES:
    if n not in poses: continue
    C, A = poses[n]
    im = Image.open(SFM + r"\images" + "\\" + n).convert("RGB"); d = ImageDraw.Draw(im)
    for p in idx:
        o = spec.get((round(p["x"], 3), round(p["y"], 3)))
        typ = o["type"] if o else "drop"
        colr = {"light": (255, 230, 0), "sign": (0, 255, 255), "signal": (255, 0, 255), "drop": (255, 40, 40)}[typ]
        a = proj((p["x"], p["y"], 0.2), C, A); bb = proj((p["x"], p["y"], min(p["z1"], 9) + 0.3), C, A)
        if not a or not bb or not (-200 < bb[0] < 2120 and -200 < bb[1] < 2120): continue
        d.line([a, bb], fill=colr, width=5); d.text((bb[0] + 6, bb[1] - 14), f"#{p['id']} {typ}", fill=colr)
        if o and "face" in o:
            i = int(np.argmin((px - p["x"]) ** 2 + (py - p["y"]) ** 2)); tt = np.array([dx[i], dy[i]]) / nn[i]; nr = np.array([tt[1], -tt[0]])
            r = math.radians(o["face"]); f = math.cos(r) * tt + math.sin(r) * nr
            hz = min(p["z1"], 9) * 0.8; q0 = proj((p["x"], p["y"], hz), C, A); q1 = proj((p["x"] + 1.5 * f[0], p["y"] + 1.5 * f[1], hz), C, A)
            if q0 and q1: d.line([q0, q1], fill=colr, width=7); d.ellipse([q1[0] - 9, q1[1] - 9, q1[0] + 9, q1[1] + 9], fill=colr)
    tiles.append(im.resize((T, T)))
cols = 3; rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * T, rows * T))
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * T, (k // cols) * T))
sheet.save(OUT); print(sheet.size)

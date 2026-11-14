import sys, json, zlib, struct, numpy as np
from PIL import Image
SP = sys.argv[1]; SH = __import__("os").environ.get("BLENDER_SHARED", "")
m = json.load(open(SH + r"\ortho_photo_meta.json")); R = m["res"]
im = np.asarray(Image.open(SP + r"\ortho_photo.png").convert("RGB")).astype(np.float32)
cls2 = np.load(SP + r"\cls.npy"); H, W, _ = im.shape
road = np.kron(cls2 == 1, np.ones((2, 2), bool))[:H, :W]
if road.shape != (H, W): road = np.pad(road, ((0, H - road.shape[0]), (0, W - road.shape[1])))
def box(a, r):
    c = np.pad(a, ((r + 1, r), (r + 1, r)), mode="edge").astype(np.float64).cumsum(0).cumsum(1)
    n = 2 * r + 1
    return ((c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)).astype(np.float32)
L = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]; sat = im.max(-1) - im.min(-1)
# road band: road dilated by 10 px (to include markings that classify as bright)
rb = box(road.astype(np.float32), 10) > 0.05
loc = box(L, 22)
paint = rb & (L > loc + 28) & (L > 120) & (sat < 55)
# remove isolated speckles
cnt = box(paint.astype(np.float32), 1) * 9
paint &= cnt >= 3
ys, xs = np.nonzero(paint)
print("paint px", len(ys))
# connected components over paint pixels (8-neigh) with a dict-based BFS
idx = {(y, x): i for i, (y, x) in enumerate(zip(ys.tolist(), xs.tolist()))}
lab = -np.ones(len(ys), np.int32); comps = []
for i in range(len(ys)):
    if lab[i] >= 0: continue
    k = len(comps); lab[i] = k; st = [i]; mem = [i]
    while st:
        j = st.pop(); y, x = ys[j], xs[j]
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                q = idx.get((y + dy, x + dx))
                if q is not None and lab[q] < 0: lab[q] = k; st.append(q); mem.append(q)
    comps.append(mem)
print("components", len(comps))
items = []
for mem in comps:
    if len(mem) < 12: continue
    pts = np.stack([xs[mem], ys[mem]], 1).astype(np.float32)
    c = pts.mean(0); u, s, vt = np.linalg.svd(pts - c, full_matrices=False)
    a = vt[0]; pa = (pts - c) @ a; pb = (pts - c) @ vt[1]
    ln = (np.percentile(pa, 98) - np.percentile(pa, 2)) * R; wd = (np.percentile(pb, 98) - np.percentile(pb, 2)) * R
    cx = m["x0"] + (c[0] + 0.5) * R; cy = m["y1"] - (c[1] + 0.5) * R
    ang = float(np.arctan2(-a[1], a[0]))                # image y is flipped
    items.append(dict(cx=float(cx), cy=float(cy), len=float(ln), wid=float(max(wd, 0.12)), ang=ang, n=len(mem)))
print("kept comps", len(items))
stripes = [t for t in items if 1.4 <= t["len"] <= 7.5 and t["wid"] <= 0.9 and t["len"] / t["wid"] >= 2.5]
lines = [t for t in items if t["len"] > 7.5 and t["wid"] <= 0.7]
print("stripes", len(stripes), "lines", len(lines))
json.dump({"stripes": stripes, "lines": lines}, open(SH + r"\paint.json", "w"))
# overlay preview on the ortho around a crosswalk (s~140)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
def save_png(path, a):
    h, w, c = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        cc = struct.pack(">I", len(d)) + t + d
        return cc + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
ov = im.astype(np.uint8).copy()
ov[paint] = (255, 40, 40)
cx = int((np.interp(140, P[:, 0], P[:, 1]) - m["x0"]) / R); cy = int((m["y1"] - np.interp(140, P[:, 0], P[:, 2])) / R)
crop = ov[cy - 220:cy + 220, cx - 220:cx + 220]
save_png(SP + r"\paint_crop.png", np.ascontiguousarray(np.kron(crop, np.ones((2, 2, 1), np.uint8))))

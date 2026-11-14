import sys, json, zlib, struct, numpy as np
from PIL import Image
SP = sys.argv[1]; import os; SH = os.environ.get("BLENDER_SHARED", "")
m = json.load(open(SH + r"\ortho_photo_meta.json")); P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
im = np.asarray(Image.open(SP + r"\ortho_photo.png").convert("RGB")).astype(np.float32)
valid = np.load(SP + r"\ortho_photo_valid.npy")
H, W, _ = im.shape; R = m["res"]
# 2x downsample (res 0.24)
H2, W2 = H // 2, W // 2
img = im[:H2 * 2, :W2 * 2].reshape(H2, 2, W2, 2, 3).mean((1, 3)); val = valid[:H2 * 2, :W2 * 2].reshape(H2, 2, W2, 2).mean((1, 3)) > 0.4
R2 = R * 2
r, g, b = img[..., 0], img[..., 1], img[..., 2]
L = 0.299 * r + 0.587 * g + 0.114 * b; sat = img.max(-1) - img.min(-1)
grass = (g > r + 6) & (g > b + 6) & (L < 190)
dark = (L < 105) & (sat < 50) & ~grass
white = (L > 175) & (sat < 45)
mid = ~grass & ~dark & ~white
cls = np.zeros((H2, W2), np.uint8)               # 0 none, 1 road, 2 sidewalk/plaza, 3 grass, 4 white paint
cls[val & mid] = 2; cls[val & grass] = 3; cls[val & dark] = 1; cls[val & white] = 4
def majority(c, k=1, n=3):
    out = c.copy(); stack = []
    pad = np.pad(c, k, mode="edge")
    cnts = np.stack([sum((pad[k + dy:k + dy + c.shape[0], k + dx:k + dx + c.shape[1]] == v).astype(np.int8) for dy in range(-k, k + 1) for dx in range(-k, k + 1)) for v in range(5)])
    return cnts.argmax(0).astype(np.uint8)
cls2 = majority(cls)
# white paint only counts when adjacent to road; elsewhere it is bright pavement
roadish = (cls2 == 1)
pad = np.pad(roadish, 3)
near_road = sum(pad[3 + dy:3 + dy + H2, 3 + dx:3 + dx + W2] for dy in range(-3, 4) for dx in range(-3, 4)) > 8
cls2[(cls2 == 4) & ~near_road] = 2
# restrict to the corridor around the route (35 units)
gx = m["x0"] + (np.arange(W2) + 0.5) * R2; gy = m["y1"] - (np.arange(H2) + 0.5) * R2
corr = np.zeros((H2, W2), bool)
for p in P[::2]:
    ix0 = max(0, int((p[1] - 36 - m["x0"]) / R2)); ix1 = min(W2, int((p[1] + 36 - m["x0"]) / R2)); iy0 = max(0, int((m["y1"] - (p[2] + 36)) / R2)); iy1 = min(H2, int((m["y1"] - (p[2] - 36)) / R2))
    xx, yy = np.meshgrid(gx[ix0:ix1], gy[iy0:iy1]); corr[iy0:iy1, ix0:ix1] |= ((xx - p[1]) ** 2 + (yy - p[2]) ** 2) < 36 ** 2
cls2[~corr] = 0
np.save(SP + r"\cls.npy", cls2)
pal = np.array([[30, 32, 30], [60, 62, 68], [170, 160, 140], [70, 120, 60], [255, 255, 255]], np.uint8)
prev = pal[cls2]
def save_png(path, a):
    h, w, c = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        cc = struct.pack(">I", len(d)) + t + d
        return cc + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
save_png(SP + r"\cls_preview.png", np.ascontiguousarray(prev))
print("classes", {int(k): int((cls2 == k).sum()) for k in range(5)}, "grid", W2, H2, "res", R2)

# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, json, zlib, struct, numpy as np
SP = sys.argv[1]
import os; SHARED = os.environ.get("BLENDER_SHARED", "")
def save_png(path, a):
    h, w, _ = a.shape
    raw = b"".join(b"\x00" + a[i].tobytes() for i in range(h))
    def ch(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
L = np.load(SP + r"\lP.npy")
Pp = np.array(json.load(open(SHARED + r"\path_level.json"))["path"])
s_st = Pp[:, 0]
t = np.gradient(Pp[:, 1:3], axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True); nr = np.c_[t[:, 1], -t[:, 0]]
LAT0, LAT1, SS0, SS1 = -30.0, 40.0, 88.0, 446.0
w = (L[:, 2] > 0.3) & (L[:, 2] < 12)
L = L[w]
# nearest station (by xy) -> (s, lat)
best = np.full(len(L), 1e9, np.float32); idx = np.zeros(len(L), np.int32)
for i in range(len(Pp)):
    d2 = (L[:, 0] - Pp[i, 1]) ** 2 + (L[:, 1] - Pp[i, 2]) ** 2
    m = d2 < best; best[m] = d2[m]; idx[m] = i
lat = ((L[:, 0] - Pp[idx, 1]) * nr[idx, 0] + (L[:, 1] - Pp[idx, 2]) * nr[idx, 1])
al = ((L[:, 0] - Pp[idx, 1]) * t[idx, 0] + (L[:, 1] - Pp[idx, 2]) * t[idx, 1])
sv = s_st[idx] - al                      # travel direction: +al = forward along route = increasing s
ok = (lat > LAT0) & (lat < LAT1) & (sv > SS0) & (sv < SS1)
L, lat, sv = L[ok], lat[ok], sv[ok]
SC = 4.0                                 # px per unit
W = int((SS1 - SS0) * SC); H = int((LAT1 - LAT0) * SC)
def grid(m):
    g = np.zeros((H, W), np.float32)
    ix = ((sv[m] - SS0) * SC).astype(int).clip(0, W - 1); iy = ((LAT1 - lat[m]) * SC).astype(int).clip(0, H - 1)
    np.add.at(g, (iy, ix), 1); return g
A = grid((L[:, 2] > 3.6) & (L[:, 2] < 9.5))      # deck / girders band
B = grid((L[:, 2] > 0.8) & (L[:, 2] < 3.4))      # pier band
img = np.zeros((H, W, 3), np.uint8)
img[..., 0] = np.clip(A * 60, 0, 255); img[..., 1] = np.clip(B * 60, 0, 255); img[..., 2] = np.clip((A + B) * 15, 0, 120)
for sg in range(90, 446, 10):
    x = int((sg - SS0) * SC)
    img[0:(24 if sg % 50 == 0 else 8), x] = (255, 255, 255)
for lt in range(int(LAT0), int(LAT1) + 1, 5):
    y = min(int((LAT1 - lt) * SC), H - 1)
    img[y, 0:(24 if lt % 10 == 0 else 8)] = (255, 255, 0)
y0 = int(LAT1 * SC); img[y0, ::4] = (0, 120, 255)           # lat = 0 (route)
save_png(SP + r"\unwrap.png", np.ascontiguousarray(img)); print("unwrap", W, H)
np.save(SP + r"\unwrapA.npy", A); np.save(SP + r"\unwrapB.npy", B)

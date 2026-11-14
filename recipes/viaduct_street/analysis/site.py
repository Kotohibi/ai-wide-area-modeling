import sys, numpy as np
SP = sys.argv[1]
N = 15000000
off = open(SP + r"\model_sh0.ply", "rb").read(3000).find(b"end_header") + 11
a = np.memmap(SP + r"\model_sh0.ply", dtype=np.float32, mode="r", offset=off, shape=(N, 17))
g = np.load(SP + r"\ground.npy"); n = g[0:3]; cen = g[3:6]; cam = g[6:9]
b = np.load(SP + r"\basis.npy"); right, fwd, up = b[0:3], b[3:6], b[6:9]
Rm = np.stack([right, fwd, up]).astype(np.float32)          # raw -> (x right, y fwd, h up)
h0 = float((cam - cen) @ up)                                  # camera height above ground
P, C, S, O = [], [], [], []
B = 1000000
for i in range(0, N, B):
    blk = np.asarray(a[i:i+B])
    rel = blk[:, 0:3] - cam.astype(np.float32)
    q = rel @ Rm.T
    q[:, 2] += h0
    op = 1 / (1 + np.exp(-blk[:, 9]))
    sc = np.exp(blk[:, 10:13]).max(1)
    m = (op > 0.35) & (sc < 3.0) & (np.abs(q[:, 0]) < 90) & (q[:, 1] > -50) & (q[:, 1] < 140) & (q[:, 2] > -1.5) & (q[:, 2] < 25)
    P.append(q[m]); S.append(sc[m]); O.append(op[m])
    C.append((np.clip(0.5 + 0.28209479 * blk[m, 6:9], 0, 1) * 255).astype(np.uint8))
P = np.concatenate(P); C = np.concatenate(C); S = np.concatenate(S); O = np.concatenate(O)
print("site points", len(P), "camera height", h0)
np.save(SP + r"\sP.npy", P); np.save(SP + r"\sC.npy", C); np.save(SP + r"\sS.npy", S); np.save(SP + r"\sO.npy", O)

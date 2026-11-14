import sys, json, numpy as np
SP = sys.argv[1]; SH = __import__("os").environ.get("BLENDER_SHARED", "")
N = 15000000
off = open(SP + r"\model_sh0.ply", "rb").read(3000).find(b"end_header") + 11
a = np.memmap(SP + r"\model_sh0.ply", dtype=np.float32, mode="r", offset=off, shape=(N, 17))
g = np.load(SP + r"\ground.npy"); cen = g[3:6]; cam0 = g[6:9]
b = np.load(SP + r"\basis.npy"); Rm = np.stack([b[0:3], b[3:6], b[6:9]]); h0 = float((cam0 - cen) @ b[6:9])
lv = json.load(open(SH + r"\path_level.json")); Rt = np.array(lv["Rt"]); c = lv["c"]
tot = 0; zs = []; ss = []; ops = []
for i in range(0, N, 1000000):
    blk = np.asarray(a[i:i + 1000000])
    q = (blk[:, 0:3] - cam0) @ Rm.T; q[:, 2] += h0; q[:, 2] -= c; q = q @ Rt.T
    m = (q[:, 0] > -140) & (q[:, 0] < 60) & (q[:, 1] > -275) & (q[:, 1] < 125)
    tot += int(m.sum())
    zz = q[m, 2]; sc = np.exp(blk[m, 10:13]).max(1); op = 1 / (1 + np.exp(-blk[m, 9]))
    sel = (zz > -3) & (zz < 4)
    zs.append(zz[sel][::20]); ss.append(sc[sel][::20]); ops.append(op[sel][::20])
zs = np.concatenate(zs); ss = np.concatenate(ss); ops = np.concatenate(ops)
print("points inside xy window", tot, "sampled", len(zs))
h, e = np.histogram(zs, bins=np.arange(-3, 4.01, 0.5))
for k in range(len(h)): print(f"z {e[k]:5.1f} n={h[k]}")
m = (zs > -0.6) & (zs < 0.6)
print("ground-band sample", int(m.sum()), "scale pct", np.percentile(ss[m], [10, 50, 90, 99]), "opacity pct", np.percentile(ops[m], [10, 50, 90]))

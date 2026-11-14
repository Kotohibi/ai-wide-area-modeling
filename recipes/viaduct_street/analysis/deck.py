import sys, json, numpy as np
SP = sys.argv[1]
s_lo, s_hi, step = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
P = np.load(SP + r"\fP.npy")
tr = np.load(SP + r"\traj_site.npy"); sm = tr[:, :3]; d = tr[:, 3]
h0 = 1.0815199170913725
res = []
for s in np.arange(s_lo, s_hi, step):
    i = np.searchsorted(d, s)
    if i < 3 or i >= len(sm) - 3: continue
    t = sm[i + 3, :2] - sm[i - 3, :2]; t /= np.linalg.norm(t)
    nrm = np.array([t[1], -t[0]])
    rel = P[:, :2] - sm[i, :2]
    al = rel @ t; lat = rel @ nrm
    gh = sm[i, 2] - h0
    hr = P[:, 2] - gh
    near = (np.abs(al) < 2.5) & (np.abs(lat) < 32)
    m = near & (hr > 3.0) & (hr < 12)
    if m.sum() < 200: continue
    hh, e = np.histogram(hr[m], bins=np.arange(3, 12.01, 0.25))
    cand = [k for k in range(1, len(hh) - 1) if hh[k] >= 0.35 * hh.max() and hh[k] >= hh[k-1] and hh[k] >= hh[k+1]]
    pk = e[cand[0]] + 0.125 if cand else e[np.argmax(hh)] + 0.125
    layer = m & (np.abs(hr - pk) < 0.5)
    L = lat[layer]
    if len(L) < 100: continue
    lo, med, hi = np.percentile(L, [8, 50, 92])
    # pier signal: points between road and deck within the deck lateral extent
    col = near & (hr > 0.6) & (hr < pk - 0.8) & (lat > lo) & (lat < hi)
    res.append(dict(s=float(s), x=float(sm[i,0]), y=float(sm[i,1]), gh=float(gh), tx=float(t[0]), ty=float(t[1]),
                    lat_lo=float(lo), lat_med=float(med), lat_hi=float(hi), under=float(pk), n=int(layer.sum()), col=int(col.sum())))
json.dump(res, open(SP + r"\deck.json", "w"))
print("  s     lat_lo  med   lat_hi  width under  n    colpts")
for r in res: print(f"{r['s']:6.1f} {r['lat_lo']:6.1f} {r['lat_med']:6.1f} {r['lat_hi']:6.1f} {r['lat_hi']-r['lat_lo']:5.1f} {r['under']:5.2f} {r['n']:6d} {r['col']:6d}")

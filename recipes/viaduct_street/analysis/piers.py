import sys, json, numpy as np
SP = sys.argv[1]
s_lo, s_hi = float(sys.argv[2]), float(sys.argv[3])
P = np.load(SP + r"\fP.npy"); tr = np.load(SP + r"\traj_site.npy"); sm = tr[:, :3]; d = tr[:, 3]
h0 = 1.0815199170913725
ss = np.arange(s_lo, s_hi, 1.0); cnt = np.zeros(len(ss)); latpk = []
for j, s in enumerate(ss):
    i = np.searchsorted(d, s)
    t = sm[i + 3, :2] - sm[i - 3, :2]; t /= np.linalg.norm(t); nrm = np.array([t[1], -t[0]])
    rel = P[:, :2] - sm[i, :2]; al = rel @ t; lat = rel @ nrm; hr = P[:, 2] - (sm[i, 2] - h0)
    m = (np.abs(al) < 1.5) & (lat > -6) & (lat < 20) & (hr > 0.8) & (hr < 3.3)
    cnt[j] = m.sum()
    hh, e = np.histogram(lat[m], bins=np.arange(-6, 20.01, 1.0)); latpk.append(hh)
sc = np.convolve(cnt, np.ones(3) / 3, "same")
thr = np.percentile(sc, 80)
peaks = [j for j in range(2, len(sc) - 2) if sc[j] >= thr and sc[j] == sc[max(0, j-6):j+7].max()]
print("threshold", round(float(thr)), "peaks (s, count):")
for j in peaks:
    top = np.argsort(-latpk[j])[:4]
    print(f"  s={ss[j]:6.0f} n={int(sc[j]):6d}  densest lateral bins (lat): {sorted(float(-6+k) for k in top)}")

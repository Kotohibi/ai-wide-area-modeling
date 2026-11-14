# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, json, numpy as np
SP = sys.argv[1]
import os; SHARED = os.environ.get("BLENDER_SHARED", "")
A = np.load(SP + r"\unwrapA.npy"); B = np.load(SP + r"\unwrapB.npy")
SC, SS0, LAT1 = 4.0, 88.0, 40.0
H, W = A.shape
lat_of = lambda r: LAT1 - (r + 0.5) / SC
# --- deck lateral extent per 10-unit s window (band A), restricted to lat -8..22
win = 10
rows_ok = [(r) for r in range(H) if -8 <= lat_of(r) <= 22]
deck = []
for s0 in np.arange(90, 440, win):
    c0, c1 = int((s0 - SS0) * SC), int((s0 + win - SS0) * SC)
    prof = A[:, c0:c1].sum(1)
    pr = np.array([prof[r] for r in rows_ok]); lt = np.array([lat_of(r) for r in rows_ok])
    if pr.sum() < 30: continue
    cdf = np.cumsum(pr) / pr.sum()
    lo = float(np.interp(0.06, cdf, lt[::1][::-1][::-1])) if False else None
    order = np.argsort(lt); pr2 = pr[order]; lt2 = lt[order]
    cdf = np.cumsum(pr2) / pr2.sum()
    lo = float(np.interp(0.05, cdf, lt2)); hi = float(np.interp(0.95, cdf, lt2)); med = float(np.interp(0.5, cdf, lt2))
    deck.append((float(s0 + win / 2), lo, med, hi, float(pr.sum())))
print("deck extent (s, lat5, lat50, lat95, mass)")
for d in deck: print("  %5.0f %6.1f %6.1f %6.1f %7.0f" % d)
# --- pier peaks from band B
cols = B[[r for r in range(H) if -6 <= lat_of(r) <= 20], :].sum(0)
sm = np.convolve(cols, np.ones(5) / 5, "same")
thr = np.percentile(sm, 88)
peaks = []
for x in range(3, W - 3):
    if sm[x] >= thr and sm[x] == sm[max(0, x - 20):x + 21].max():
        s = SS0 + x / SC
        c0, c1 = max(0, x - 6), min(W, x + 7)
        prof = B[:, c0:c1].sum(1)
        pr = np.array([prof[r] for r in rows_ok]); lt = np.array([lat_of(r) for r in rows_ok]); o = np.argsort(lt)
        cdf = np.cumsum(pr[o]) / max(pr.sum(), 1)
        peaks.append((float(s), float(sm[x]), float(np.interp(0.05, cdf, lt[o])), float(np.interp(0.95, cdf, lt[o]))))
print("pier peaks (s, strength, lat5, lat95)")
for p in peaks: print("  %6.1f %7.1f %6.1f %6.1f" % p)
json.dump({"deck": deck, "piers": peaks}, open(SHARED + r"\deck_piers.json", "w"))

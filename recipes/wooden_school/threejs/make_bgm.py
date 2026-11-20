r"""Two BGM loops for the Three.js viewer, synthesised with numpy only (no samples, no existing tune):
    "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" web\make_bgm.py     (any Python with numpy; ffmpeg on the PATH)
    -> public\bgm_restored.m4a, public\bgm_ruin.m4a, public\bgm.json ({"loop": seconds})
The two pieces are ONE tune in two states, on the same grid (72 BPM, 16 bars of 4/4 = 53.33 s), so the viewer can start them together and
fade from one to the other - or mix them in the split-screen comparison - without a clash:
  restored  C major: a reed organ (the classroom has one) plays the chords and a plain school-song melody (C D E G A only), a piano
            doubles it softly, a light bass on beats 1 and 3.  Warm, a spring morning.
  ruin      the relative minor chords under the same bars (C -> Am, G -> Em, F -> Dm): only fragments of the same melody are left, on an
            out-of-tune piano an octave up and a music-box tone, late and soft, with a long room; a low string drone and wind.
Each file = the loop + a ringing tail; the next pass starts exactly one loop later, so the tail sounds under the start of the next pass."""
import os, json, subprocess, wave, numpy as np
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public"); SR = 44100; TAIL = 5.0; BPM = 72.0; BEAT = 60.0 / BPM; BAR = 4 * BEAT; NBAR = 16; LOOP = NBAR * BAR
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
rng = np.random.default_rng(31)
def _filt(x, fc, high=False, order=2):
    """zero-phase Butterworth-shaped filter in the frequency domain (numpy only)"""
    n = len(x); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR); r = (f / fc) ** (2 * order)
    return np.fft.irfft(X * (np.sqrt(r / (1 + r)) if high else 1.0 / np.sqrt(1 + r)), n)
lp = lambda x, fc: _filt(x, fc); hp = lambda x, fc: _filt(x, fc, True)
def conv(x, ir):
    n = len(x) + len(ir) - 1; m = 1 << (n - 1).bit_length(); return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:n]
T = lambda d: np.arange(int(d * SR)) / SR

def piano(m, d=3.0, vel=0.6, detune=0.0012, drift=0.0):
    """felt piano; detune = the two strings apart (0.0012 in tune, 0.008 an old upright), drift = slow sag of the pitch"""
    t = T(d); f = hz(m); s = np.zeros(len(t)); B = 0.00035; dark = 1.25 + (1 - vel) * 0.9; kmax = int(min(14, (SR * 0.45) / f)); sag = 1.0 - drift * (1 - np.exp(-t * 1.2))
    for k in range(1, kmax + 1):
        fk = f * k * np.sqrt(1 + B * k * k); dec = (0.55 + 0.32 * k) * (1 + (m - 60) / 40.0); env = 0.65 * np.exp(-t * dec * 2.6) + 0.35 * np.exp(-t * dec * 0.55)
        ph = 2 * np.pi * fk * np.cumsum(sag) / SR
        s += (1.0 / k ** dark) * (0.3 if k == 7 else 1.0) * env * (np.sin(ph) + np.sin(ph * (1 + detune) + 0.7)) * 0.5
    s += 0.10 * vel * lp(rng.standard_normal(len(t)), 900) * np.exp(-t * 60)
    return s * (1 - np.exp(-t * 700)) * np.minimum(1, (d - t) / 0.08) * vel
def organ(ms, d, bright=1700):
    """reed organ: two reeds a few cents apart per note, a slow breath of the bellows, soft attack and release"""
    t = T(d); s = np.zeros(len(t)); trem = 1 + 0.05 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.6, 0, 1)
    for m in ms:
        for det in (-0.035, 0.04):
            ph = (hz(m + det) * t) % 1.0; s += (2 * ph - 1) * 0.7 + np.sign(np.sin(2 * np.pi * ph)) * 0.18
    return lp(s, bright) * trem * np.minimum(1, t / 0.09) * np.minimum(1, (d - t) / 0.16) / (2 * max(1, len(ms)))
def strings(ms, d, bright=700, att=2.0):
    t = T(d); s = np.zeros(len(t))
    for m in ms:
        for det in (-0.09, -0.03, 0.04, 0.10):
            f = hz(m + det) * (1 + 0.003 * np.sin(2 * np.pi * (4.6 + det) * t)); s += 2 * ((np.cumsum(f) / SR) % 1) - 1
    return lp(s, bright) * np.minimum(1, t / att) ** 1.5 * np.minimum(1, (d - t) / 1.6) / (4 * len(ms))
def musicbox(m, d=4.0):
    t = T(d); f = hz(m)
    return sum(np.sin(2 * np.pi * f * r * t) * np.exp(-t * dd) * a for r, dd, a in ((1, 1.3, 1.0), (2.76, 2.6, 0.30), (5.4, 4.5, 0.10))) * (1 - np.exp(-t * 400))
def sub(m, d):
    t = T(d); f = hz(m); return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.minimum(1, t / 0.03) * np.exp(-t * 1.6) * np.minimum(1, (d - t) / 0.2)
def wind(d):
    """a draught through broken windows: band-limited noise, swelling and falling slowly"""
    t = T(d); n = hp(lp(rng.standard_normal(len(t)), 620), 170); sw = 0.5 + 0.5 * np.sin(2 * np.pi * t / 13.3 + 1.0) * np.sin(2 * np.pi * t / 8.9 + 0.3)
    return n * (0.25 + 0.75 * np.clip(sw, 0, 1) ** 1.5)

# ---- the tune (shared).  chords per bar: (bass, tones); melody: (beat, midi, beats)
C4, D4, E4, F4, G4, A4, B4 = 60, 62, 64, 65, 67, 69, 71
MAJ = [("C", 36, [C4, E4, G4]), ("G/B", 35, [D4, G4, B4 - 12]), ("Am", 33, [C4, E4, A4 - 12]), ("F", 29, [C4, F4, A4 - 12]), ("C/E", 28, [C4, E4, G4]), ("F", 29, [C4, F4, A4]), ("G", 31, [D4, G4, B4 - 12]), ("C", 36, [C4, E4, G4]),
       ("C", 36, [C4, E4, G4]), ("G/B", 35, [D4, G4, B4 - 12]), ("Am", 33, [C4, E4, A4 - 12]), ("F", 29, [C4, F4, A4 - 12]), ("Dm", 38, [D4, F4, A4]), ("G", 31, [D4, G4, B4 - 12]), ("C", 36, [C4, E4, G4]), ("C", 36, [C4, E4, G4])]
MIN = [("Am", 33, [A4 - 12, E4]), ("Em", 28, [G4 - 12, E4]), ("Am", 33, [A4 - 12, E4]), ("F", 29, [A4 - 12, F4]), ("Am", 33, [A4 - 12, E4]), ("Dm", 26, [A4 - 12, D4]), ("Em", 28, [G4 - 12, E4]), ("Am", 33, [A4 - 12, E4]),
       ("Am", 33, [A4 - 12, E4]), ("Em", 28, [G4 - 12, E4]), ("Am", 33, [A4 - 12, E4]), ("F", 29, [A4 - 12, F4]), ("Dm", 26, [A4 - 12, D4]), ("Em", 28, [G4 - 12, E4]), ("Am", 33, [A4 - 12, E4]), ("Am", 33, [A4 - 12, E4])]
_bars = [[(E4, 1), (G4, 1), (A4, 1), (G4, 1)], [(D4, 1.5), (E4, .5), (D4, 2)], [(C4, 1), (E4, 1), (A4, 2)], [(A4, 1), (C4 + 12, 1), (A4, 2)],
         [(G4, 1), (E4, 1), (G4, 1), (C4 + 12, 1)], [(A4, 2), (C4 + 12, 1), (A4, 1)], [(G4, 1), (A4, 1), (D4 + 12, 2)], [(C4 + 12, 3), (None, 1)],
         [(E4 + 12, 1), (D4 + 12, 1), (C4 + 12, 1), (G4, 1)], [(D4 + 12, 1.5), (E4 + 12, .5), (D4 + 12, 2)], [(C4 + 12, 1), (A4, 1), (E4 + 12, 2)], [(C4 + 12, 1), (A4, 1), (C4 + 12, 2)],
         [(D4 + 12, 1), (A4, 1), (D4 + 12, 1), (E4 + 12, 1)], [(D4 + 12, 2), (G4, 2)], [(E4, 1), (G4, 1), (C4 + 12, 2)], [(C4 + 12, 3), (None, 1)]]
MEL = []
for b, notes in enumerate(_bars):
    o = b * 4.0
    for m, d in notes:
        if m is not None: MEL.append((o, m, d))
        o += d
# what the ruin still remembers of it: the long notes and the first note of some bars (index into MEL), played late
KEEP = [i for i, (o, m, d) in enumerate(MEL) if d >= 2 or (o % 4 == 0 and int(o // 4) in (0, 2, 4, 8, 10, 12, 14))]

def render(name, part="all"):
    """part: 'all', or 'bed' / 'mel' alone (to measure the balance of the tune against what lies under it)"""
    N = int((LOOP + TAIL) * SR); L = np.zeros(N); R = np.zeros(N); wL = np.zeros(N); wR = np.zeros(N)
    def add(sig, t, g=1.0, pan=0.0, wet=0.3):
        i = int(t * SR)
        if i >= N or i < 0 or (part != "all" and part != PART[0]): return
        n = min(len(sig), N - i); gl = g * np.cos((pan + 1) * np.pi / 4); gr = g * np.sin((pan + 1) * np.pi / 4)
        L[i:i + n] += sig[:n] * gl; R[i:i + n] += sig[:n] * gr; wL[i:i + n] += sig[:n] * gl * wet; wR[i:i + n] += sig[:n] * gr * wet
    jit = lambda a=0.006: rng.uniform(-a, a); PART = ["bed"]
    if name == "restored":
        for b, (_, bass, ch) in enumerate(MAJ):
            t0 = b * BAR
            add(organ(ch, BAR - 0.05, 1500), t0, 0.50, -0.2, 0.35)                                   # chords, held for the bar
            add(sub(bass + 12, BEAT * 1.8), t0, 0.30, 0.0, 0.05); add(sub(bass + 12 + (7 if b % 2 else 0), BEAT * 1.6), t0 + 2 * BEAT, 0.20, 0.0, 0.05)
            for e, k in enumerate((0, 1, 2, 1)): add(piano(ch[k] + 12, 2.2, 0.30), t0 + (e + 0.5) * BEAT + jit(), 0.30, 0.25, 0.4)      # off-beat broken chord, quiet
        PART[0] = "mel"
        for o, m, d in MEL:
            add(organ([m + 12], d * BEAT - 0.04, 2300), o * BEAT, 0.62, 0.1, 0.4)                       # the tune on the organ's upper rank
            add(piano(m + 12, max(d * BEAT + 1.0, 1.8), 0.5), o * BEAT + jit(), 0.42, -0.1, 0.45)
        rt, wetg = 2.2, 0.030
    else:
        w = wind(LOOP + TAIL); add(w, 0.0, 0.060, -0.3, 0.2); add(np.roll(w, SR * 3), 0.0, 0.060, 0.3, 0.2)
        for b, (_, bass, ch) in enumerate(MIN):
            t0 = b * BAR
            pad = strings([bass + 12, bass + 19] + ([ch[1]] if b % 4 == 3 else []), BAR + 2.4, 620, 2.2); add(pad, t0, 0.17, -0.15, 0.6); add(np.roll(pad, 260), t0, 0.17, 0.15, 0.6)      # (0.30 buried the tune: bed 2 dB over it)
            if b % 2 == 0: add(piano(bass + 12, 6.0, 0.40, 0.006, 0.004), t0 + jit(0.02), 0.55, -0.1, 0.7)       # a low note of the old upright, every other bar
        PART[0] = "mel"
        for i in KEEP:
            o, m, d = MEL[i]; late = 0.10 + rng.uniform(0, 0.12)
            add(piano(m + 12, max(d * BEAT + 3.0, 4.5), 0.42, 0.008, 0.006), o * BEAT + late, 0.62, 0.15, 0.85)  # out of tune, sagging, late
            if d >= 2: add(musicbox(m + 24, 4.5), o * BEAT + late + BEAT * 0.5, 0.050, -0.35, 1.0)
        rt, wetg = 1.1, 0.060
    t = T(4.2); ir = rng.standard_normal((2, len(t))) * np.exp(-t * rt); ir[:, :int(0.015 * SR)] = 0
    L += lp(conv(wL, ir[0])[:N], 4500) * wetg; R += lp(conv(wR, ir[1])[:N], 4500) * wetg
    M = np.stack([hp(L, 30), hp(R, 30)], 1)
    env = np.ones(N); e0 = int(LOOP * SR); env[e0:] = np.linspace(1, 0, N - e0) ** 1.5            # after the loop point only the tail rings on
    M *= env[:, None]
    if part != "all": return M                                                                  # raw level, for the balance check
    M = np.tanh(M / np.percentile(np.abs(M), 99.8)) * 0.80
    return M

def stats(name, M):
    mono = M.mean(1); n = int(LOOP * SR); sec = np.sqrt((mono[:n // SR * SR].reshape(-1, SR) ** 2).mean(1))
    X = np.abs(np.fft.rfft(mono[:n])) ** 2; f = np.fft.rfftfreq(n, 1.0 / SR); tot = X.sum()
    bands = {k: round(float(X[(f >= a) & (f < b)].sum() / tot), 3) for k, (a, b) in dict(sub=(20, 120), low=(120, 400), mid=(400, 2000), high=(2000, 8000), air=(8000, 20000)).items()}
    return dict(name=name, seconds=round(len(M) / SR, 2), rms=round(float(np.sqrt((M ** 2).mean())), 3), peak=round(float(np.abs(M).max()), 3), dc=round(float(mono.mean()), 5),
                quietest_second=round(float(sec.min()), 4), loudest_second=round(float(sec.max()), 3), bands=bands, lr_corr=round(float(np.corrcoef(M[:n, 0], M[:n, 1])[0, 1]), 3))

def balance():
    """python make_bgm.py balance: level of the tune against the bed, per track (rms over the loop, and the tune's level while it sounds)"""
    for name in ("restored", "ruin"):
        st = rng.bit_generator.state; b = render(name, "bed").mean(1); rng.bit_generator.state = st; m = render(name, "mel").mean(1); n = int(LOOP * SR)
        act = np.abs(m[:n]) > 0.02 * np.abs(m[:n]).max(); rb = float(np.sqrt((b[:n] ** 2).mean())); rm = float(np.sqrt((m[:n] ** 2).mean())); rma = float(np.sqrt((m[:n][act] ** 2).mean()))
        print("%-9s bed rms %.3f  tune rms %.3f (%.1f dB vs bed)  tune while sounding %.3f (%.1f dB)  tune sounds %.0f %% of the time" % (name, rb, rm, 20 * np.log10(rm / rb), rma, 20 * np.log10(rma / rb), 100 * act.mean()))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "balance": balance(); sys.exit()
    os.makedirs(OUT, exist_ok=True); S = {}
    for name in ("restored", "ruin"):
        M = render(name); S[name] = M
        wav = os.path.join(OUT, "_bgm_%s.wav" % name); w = wave.open(wav, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((M * 32767).astype("<i2").tobytes()); w.close()
        out = os.path.join(OUT, "bgm_%s.m4a" % name)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True); os.remove(wav)
        print(json.dumps(stats(name, M)), os.path.getsize(out) // 1024, "kB")
    mix = (S["restored"] + S["ruin"]) * 0.7071                                                    # the split-screen comparison at the middle: both at -3 dB
    print("mix at the middle: peak %.3f rms %.3f" % (float(np.abs(mix).max()), float(np.sqrt((mix ** 2).mean()))))
    json.dump({"loop": round(LOOP, 4), "bpm": BPM, "bars": NBAR, "tracks": ["ruin", "restored"]}, open(os.path.join(OUT, "bgm.json"), "w"))
    print("loop %.4f s, melody notes %d, kept in the ruin %d" % (LOOP, len(MEL), len(KEEP)))

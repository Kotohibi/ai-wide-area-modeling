r"""Check a rendered frame sequence (Blender or Unreal) before editing it into a video:
missing numbers, frames that are almost one flat colour (the camera is inside a wall, a door leaf, the ground),
sudden jumps between neighbours (a pop, a wrong cut), and a contact sheet to look at.

  python frames_check.py <dir> [--pattern f_%04d] [--range 1 1459] [--sheet sheet.jpg] [--rename]
--rename: .jpeg -> .jpg first (Movie Render Queue writes .jpeg).  Needs numpy and Pillow."""
import sys, os, numpy as np
from PIL import Image, ImageDraw
a = sys.argv[1:]
if not a: sys.exit(__doc__)
def opt(name, n, default):
    if name in a:
        i = a.index(name); v = a[i + 1:i + 1 + n]; del a[i:i + 1 + n]; return v
    return default
pat = opt("--pattern", 1, ["f_%04d"])[0]; rng = opt("--range", 2, None); sheet = opt("--sheet", 1, [None])[0]; ren = "--rename" in a
if ren: a.remove("--rename")
d = a[0]
if ren:
    for f in os.listdir(d):
        if f.lower().endswith(".jpeg"): os.replace(os.path.join(d, f), os.path.join(d, f[:-5] + ".jpg"))
def path(i):
    for ext in (".jpg", ".jpeg", ".png"):
        p = os.path.join(d, pat % i + ext)
        if os.path.exists(p): return p
if rng: s, e = int(rng[0]), int(rng[1])
else:
    have = [i for i in range(0, 100000) if path(i)]
    if not have: sys.exit("no frames match %s in %s" % (pat, d))
    s, e = have[0], have[-1]
miss = [i for i in range(s, e + 1) if not path(i)]; print("frames %d..%d: %d present, missing %s" % (s, e, e - s + 1 - len(miss), miss[:30]))
prev = None; flat = []; jump = []
for i in range(s, e + 1):
    p = path(i)
    if not p: continue
    g = np.asarray(Image.open(p).convert("L").resize((64, 36)), np.float32); sd = float(g.std())
    if sd < 9: flat.append((i, round(sd, 1)))
    if prev is not None:
        df = float(np.abs(g - prev).mean())
        if df > 38: jump.append((i, round(df, 1)))
    prev = g
print("flat frames (grey std < 9):", flat); print("jumps (mean difference to the previous frame > 38):", jump)
if sheet:
    ok = [i for i in range(s, e + 1) if path(i)]; pick = [ok[int(round(k * (len(ok) - 1) / 15))] for k in range(16)]; im = Image.new("RGB", (4 * 480, 4 * 270))
    for k, i in enumerate(pick):
        t = Image.open(path(i)).convert("RGB").resize((480, 270)); ImageDraw.Draw(t).text((6, 4), str(i), fill=(255, 255, 0)); im.paste(t, ((k % 4) * 480, (k // 4) * 270))
    im.save(sheet, quality=85); print("sheet", sheet)

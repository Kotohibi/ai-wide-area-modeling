r"""Review a comparison set (cmp_set.py + blender/bl_cmp_render.py): sheets, full-resolution crops, tone patches, versions.

usage: python cmp_review.py <dir> sheets [--tile 400]
           -> _overview_XX.jpg  (photo | blender | overlay: render outline in red on the darkened photo; 6 views per sheet)
           -> _before_after_XX.jpg  (photo | previous version | current) when a _v* folder exists (latest one is used)
       python cmp_review.py <dir> keep [tag]           copy the current *_blender.png to <dir>/_<tag>/ (default: next free v1, v2, ...)
       python cmp_review.py <dir> crop <out.jpg> <stem> x0 y0 x1 y1 [<stem> x0 y0 x1 y1 ...]
           photo | blender side by side at full resolution with pixel ticks every 100 px (read pixels for bl_cmp_probe / pick3d)
       python cmp_review.py <dir> patch <stem> x0 y0 x1 y1 [label] [<stem> x0 y0 x1 y1 label ...]
           mean RGB (0-255) of the same box in the photo, the render and the previous version: calibrate light and materials with numbers
Reading order: overlay first (geometry: red lines off the photo edges = position or size error, red lines on empty photo = extra object,
photo object without red = missing), then before/after, then crops and probes for each difference, then patches for tone.
"""
import os, sys, json, glob, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

D = sys.argv[1]; cmd = sys.argv[2]; args = sys.argv[3:]
cams = json.load(open(os.path.join(D, "cameras.json"), encoding="utf-8"))
def photo_path(stem):
    c = [c for c in cams if c["stem"] == stem][0]; return os.path.join(D, c.get("photo_file", stem + "_photo.png"))
def versions(): return sorted([p for p in glob.glob(os.path.join(D, "_v*")) if os.path.isdir(p)], key=lambda p: int(p.rsplit("_v", 1)[1]) if p.rsplit("_v", 1)[1].isdigit() else 0)
def label(im, t):
    d = ImageDraw.Draw(im); d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0)); d.text((4, 3), t, fill=(255, 255, 0)); return im
def edges(im):
    g = im.convert("L").filter(ImageFilter.GaussianBlur(1.5)).filter(ImageFilter.FIND_EDGES); a = np.asarray(g, float)
    m = a > max(18.0, np.percentile(a, 92)); return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0

if cmd == "sheets":
    T = int(args[args.index("--tile") + 1]) if "--tile" in args else 400
    vs = versions(); prev = vs[-1] if vs else None; rows, ba = [], []
    for c in cams:
        st = c["stem"]; bp = os.path.join(D, st + "_blender.png")
        if not os.path.exists(bp): continue
        ph = Image.open(photo_path(st)).convert("RGB"); bl = Image.open(bp).convert("RGB")
        e = edges(bl); ov = (np.asarray(ph, float) * .6).astype(np.uint8); ov[e] = (255, 0, 0); ov = Image.fromarray(ov)
        t = [x.resize((T, T * ph.height // ph.width)) for x in (ph, bl, ov)]
        for im, s in zip(t, ("photo", "blender", "overlay")): label(im, "%s  %s" % (st, s))
        rows.append(t)
        if prev and os.path.exists(os.path.join(prev, st + "_blender.png")):
            pv = Image.open(os.path.join(prev, st + "_blender.png")).convert("RGB"); t2 = [x.resize((T, T * ph.height // ph.width)) for x in (ph, pv, bl)]
            for im, s in zip(t2, ("photo", os.path.basename(prev)[1:], "current")): label(im, "%s  %s" % (st, s))
            ba.append(t2)
    for name, R in (("_overview", rows), ("_before_after", ba)):
        for i in range(0, len(R), 6):
            ch = R[i:i + 6]; H = sum(r[0].height for r in ch); S = Image.new("RGB", (3 * T, H)); y = 0
            for r in ch:
                for k, im in enumerate(r): S.paste(im, (k * T, y))
                y += r[0].height
            S.save(os.path.join(D, "%s_%02d.jpg" % (name, i // 6)), quality=88)
    print("sheets:", len(rows), "views", ("before/after vs " + os.path.basename(prev)) if prev and ba else "")
elif cmd == "keep":
    vs = versions(); tag = args[0] if args else "v%d" % (len(vs) + 1); od = os.path.join(D, "_" + tag); os.makedirs(od, exist_ok=True)
    n = 0
    for p in glob.glob(os.path.join(D, "*_blender.png")): shutil.copy2(p, od); n += 1
    print("kept", n, "renders in", od)
elif cmd == "crop":
    out = args[0]; rows = []
    for i in range(1, len(args), 5):
        st = args[i]; x0, y0, x1, y1 = [int(v) for v in args[i + 1:i + 5]]; pair = []
        for p, s in ((photo_path(st), "photo"), (os.path.join(D, st + "_blender.png"), "blender")):
            im = Image.open(p).convert("RGB").crop((x0, y0, x1, y1)); d = ImageDraw.Draw(im)
            for x in range((x0 // 100 + 1) * 100, x1, 100): d.line([(x - x0, 0), (x - x0, 10)], fill=(255, 255, 0)); d.text((x - x0 + 2, 10), str(x), fill=(255, 255, 0))
            for y in range((y0 // 100 + 1) * 100, y1, 100): d.line([(0, y - y0), (10, y - y0)], fill=(255, 255, 0)); d.text((12, y - y0 - 5), str(y), fill=(255, 255, 0))
            d.text((6, im.height - 14), "%s %s" % (st, s), fill=(255, 255, 0)); pair.append(im)
        rows.append(pair)
    W = max(r[0].width for r in rows) * 2; H = sum(r[0].height for r in rows); S = Image.new("RGB", (W, H)); y = 0
    for a_, b_ in rows: S.paste(a_, (0, y)); S.paste(b_, (a_.width, y)); y += a_.height
    S.save(out, quality=88); print(out)
elif cmd == "patch":
    vs = versions(); prev = vs[-1] if vs else None; i = 0
    while i < len(args):
        st = args[i]; x0, y0, x1, y1 = [int(v) for v in args[i + 1:i + 5]]; i += 5; lab = ""
        if i < len(args) and not any(c["stem"] == args[i] for c in cams): lab = args[i]; i += 1
        m = lambda p: np.asarray(Image.open(p).convert("RGB").crop((x0, y0, x1, y1)), float).reshape(-1, 3).mean(0).round().astype(int).tolist()
        line = "%-24s %-14s photo %s  blender %s" % (st, lab, m(photo_path(st)), m(os.path.join(D, st + "_blender.png")))
        if prev and os.path.exists(os.path.join(prev, st + "_blender.png")): line += "  %s %s" % (os.path.basename(prev)[1:], m(os.path.join(prev, st + "_blender.png")))
        print(line)

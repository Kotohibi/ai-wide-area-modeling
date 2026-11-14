import sys, numpy as np
from PIL import Image, ImageDraw
SP, view, s_lo, s_hi, step, cols, tile, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7]), sys.argv[8]
rows = [l.strip().split(",") for l in open(SP + r"\cams.csv", encoding="utf-8-sig") if l.strip()]
front = [r[4] for r in rows if r[4].endswith("_front.png")]
d = np.load(SP + r"\traj_site.npy")[:, 3]
ss = np.arange(s_lo, s_hi, step)
tiles = []
for s in ss:
    i = min(int(np.searchsorted(d, s)), len(front) - 1)
    name = front[i].replace("_front.png", f"_{view}.png")
    im = Image.open(__import__("os").path.join(__import__("os").environ.get("SFM_DIR", "."), "images") + "\\" + name).convert("RGB").resize((tile, tile))
    ImageDraw.Draw(im).text((6, 6), f"s={int(s)} {view}", fill=(255, 255, 0))
    tiles.append(im)
n = len(tiles); r = (n + cols - 1) // cols
sheet = Image.new("RGB", (cols * tile, r * tile))
for k, im in enumerate(tiles): sheet.paste(im, ((k % cols) * tile, (k // cols) * tile))
sheet.save(out); print(sheet.size, n)

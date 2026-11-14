# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import sys, json
from PIL import Image, ImageDraw
import os; SH = os.environ.get("BLENDER_SHARED", "")
view = sys.argv[1]; out = sys.argv[2]; tile = int(sys.argv[3]) if len(sys.argv) > 3 else 400
poses = [o for o in json.load(open(SH + r"\poses_level.json")) if o["view"] == view]
pairs = []
for o in poses:
    ph = Image.open(__import__("os").path.join(__import__("os").environ.get("SFM_DIR", "."), "images") + "\\" + o["name"]).convert("RGB").resize((tile, tile))
    try: bl = Image.open(SH + "\\cmp_" + o["name"].replace(".png", "") + ".png").convert("RGB").resize((tile, tile))
    except Exception: bl = Image.new("RGB", (tile, tile), (60, 0, 0))
    ImageDraw.Draw(ph).text((6, 6), f"photo s={int(o['s'])}", fill=(255, 255, 0))
    ImageDraw.Draw(bl).text((6, 6), "model", fill=(255, 255, 0))
    pairs.append((ph, bl))
cols = 2
rows = (len(pairs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 2 * tile, rows * tile))
for k, (a, b) in enumerate(pairs):
    x = (k % cols) * 2 * tile; y = (k // cols) * tile
    sheet.paste(a, (x, y)); sheet.paste(b, (x + tile, y))
sheet.save(out); print(sheet.size)

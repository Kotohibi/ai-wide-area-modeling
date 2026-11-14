# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
r"""Photo | LFS 3DGS (same training camera) | Blender model, one row per pose.

usage: python cmp3_sheet.py <scratch_dir> <out.png> <tile> name1.png name2.png ...
Needs: SFM_DIR\images\<name> (photo), <scratch_dir>\lfs_<name> (lfs_capture_dataset.ps1),
       $BLENDER_SHARED\cmp_<stem>.png (cmp_render.py).
"""
import sys, os
from PIL import Image, ImageDraw
SP, OUT, T = sys.argv[1], sys.argv[2], int(sys.argv[3]); names = sys.argv[4:]
SH = os.environ.get("BLENDER_SHARED", ""); SFM = os.environ.get("SFM_DIR", ".")
rows = []
for n in names:
    ims = []
    for path, lab in ((SFM + r"\images" + "\\" + n, "photo " + n[-22:-4]), (SP + "\\lfs_" + n, "LFS 3DGS"), (SH + "\\cmp_" + n.replace(".png", "") + ".png", "Blender")):
        try: im = Image.open(path).convert("RGB").resize((T, T))
        except Exception: im = Image.new("RGB", (T, T), (60, 0, 0))
        ImageDraw.Draw(im).text((6, 6), lab, fill=(255, 255, 0)); ims.append(im)
    rows.append(ims)
sheet = Image.new("RGB", (3 * T, len(rows) * T))
for r, ims in enumerate(rows):
    for c, im in enumerate(ims): sheet.paste(im, (c * T, r * T))
sheet.save(OUT); print(sheet.size)

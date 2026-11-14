r"""Fix the comparison set: copy each chosen photo unchanged and write its exact pose and intrinsics for Blender.

usage: python cmp_set.py <project.json> <chosen.json> <out_dir>
  chosen.json: [{"key": "P2_sign", "image": "frame_00066_left.png", "note": "..."}, ...]
out_dir: NN_<key>_photo.<ext> (the training photo, untouched) and cameras.json (stem, key, note, source_image, loc, rot, fx, fy, cx, cy, w, h).
blender/bl_cmp_render.py writes NN_<key>_blender.png next to each photo, at the same size.
"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project
P = Project(sys.argv[1]); chosen = json.load(open(sys.argv[2], encoding="utf-8")); out = sys.argv[3]; os.makedirs(out, exist_ok=True)
cams = []
for i, c in enumerate(chosen, 1):
    cam = P.camera(c["image"]); stem = "%02d_%s" % (i, c["key"]); ext = os.path.splitext(c["image"])[1]
    shutil.copy2(P.photo_path(c["image"]), os.path.join(out, stem + "_photo" + ext))
    cam.update(stem=stem, key=c["key"], note=c.get("note", ""), source_image=c["image"], photo_file=stem + "_photo" + ext); cams.append(cam)
    print(stem, c["image"], [round(v, 2) for v in cam["loc"]], "f %.1f  %dx%d" % (cam["fx"], cam["w"], cam["h"]))
json.dump(cams, open(os.path.join(out, "cameras.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

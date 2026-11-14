r"""Blender: render the comparison set written by cmp_set.py with the photo's exact pose and intrinsics, final materials and light.

    CMPCFG = {"dir": r"...\compare", "only": ["01_P2_sign"] or None, "spp": 128, "hide": ["Anim", "FX"], "frame": 1}
    p = SH + r"\bl_cmp_render.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
Writes <dir>\NN_<key>_blender.png (RGB, same size as the photo). Collections in "hide" (animated vehicles, effects, helpers) are excluded
during the render; camera, resolution, samples, motion blur and frame are restored afterwards.
A 1920x1920 Cycles render at 128 spp takes about 10 s on one RTX 3090: keep each MCP call to 4 views or fewer, or the call times out
(Blender then finishes anyway; check the file times before rendering again).
"""
import bpy, json, os
from mathutils import Matrix, Vector
cfg = globals().get("CMPCFG", {}); D_ = cfg["dir"]
cams = json.load(open(os.path.join(D_, "cameras.json"), encoding="utf-8"))
if cfg.get("only"): cams = [c for c in cams if c["stem"] in cfg["only"]]
sc = bpy.context.scene; r = sc.render
keep = dict(cam=sc.camera, rx=r.resolution_x, ry=r.resolution_y, pct=r.resolution_percentage, fp=r.filepath, fmt=r.image_settings.file_format,
            cm=r.image_settings.color_mode, mb=r.use_motion_blur, spp=sc.cycles.samples, frame=sc.frame_current, film=r.film_transparent, eng=r.engine)
hidden = []
for n in cfg.get("hide", ["Anim", "FX", "RefViews", "Diff"]):
    lc = bpy.context.view_layer.layer_collection.children.get(n)
    if lc and not lc.exclude: lc.exclude = True; hidden.append(n)
cd = bpy.data.cameras.get("_CmpCam") or bpy.data.cameras.new("_CmpCam")
ob = bpy.data.objects.get("_CmpCam") or bpy.data.objects.new("_CmpCam", cd)
if ob.name not in sc.collection.objects: sc.collection.objects.link(ob)
sc.camera = ob; sc.frame_set(int(cfg.get("frame", 1)))
r.engine = cfg.get("engine", "CYCLES")
if r.engine == "CYCLES":
    sc.cycles.samples = int(cfg.get("spp", 128)); sc.cycles.use_denoising = True
r.use_motion_blur = False; r.film_transparent = False; r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.color_depth = '8'
done = []
try:
    for c in cams:
        w, h = c["w"], c["h"]; m = max(w, h)
        cd.sensor_fit = 'HORIZONTAL' if w >= h else 'VERTICAL'; cd.sensor_width = cd.sensor_height = 36.0
        cd.lens = c["fx"] * 36.0 / w if w >= h else c["fy"] * 36.0 / h
        cd.shift_x = -(c["cx"] - w / 2) / m; cd.shift_y = (c["cy"] - h / 2) / m; cd.clip_start = .05; cd.clip_end = 10000
        M = Matrix(c["rot"]).to_4x4(); M.translation = Vector(c["loc"]); ob.matrix_world = M
        r.resolution_x, r.resolution_y = w, h
        r.filepath = os.path.join(D_, c["stem"] + "_blender.png")
        bpy.ops.render.render(write_still=True); done.append(c["stem"])
finally:
    sc.camera = keep["cam"]; r.resolution_x, r.resolution_y, r.resolution_percentage = keep["rx"], keep["ry"], keep["pct"]; r.filepath = keep["fp"]
    r.image_settings.file_format = keep["fmt"]; r.image_settings.color_mode = keep["cm"]; r.use_motion_blur = keep["mb"]; sc.cycles.samples = keep["spp"]
    r.film_transparent = keep["film"]; r.engine = keep["eng"]; sc.frame_set(keep["frame"])
    for n in hidden: bpy.context.view_layer.layer_collection.children[n].exclude = False
    bpy.data.objects.remove(ob); bpy.data.cameras.remove(cd)
result = {"rendered": done}

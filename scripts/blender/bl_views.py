r"""Blender side of views.py: render the model from training-photo poses, or create those cameras for inspection.

Run inside Blender (execute_blender_code):
    import os; os.environ["BLENDER_SHARED"] = SH = r"<shared folder>"
    VIEWCFG = {"set": "check1", "mode": "render", "width": 640}          # or "mode": "create"
    p = SH + r"\bl_views.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())

VIEWCFG keys
  set        name of <shared>\views\<set>.json written by `views.py select` / `views.py viewport`
  names      optional subset of image names
  mode       "render": write <shared>\views\<set>\bl_<stem>.png (RGBA, transparent background = no geometry) and
                       restore the scene's camera / resolution / engine afterwards
             "create": add one camera per view to collection "RefViews" (photo as camera background image when
                       the photo is readable from Blender) so you can look through it (Numpad 0) and compare by eye
  width      output width in pixels (height follows the photo's aspect)
  color_type Workbench colour mode, default "MATERIAL" ("TEXTURE" for image-textured models, "OBJECT", "RANDOM")
  hide       collections to exclude during the render (default ["Diff", "RefViews"]: diff points, helper cameras)
The camera uses the photo's intrinsics (fx, cx, cy -> lens, shift), so pixels line up with the photo and with the
LichtFeld render of the same training camera.
"""
import bpy, json, os, math
from mathutils import Matrix, Vector

SH = os.environ.get("BLENDER_SHARED", "")
cfg = globals().get("VIEWCFG", {})
cams = json.load(open(os.path.join(SH, "views", cfg["set"] + ".json"), encoding="utf-8"))
if cfg.get("names"): cams = [c for c in cams if c["name"] in cfg["names"]]
W = int(cfg.get("width", 640)); mode = cfg.get("mode", "render")
sc = bpy.context.scene

def fit_camera(cd, c):
    w, h = c["w"], c["h"]; m = max(w, h)
    cd.sensor_width = cd.sensor_height = 36.0; cd.clip_start = 0.05; cd.clip_end = 5000
    if c.get("fx"):
        if w >= h: cd.sensor_fit = 'HORIZONTAL'; cd.lens = c["fx"] * 36.0 / w
        else: cd.sensor_fit = 'VERTICAL'; cd.lens = c["fy"] * 36.0 / h
        cd.shift_x = -(c["cx"] - w / 2) / m; cd.shift_y = (c["cy"] - h / 2) / m
    else:                                                    # LichtFeld viewport: vertical FOV only
        cd.sensor_fit = 'VERTICAL'; cd.lens = 18.0 / math.tan(math.radians(c["fov_v_deg"]) / 2); cd.shift_x = cd.shift_y = 0
    return W, max(1, round(h * W / w))

def pose(c):
    M = Matrix(c["rot"]).to_4x4(); M.translation = Vector(c["loc"]); return M

done = []
if mode == "create":
    col = bpy.data.collections.get("RefViews") or bpy.data.collections.new("RefViews")
    if col.name not in sc.collection.children: sc.collection.children.link(col)
    for c in cams:
        stem = os.path.splitext(c["name"])[0]; nm = "View_" + stem[-56:]          # Blender names max 63 chars
        cd = bpy.data.cameras.get(nm) or bpy.data.cameras.new(nm); fit_camera(cd, c)
        ob = bpy.data.objects.get(nm) or bpy.data.objects.new(nm, cd)
        if ob.name not in col.objects: col.objects.link(ob)
        ob.matrix_world = pose(c); ob["photo"] = c.get("photo", ""); ob["res"] = [c["w"], c["h"]]
        ph = c.get("photo_shared") or c.get("photo")
        if ph and os.path.exists(ph):
            img = bpy.data.images.load(ph, check_existing=True)
            cd.show_background_images = True
            bg = cd.background_images[0] if cd.background_images else cd.background_images.new()
            bg.image = img; bg.alpha = 0.5; bg.display_depth = 'FRONT'; bg.frame_method = 'STRETCH'
        done.append(nm)
    result = {"created": done, "hint": "select a View_* camera, set it active (Ctrl+Numpad0); resolution = photo aspect (see custom prop res)"}
else:
    keep = dict(cam=sc.camera, rx=sc.render.resolution_x, ry=sc.render.resolution_y, pct=sc.render.resolution_percentage,
                eng=sc.render.engine, film=sc.render.film_transparent, ct=sc.display.shading.color_type, fp=sc.render.filepath)
    hidden = []
    for n in cfg.get("hide", ["Diff", "RefViews"]):
        lc = bpy.context.view_layer.layer_collection.children.get(n)
        if lc and not lc.exclude: lc.exclude = True; hidden.append(n)
    cd = bpy.data.cameras.get("_ViewCam") or bpy.data.cameras.new("_ViewCam")
    ob = bpy.data.objects.get("_ViewCam") or bpy.data.objects.new("_ViewCam", cd)
    if ob.name not in sc.collection.objects: sc.collection.objects.link(ob)
    sc.camera = ob; sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = cfg.get("color_type", "MATERIAL")
    od = os.path.join(SH, "views", cfg["set"]); os.makedirs(od, exist_ok=True)
    try:
        for c in cams:
            rx, ry = fit_camera(cd, c); ob.matrix_world = pose(c)
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
            sc.render.filepath = os.path.join(od, "bl_" + os.path.splitext(c["name"])[0] + ".png")
            bpy.ops.render.render(write_still=True); done.append(c["name"])
    finally:
        sc.camera = keep["cam"]; sc.render.resolution_x, sc.render.resolution_y = keep["rx"], keep["ry"]
        sc.render.resolution_percentage = keep["pct"]; sc.render.engine = keep["eng"]; sc.render.film_transparent = keep["film"]
        sc.display.shading.color_type = keep["ct"]; sc.render.filepath = keep["fp"]
        for n in hidden: bpy.context.view_layer.layer_collection.children[n].exclude = False
        bpy.data.objects.remove(ob); bpy.data.cameras.remove(cd)
    result = {"rendered": len(done), "dir": od}

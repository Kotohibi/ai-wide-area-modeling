r"""Write the animated scene camera as camera.json for scripts/unreal/ue_camera_seq.py (Level Sequence in Unreal).
Before running:  CAMJSON = {"path": r"...\camera.json", "camera": "FlyCam" (default: scene camera),
                            "start": 1, "end": 250 (default: scene range), "cuts": [[1, 120], [120, 251]] (optional)}
One entry per frame: position and a look-at point 1 m ahead (the camera's roll is not carried over), fps, focal length
and sensor (the height is taken from the render aspect, so the horizontal field of view matches).  result -> dict."""
import bpy, json
from mathutils import Vector
_c = globals().get("CAMJSON", {}); sc = bpy.context.scene; cam = bpy.data.objects[_c["camera"]] if _c.get("camera") else sc.camera
s, e = int(_c.get("start", sc.frame_start)), int(_c.get("end", sc.frame_end)); keep = sc.frame_current; fr = []
for f in range(s, e + 1):
    sc.frame_set(f); M = cam.matrix_world; p = M.translation; d = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    fr.append({"f": f, "loc": [round(v, 4) for v in p], "look": [round(v, 4) for v in (p + d)]})
sc.frame_set(keep); sw = cam.data.sensor_width
out = {"fps": round(sc.render.fps / sc.render.fps_base), "lens_mm": cam.data.lens, "sensor_mm": [sw, round(sw * sc.render.resolution_y / sc.render.resolution_x, 4)], "frames": fr}
if _c.get("cuts"): out["cuts"] = _c["cuts"]
json.dump(out, open(_c["path"], "w")); result = {"frames": len(fr), "path": _c["path"], "lens_mm": cam.data.lens}

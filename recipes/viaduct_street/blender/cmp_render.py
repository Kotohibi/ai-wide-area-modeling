import bpy, json, math
from mathutils import Matrix, Vector
import os; SH = os.environ.get("BLENDER_SHARED", "")
poses = json.load(open(SH + r"\poses_level.json"))
S = PARAMS_S
sc = bpy.context.scene
cd = bpy.data.cameras.get("CmpCam") or bpy.data.cameras.new("CmpCam")
cam = bpy.data.objects.get("CmpCam") or bpy.data.objects.new("CmpCam", cd)
if cam.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(cam)
cd.sensor_fit = 'VERTICAL'; cd.angle = math.radians(90); cd.clip_end = 3000; cd.clip_start = 0.05
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 480; sc.render.resolution_y = 480; sc.render.resolution_percentage = 100
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.color = (0.55, 0.72, 0.92)
sc.camera = cam
done = []
for o in poses:
    if o["name"] not in CMP_NAMES: continue
    loc = Vector(o["loc"]) / 1.15 * S
    R = Matrix(o["rot"]).to_4x4(); R.translation = loc
    cam.matrix_world = R
    sc.render.filepath = SH + "\\cmp_" + o["name"].replace(".png", "") + ".png"
    bpy.ops.render.render(write_still=True)
    done.append(o["name"])
# restore main camera
sc.camera = bpy.data.objects["Camera"]
sc.render.resolution_x = 1408; sc.render.resolution_y = 1004
result = {"rendered": len(done)}

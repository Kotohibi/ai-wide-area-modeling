r"""Check the tree trunks of a .blend (background Blender):  blender -b <file>.blend -P tools\check_trunks.py -- <out.png>
1. per trunk mesh TW_*: vertices, faces, loose parts (= branches; with one cylinder per segment it was one part per SEGMENT) and
   open edges (a continuous, closed tube has none)
2. a close-up render of the tallest cherry's trunk (camera 1.6 m from it, 1.5 m up), Cycles 48 samples -> <out.png>"""
import bpy, bmesh, sys, math
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else None
rows = []
for c in bpy.data.collections["TreeProtos"].children:
    for o in c.objects:
        if not o.name.startswith("TW_"): continue
        bm = bmesh.new(); bm.from_mesh(o.data); seen = set(); parts = 0
        for v in bm.verts:
            if v.index in seen: continue
            parts += 1; st = [v]; seen.add(v.index)
            while st:
                x = st.pop()
                for e in x.link_edges:
                    w = e.other_vert(x)
                    if w.index not in seen: seen.add(w.index); st.append(w)
        rows.append((o.name, len(bm.verts), len(bm.faces), parts, sum(1 for e in bm.edges if len(e.link_faces) == 1))); bm.free()
for r in rows: print("TRUNK %-16s verts %5d faces %5d parts %4d open_edges %4d" % r)
if out:
    sc = bpy.context.scene; es = [e for e in bpy.data.collections["Trees"].objects if e.instance_collection and "cherry" in e.instance_collection.name]
    e = max(es, key=lambda x: x.scale.z); p = e.matrix_world.translation
    cam = bpy.data.objects.new("TrunkCheckCam", bpy.data.cameras.new("TrunkCheckCam")); sc.collection.objects.link(cam); cam.data.lens = 24
    cam.location = p + Vector((1.6, -1.6, 1.5)); d = (p + Vector((0, 0, 2.2))) - cam.location; cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam; sc.frame_set(1); sc.render.engine = "CYCLES"; sc.cycles.samples = 48; sc.render.resolution_x = 480; sc.render.resolution_y = 720; sc.render.resolution_percentage = 100
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA"):
            pr.compute_device_type = dev; pr.get_devices()
            for d_ in pr.devices: d_.use = d_.type == dev
            if any(d_.use for d_ in pr.devices): sc.cycles.device = "GPU"; break
    except Exception as ex: print("GPU:", ex)
    sc.render.filepath = out; sc.render.image_settings.file_format = "PNG"; bpy.ops.render.render(write_still=True); print("TRUNK_RENDER", out, e.name, tuple(round(v, 2) for v in p))
print("TRUNK_CHECK_DONE")

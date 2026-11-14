r"""Blender: what does the model show at given pixels of a comparison view? (object, material, 3D point, distance)

    CMPPROBE = {"dir": r"...\compare", "pixels": {"07_soffit": [(960, 960), (400, 1500)], ...}, "hide": ["Anim", "FX"]}
    p = SH + r"\bl_cmp_probe.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
result = {stem: [(u, v, object, material, [x, y, z], distance) | (u, v, None)]}
Use it on every pixel where the render and the photo disagree before changing anything: the wrong thing is often another object than
expected (a strip of road behind a footway that got its own kerb, a tree that is really a chain-link fence, a building that is not there).
"""
import bpy, json, os
from mathutils import Matrix, Vector
cfg = globals()["CMPPROBE"]
cams = {c["stem"]: c for c in json.load(open(os.path.join(cfg["dir"], "cameras.json"), encoding="utf-8"))}
sc = bpy.context.scene; hidden = []
for n in cfg.get("hide", ["Anim", "FX", "RefViews", "Diff"]):
    lc = bpy.context.view_layer.layer_collection.children.get(n)
    if lc and not lc.exclude: lc.exclude = True; hidden.append(n)
bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); out = {}
try:
    for stem, pix in cfg["pixels"].items():
        c = cams[stem]; R = Matrix(c["rot"]); o = Vector(c["loc"]); res = []
        for u, v in pix:
            d = R @ Vector(((u + .5 - c["cx"]) / c["fx"], -(v + .5 - c["cy"]) / c["fy"], -1.0)); d.normalize()
            hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, o, d)
            if not hit: res.append((u, v, None)); continue
            mat = None
            try:
                me = ob.data; mat = me.materials[me.polygons[idx].material_index].name if idx < len(me.polygons) else None
            except Exception: pass
            res.append((u, v, ob.name, mat, [round(x, 2) for x in loc], round((loc - o).length, 1)))
        out[stem] = res
finally:
    for n in hidden: bpy.context.view_layer.layer_collection.children[n].exclude = False
result = out

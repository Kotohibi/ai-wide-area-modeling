r"""Export groups of collections/objects as one FBX per group, for game engines (Unreal Engine).
Each group: modifiers applied, all objects joined into one mesh (materials kept as slots), origin moved to the
group's footprint centre on the ground (x, y of the bbox centre, z = 0), written at the world origin.
The scene is not modified (temporary data is removed afterwards).

Run inside Blender:
    EXPORT = {"out_dir": r"F:\...\ue_export", "groups": {"SM_Gate": {"collections": ["Temple_Gate_Base", ...]},
              "SM_Planting": {"objects": ["Trees", "Hedges"]}, ...}, "center": {"SM_Gate": [1.15, 23.95]}}
    p = SH + r"\bl_export_groups.py"; exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
result: {group: {"file", "center_m": [x, y, 0], "tris", "materials": [...], "size_m"}}
Also merges everything into <out_dir>/export_manifest.json, with "_materials": {name: [r, g, b (linear), roughness]}
(from each material's Principled BSDF, else its viewport colour) - scripts/unreal/ue_port.py reads that file.
Unreal: vertices are baked x100 (EXPORT["unit_scale"], default 100) because UE's FBX import (Interchange) read the
exported numbers as centimetres (a 6.33 m garage came in 6.33 cm). Verify the axes with an asymmetric mesh
(StaticMeshTools.get_bounds) before placing: Blender (x, y, z) m -> UE (100x, -100y, 100z) cm was measured.
Check before exporting that no object has a stray transform (a user edit moved one object by metres once), and that
faces point outward (UE culls back faces; Blender draws both sides) - see references/unreal.md.
"""
import bpy, bmesh, os
from mathutils import Matrix, Vector

cfg = globals().get("EXPORT", {})
out_dir = cfg["out_dir"]; os.makedirs(out_dir, exist_ok=True)
dg = bpy.context.evaluated_depsgraph_get()

def objects_of(spec):
    obs = []
    for cn in spec.get("collections", []):
        col = bpy.data.collections.get(cn)
        if col: obs += [o for o in col.all_objects if o.type == 'MESH']
    for on in spec.get("objects", []):
        o = bpy.data.objects.get(on)
        if o and o.type == 'MESH': obs.append(o)
    seen = set(); return [o for o in obs if not (o.name in seen or seen.add(o.name))]

res = {}
prev_sel = [o for o in bpy.context.selected_objects]; prev_active = bpy.context.view_layer.objects.active
for gname, spec in cfg["groups"].items():
    obs = objects_of(spec)
    if not obs: res[gname] = "no objects"; continue
    bm = bmesh.new(); mats = []; lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for o in obs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
        me.transform(o.matrix_world)
        remap = []
        for m in me.materials:
            if m is None: remap.append(0); continue
            if m not in mats: mats.append(m)
            remap.append(mats.index(m))
        for p in me.polygons: p.material_index = remap[p.material_index] if remap else 0
        for v in me.vertices:
            lo = Vector(map(min, lo, v.co)); hi = Vector(map(max, hi, v.co))
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    c = cfg.get("center", {}).get(gname) or [(lo.x + hi.x) / 2, (lo.y + hi.y) / 2]
    bmesh.ops.translate(bm, vec=Vector((-c[0], -c[1], 0.0)), verts=bm.verts)
    k = cfg.get("unit_scale", 100.0)                           # UE (Interchange) reads these FBX numbers as cm: bake m -> cm
    if k != 1.0: bmesh.ops.scale(bm, vec=Vector((k, k, k)), verts=bm.verts)
    bmesh.ops.triangulate(bm, faces=bm.faces)                 # explicit triangles: same shading in every engine
    me = bpy.data.meshes.new(gname); bm.to_mesh(me); tris = len(bm.faces); bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(gname, me); bpy.context.scene.collection.objects.link(ob)
    for o in bpy.context.selected_objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    f = os.path.join(out_dir, gname + ".fbx")
    bpy.ops.export_scene.fbx(filepath=f, use_selection=True, object_types={'MESH'}, use_mesh_modifiers=True,
                             mesh_smooth_type='FACE', apply_scale_options='FBX_SCALE_UNITS', bake_space_transform=False,
                             add_leaf_bones=False, path_mode='STRIP', embed_textures=False)
    res[gname] = {"file": f, "center_m": [round(c[0], 3), round(c[1], 3), 0.0], "tris": tris, "materials": [m.name for m in mats],
                  "size_m": [round(hi.x - lo.x, 2), round(hi.y - lo.y, 2), round(hi.z - lo.z, 2)]}
    bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
for o in prev_sel: o.select_set(True)
bpy.context.view_layer.objects.active = prev_active

def mat_info(m):
    try:
        b = m.node_tree.nodes.get("Principled BSDF")
        c = b.inputs["Base Color"].default_value; r = b.inputs["Roughness"].default_value
        return [round(c[0], 4), round(c[1], 4), round(c[2], 4), round(r, 3)]
    except Exception:
        c = m.diffuse_color; return [round(c[0], 4), round(c[1], 4), round(c[2], 4), round(m.roughness, 3)]
import json
mp = os.path.join(out_dir, "export_manifest.json")
man = json.load(open(mp)) if os.path.exists(mp) else {}
man.update({k: v for k, v in res.items() if isinstance(v, dict)})
mats_all = man.get("_materials", {})
for v in res.values():
    if isinstance(v, dict):
        for n in v["materials"]:
            m = bpy.data.materials.get(n)
            if m: mats_all[n] = mat_info(m)
man["_materials"] = mats_all
json.dump(man, open(mp, "w"), indent=1)
result = res

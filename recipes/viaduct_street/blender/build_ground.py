# NOTE: example from a real project. Contains project-specific constants (paths, ranges, sizes): change them before reuse.
import bpy, bmesh, json, math, os
import numpy as np
from mathutils import Vector

import os; SH = os.environ.get("BLENDER_SHARED", "")
S = GSCALE
col = bpy.data.collections.get("Viaduct_V3")
for nm in ("RoadStrip",):
    o = bpy.data.objects.get(nm)
    if o: bpy.data.objects.remove(o, do_unlink=True)
gcol = bpy.data.collections.get("Street_V1")
if gcol:
    for o in list(gcol.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(gcol)
gcol = bpy.data.collections.new("Street_V1"); bpy.context.scene.collection.children.link(gcol)

# ---------------------------------------------------------------- materials
def flat(name, rgb, rough=0.9):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough; m.diffuse_color = (*rgb, 1)
    return m
img = bpy.data.images.get("ortho_photo.png")
if img: bpy.data.images.remove(img)
img = bpy.data.images.load(SH + r"\ortho_photo.png"); img.colorspace_settings.name = 'sRGB'
road_mat = bpy.data.materials.get("RoadPhoto") or bpy.data.materials.new("RoadPhoto")
road_mat.use_nodes = True
nt = road_mat.node_tree
for n in list(nt.nodes):
    if n.type not in ('OUTPUT_MATERIAL', 'BSDF_PRINCIPLED'): nt.nodes.remove(n)
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = 'Linear'
bsdf = nt.nodes["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.95
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
road_mat.diffuse_color = (0.25, 0.25, 0.27, 1)
GRASS = flat("GrassFlat", (0.20, 0.38, 0.14)); CURB = flat("CurbConcrete", (0.62, 0.61, 0.58)); POLE = flat("PoleGray", (0.45, 0.47, 0.48), 0.6)
SIGB = flat("SignBlue", (0.05, 0.25, 0.65)); SIGW = flat("SignWhite", (0.92, 0.92, 0.90)); SIGR = flat("SignRed", (0.75, 0.08, 0.06))
HOUSE = flat("SignalHousing", (0.10, 0.12, 0.10)); LAMP = flat("LampLight", (0.95, 0.93, 0.80))

def textured_mesh(name, V, F, UV, material, z_scale=True):
    V = np.asarray(V, np.float64).copy(); V[:, :] *= S
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], np.asarray(F).tolist()); me.update()
    if UV is not None:
        uvl = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li, vi in zip(poly.loop_indices, poly.vertices):
                uvl.data[li].uv = UV[vi]
    ob = bpy.data.objects.new(name, me); ob.data.materials.append(material); gcol.objects.link(ob); return ob

# Photo-textured ground meshes (classification + orthophoto) are optional: set GROUND_MESHES = False before exec
# when the road is modelled procedurally with build_road.py (preferred for a clean model).
if globals().get("GROUND_MESHES", True):
    gm = np.load(SH + r"\ground_mesh.npz")
    textured_mesh("Road", gm["rv"], gm["rf"], gm["ruv"], road_mat)
    textured_mesh("Sidewalk", gm["sv"], gm["sf"], gm["suv"], road_mat)
    textured_mesh("Grass", gm["gv"], gm["gf"], None, GRASS)
    if len(gm["cf"]): textured_mesh("Curb", gm["cv"], gm["cf"], None, CURB)

# ---------------------------------------------------------------- poles, signals, signs, street lights
poles = json.load(open(SH + r"\poles.json"))
Pp = np.array(json.load(open(SH + r"\path_level.json"))["path"])
# merge near duplicates
kept = []
for p in sorted(poles, key=lambda q: -(q["z1"] - q["z0"])):
    if all((p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2 > 1.2 ** 2 for q in kept): kept.append(p)
bm = {}
def bmesh_for(key):
    if key not in bm: bm[key] = bmesh.new()
    return bm[key]
def add_box(b, c, size, rot_z=0.0):
    r = bmesh.ops.create_cube(b, size=1.0)
    for v in r["verts"]:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bmesh.ops.rotate(b, verts=r["verts"], cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(rot_z, 3, 'Z'))
    bmesh.ops.translate(b, verts=r["verts"], vec=c)
def add_cyl(b, base, h, rad):
    r = bmesh.ops.create_cone(b, cap_ends=True, segments=8, radius1=rad, radius2=rad, depth=h)
    bmesh.ops.translate(b, verts=r["verts"], vec=(base[0], base[1], base[2] + h / 2))
n_light = n_sig = n_sign = 0
# POLES_AUTO = False: skip these height-based guesses and place street furniture from a photo-reviewed spec
# with build_furniture.py (signs / signals with their real facing). The guesses below mislabel most under-viaduct
# street lights as signs, because only the lower part of a lamp pole is reconstructed.
if not globals().get("POLES_AUTO", True): kept = []
for p in kept:
    z0 = max(0.0, min(p["z0"], 0.6)); z1 = min(p["z1"], 9.0); h = z1 - z0
    if h < 1.5: continue
    base = Vector((p["x"] * S, p["y"] * S, z0 * S))
    # direction toward the nearest route point (towards the road)
    i = int(np.argmin((Pp[:, 1] - p["x"]) ** 2 + (Pp[:, 2] - p["y"]) ** 2))
    d = np.array([Pp[i, 1] - p["x"], Pp[i, 2] - p["y"]]); d /= max(np.linalg.norm(d), 1e-6); ang = math.atan2(d[1], d[0])
    bp = bmesh_for("pole")
    add_cyl(bp, base, h * S, 0.07 * S)
    if p["z1"] > 6.0:                                            # street light: arm + lamp head
        arm = Vector((d[0], d[1], 0)) * 1.4 * S
        add_box(bp, (base.x + arm.x * 0.5, base.y + arm.y * 0.5, (z1 - 0.1) * S), (1.4 * S, 0.08 * S, 0.08 * S), ang)
        add_box(bmesh_for("lamp"), (base.x + arm.x, base.y + arm.y, (z1 - 0.18) * S), (0.5 * S, 0.22 * S, 0.1 * S), ang); n_light += 1
    elif p["z1"] >= 3.4:                                          # traffic signal head + pedestrian signal
        off = Vector((d[0], d[1], 0)) * 0.25 * S
        add_box(bmesh_for("house"), (base.x + off.x, base.y + off.y, (z1 - 0.25) * S), (0.22 * S, 0.8 * S, 0.3 * S), ang + math.pi / 2)
        add_box(bmesh_for("house"), (base.x + off.x, base.y + off.y, 2.4 * S), (0.2 * S, 0.3 * S, 0.3 * S), ang + math.pi / 2); n_sig += 1
    else:                                                         # sign plate
        key = "signb" if p["blue"] > 0.55 else "signw"
        off = Vector((d[0], d[1], 0)) * 0.1 * S
        add_box(bmesh_for(key), (base.x + off.x, base.y + off.y, (z1 - 0.3) * S), (0.04 * S, 0.7 * S, 0.7 * S), ang); n_sign += 1
mats = {"pole": POLE, "lamp": LAMP, "house": HOUSE, "signb": SIGB, "signw": SIGW}
for k, b in bm.items():
    me = bpy.data.meshes.new("Street_" + k); b.to_mesh(me); b.free()
    ob = bpy.data.objects.new("Street_" + k, me); ob.data.materials.append(mats[k]); gcol.objects.link(ob)
result = {"poles_kept": len(kept), "lights": n_light, "signals": n_sig, "signs": n_sign, "street_objects": len(gcol.objects)}

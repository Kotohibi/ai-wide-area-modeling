"""Road markings as thin 3D plates in the `Markings` collection (run inside Blender after build_v3/build_ground).

Inputs (namespace before exec): MPARAMS = {
  "S": 1.6,                       # metres per unit (same as build_v3)
  "min_lat": 1.0,                 # drop detected lines nearer the route than this (curbs / sidewalk edges)
  "crosswalks": [dict(s0=, s1=, lat0=, lat1=, bars="s"|"lat"), ...],   # bars="s": bars run along the route
}
Lines come from $BLENDER_SHARED/lines.json (detect_lines.py). Coordinates are (s, lat) on the same smoothed route as build_v3.
Dimensions follow Japanese standards: lane line 0.15 m wide, dashes 5 m / gaps 5 m, crosswalk bars 0.45 m / gaps 0.45 m.
"""
import bpy, bmesh, json, math, os
import numpy as np
SH = os.environ.get("BLENDER_SHARED", "")
S = MPARAMS.get("S", 1.6)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0
cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4); cz = np.polyfit(u, P[:, 3], 2)
def frame(s):
    uu = (s - 266.0) / 180.0
    p = np.array([np.polyval(cx, uu), np.polyval(cy, uu)]); d = np.array([np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)])
    t = d / np.linalg.norm(d); return p, t, np.array([t[1], -t[0]]), float(np.polyval(cz, uu))
Z = 0.012                                     # metres above the road surface (avoids z-fighting with the textured road)
col = bpy.data.collections.get("Markings")
if col:
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
col = bpy.data.collections.new("Markings"); bpy.context.scene.collection.children.link(col)
mat = bpy.data.materials.get("RoadPaint") or bpy.data.materials.new("RoadPaint")
mat.use_nodes = True; mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.93, 0.93, 0.90, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6; mat.diffuse_color = (0.93, 0.93, 0.90, 1)
bm = bmesh.new()
def quad(s0, s1, l0, l1):
    """plate between route stations s0..s1 and lateral l0..l1 (units), following the curve"""
    n = max(1, int(abs(s1 - s0) / 2.0))
    ring = []
    for k in range(n + 1):
        s = s0 + (s1 - s0) * k / n; p, t, nr, g = frame(s)
        ring.append(((p + nr * l0) * S, (p + nr * l1) * S, g * S + Z))
    vs = [(bm.verts.new((a[0], a[1], z)), bm.verts.new((b[0], b[1], z))) for a, b, z in ring]
    for k in range(n):
        bm.faces.new((vs[k][0], vs[k + 1][0], vs[k + 1][1], vs[k][1]))
nl = 0
W = 0.15 / S; DASH = 5.0 / S; GAP = 5.0 / S
for ln in (json.load(open(SH + r"\lines.json")) if MPARAMS.get("lines", True) else []):   # "lines": False when build_road draws lane lines
    if ln["lat"] < MPARAMS.get("min_lat", 1.0): continue
    if ln["type"] == "solid":
        quad(ln["s0"], ln["s1"], ln["lat"] - W / 2, ln["lat"] + W / 2)
    else:
        s = ln["s0"]
        while s < ln["s1"]:
            quad(s, min(s + DASH, ln["s1"]), ln["lat"] - W / 2, ln["lat"] + W / 2); s += DASH + GAP
    nl += 1
BAR = 0.45 / S; PITCH = 0.9 / S
for cw in MPARAMS.get("crosswalks", []):
    if cw.get("bars", "s") == "s":           # bars along the route, stacked across it
        l = cw["lat0"] + (PITCH - BAR) / 2
        while l + BAR <= cw["lat1"]:
            quad(cw["s0"], cw["s1"], l, l + BAR); l += PITCH
    else:                                    # bars across the route (crossing a side street), stacked along s
        s = cw["s0"] + (PITCH - BAR) / 2
        while s + BAR <= cw["s1"]:
            quad(s, s + BAR, cw["lat0"], cw["lat1"]); s += PITCH
me = bpy.data.meshes.new("RoadMarkings"); bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new("RoadMarkings", me); ob.data.materials.append(mat); col.objects.link(ob)
result = {"lines": nl, "crosswalks": len(MPARAMS.get("crosswalks", [])), "faces": len(me.polygons)}

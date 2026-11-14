"""Transmission towers, utility poles and trees (from extras.py) in the `Extras` collection.

Inputs (namespace before exec): XPARAMS = {"S": 1.6, "tower_min_n": 1000, "tower_merge": 8.0}
Towers: 4 tapered legs + horizontal bracing + cross-arms (rough lattice silhouette).
Trees: trunk + slightly squashed sphere crown. Utility poles: concrete pole with a cross-arm.
"""
import bpy, bmesh, json, math, os
from mathutils import Matrix, Vector
SH = os.environ.get("BLENDER_SHARED", "")
S = XPARAMS.get("S", 1.6)
E = json.load(open(SH + r"\extras.json"))
col = bpy.data.collections.get("Extras")
if col:
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
col = bpy.data.collections.new("Extras"); bpy.context.scene.collection.children.link(col)
def mat(name, rgb, rough=0.8, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*rgb, 1); return m
STEELG = mat("TowerSteel", (0.55, 0.57, 0.58), 0.5, 0.6); POLEC = mat("PoleConcrete", (0.62, 0.62, 0.60))
BARK = mat("Bark", (0.25, 0.18, 0.12)); LEAF = mat("Leaves", (0.18, 0.34, 0.12))
def beam(bm, a, b, w):
    """square bar from point a to point b (metres), width w"""
    a, b = Vector(a), Vector(b); d = b - a; L = d.length
    if L < 1e-6: return
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]: v.co.x *= w; v.co.y *= w; v.co.z *= L
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix()
    bmesh.ops.rotate(bm, verts=r["verts"], cent=(0, 0, 0), matrix=rot)
    bmesh.ops.translate(bm, verts=r["verts"], vec=(a + b) / 2)
def obj(name, bm, material):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.data.materials.append(material); col.objects.link(o); return o
# ---- towers (strong clusters only, merged)
tw = sorted([t for t in E["towers"] if t["n"] >= XPARAMS.get("tower_min_n", 1000)], key=lambda t: -t["h"])
kept = []
for t in tw:
    if all((t["x"] - k["x"]) ** 2 + (t["y"] - k["y"]) ** 2 > XPARAMS.get("tower_merge", 8.0) ** 2 for k in kept): kept.append(t)
# tall clusters that the photos show are NOT lattice towers (e.g. a white water/observation tower):
# XPARAMS["round_towers"] = [dict(x=, y=, h=, r=, top_r=)] replaces any kept tower within 15 units
WHITE = mat("TowerWhite", (0.88, 0.88, 0.86))
for rt in XPARAMS.get("round_towers", []):
    kept = [t for t in kept if (t["x"] - rt["x"]) ** 2 + (t["y"] - rt["y"]) ** 2 > 15 ** 2]
    bm = bmesh.new(); H = rt["h"] * S; R = rt.get("r", 1.6) * S; TR = rt.get("top_r", 3.2) * S
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=R * 1.2, radius2=R, depth=H * 0.82)
    bmesh.ops.translate(bm, verts=r["verts"], vec=(rt["x"] * S, rt["y"] * S, H * 0.41))
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=TR * 0.7, radius2=TR, depth=H * 0.12)
    bmesh.ops.translate(bm, verts=r["verts"], vec=(rt["x"] * S, rt["y"] * S, H * 0.88))
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=TR * 0.9, radius2=TR * 0.3, depth=H * 0.06)
    bmesh.ops.translate(bm, verts=r["verts"], vec=(rt["x"] * S, rt["y"] * S, H * 0.97))
    obj("RoundTower", bm, WHITE)
for i, t in enumerate(kept):
    bm = bmesh.new(); H = t["h"] * S; B = min(max(t["base"], 5.0), 9.0) * S / 2; Tp = B * 0.18
    cx, cy = t["x"] * S, t["y"] * S
    def leg(sx, sy, z):
        k = z / H; hw = B * (1 - k) + Tp * k
        return (cx + sx * hw, cy + sy * hw, z)
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    for sx, sy in corners: beam(bm, leg(sx, sy, 0), leg(sx, sy, H), 0.35)
    nb = 8
    for k in range(1, nb + 1):
        z = H * k / (nb + 1)
        for j in range(4):
            beam(bm, leg(*corners[j], z), leg(*corners[(j + 1) % 4], z), 0.18)
            if k < nb: beam(bm, leg(*corners[j], z), leg(*corners[(j + 1) % 4], H * (k + 1) / (nb + 1)), 0.1)
    for frac, arm in ((0.70, 2.6), (0.80, 2.2), (0.90, 1.8)):           # cross-arms
        z = H * frac; hw = B * (1 - frac) + Tp * frac
        beam(bm, (cx - hw - arm * B * 0.6, cy, z), (cx + hw + arm * B * 0.6, cy, z), 0.3)
    obj(f"Tower_{i+1}", bm, STEELG)
# ---- utility poles
bm = bmesh.new(); npl = 0
for p in E["poles"]:
    H = min(p["h"], 10.0) * S; x, y = p["x"] * S, p["y"] * S
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.17, radius2=0.12, depth=H)
    bmesh.ops.translate(bm, verts=r["verts"], vec=(x, y, H / 2))
    beam(bm, (x - 0.9, y, H - 0.6), (x + 0.9, y, H - 0.6), 0.1); npl += 1
if npl: obj("UtilityPoles", bm, POLEC)
else: bm.free()
# ---- trees
bt = bmesh.new(); bl = bmesh.new(); ntr = 0
for t in E["trees"]:
    th = min(max(t["h"], 2.0), XPARAMS.get("tree_max_h", 9.0))      # street trees rarely exceed ~14 m
    H = th * S; R = min(max(t["r"], 1.0), 4.0, 0.33 * th) * S; x, y = t["x"] * S, t["y"] * S   # crown in proportion to height
    trunk_h = max(H - 1.4 * R, 0.4 * H)
    r = bmesh.ops.create_cone(bt, cap_ends=True, segments=6, radius1=0.18, radius2=0.12, depth=trunk_h)
    bmesh.ops.translate(bt, verts=r["verts"], vec=(x, y, trunk_h / 2))
    r = bmesh.ops.create_icosphere(bl, subdivisions=2, radius=R)
    for v in r["verts"]: v.co.z *= 0.8
    bmesh.ops.translate(bl, verts=r["verts"], vec=(x, y, max(H - 0.8 * R, trunk_h + 0.5 * R)))
    ntr += 1
obj("TreeTrunks", bt, BARK); obj("TreeCrowns", bl, LEAF)
result = {"towers": len(kept), "round_towers": len(XPARAMS.get("round_towers", [])), "utility_poles": npl, "trees": ntr}

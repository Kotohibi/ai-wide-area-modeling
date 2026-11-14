"""Street furniture from a photo-reviewed spec: street lights, traffic signals and road signs with their real facing.

Inputs (namespace before exec): FPARAMS = {"S": 1.6} and $BLENDER_SHARED/street_furniture.json:
  {"items": [ {"x":..,"y":..,"type":"light"|"signal"|"sign", "face": deg, ...}, ... ]}
  x, y      leveled-frame position of the pole (units; from pole_index.json written by sign_views.py)
  face      bearing of the FRONT face normal, relative to the route at that point: 0 = +s, 90 = +lat (right),
            180 = -s, -90 = -lat. Read it from sign_views.py 'quad' sheets: the camera sector in which the
            coloured face / lit lamps are visible is the facing.
  light : "h" lamp height (units, default 3.8), arm points to "face".
  signal: "arm" length (units, default 3.0) along "arm_dir" (deg, default = toward the road centre),
          vehicle head (horizontal 3 lamps) at the arm end facing "face"; "ped": true adds a pedestrian head
          on the pole facing "ped_face" (default = face).
  sign  : "kind" in guide_blue (large blue guide plate), round_blue, round_red, round_white, triangle;
          "h" plate centre height (units, default 1.6), "size" (m, default 0.6; guide_blue 2.0 x 1.4).
          "extra": [ {kind, face, h}, ... ] for more plates on the same pole.
Front faces carry the colour (and lit lamps for signals); backs are grey, so the facing is visible in renders.
Collection `Furniture` (re-runnable).
"""
import bpy, bmesh, json, math, os
import numpy as np
from mathutils import Matrix, Vector
SH = os.environ.get("BLENDER_SHARED", "")
S = FPARAMS.get("S", 1.6)
spec = json.load(open(SH + r"\street_furniture.json"))
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0; cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4)
ss = np.arange(40, 480, 0.25); U = (ss - 266.0) / 180.0
px, py = np.polyval(cx, U), np.polyval(cy, U); dx, dy = np.polyval(np.polyder(cx), U), np.polyval(np.polyder(cy), U); nn = np.hypot(dx, dy)
def route_dirs(x, y):
    i = int(np.argmin((px - x) ** 2 + (py - y) ** 2)); t = np.array([dx[i], dy[i]]) / nn[i]
    return t, np.array([t[1], -t[0]]), float(ss[i]), float((x - px[i]) * t[1] - (y - py[i]) * t[0]), np.array([px[i], py[i]])
def bearing_vec(b, t, n):
    r = math.radians(b); v = math.cos(r) * t + math.sin(r) * n; return v / np.linalg.norm(v)
col = bpy.data.collections.get("Furniture")
if col:
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
col = bpy.data.collections.new("Furniture"); bpy.context.scene.collection.children.link(col)
def mat(name, rgb, rough=0.7, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    if emit: b.inputs["Emission Color"].default_value = (*rgb, 1); b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (*rgb, 1); return m
M = {"pole": mat("FurnPole", (0.55, 0.57, 0.58), 0.5), "back": mat("SignBack", (0.62, 0.63, 0.64)),
     "housing": mat("SignalHousing", (0.12, 0.13, 0.12)), "lamp": mat("LampHead", (0.95, 0.93, 0.80)),
     "red": mat("LampRed", (0.9, 0.08, 0.05), 0.4, 2.0), "yellow": mat("LampYellow", (0.95, 0.65, 0.05), 0.4, 0.0),
     "green": mat("LampGreen", (0.05, 0.75, 0.55), 0.4, 0.0),
     "blue": mat("SignBlue", (0.05, 0.25, 0.65)), "white": mat("SignWhite", (0.92, 0.92, 0.90)),
     "redsign": mat("SignRed", (0.78, 0.08, 0.06)), "yellowsign": mat("SignYellow", (0.95, 0.75, 0.05))}
bms = {k: bmesh.new() for k in M}
def box(key, centre, size, dirv):
    """box centred at centre (m), size (w along face plane, d along dirv, h), oriented so +depth = dirv"""
    r = bmesh.ops.create_cube(bms[key], size=1.0)
    for v in r["verts"]: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    ang = math.atan2(dirv[1], dirv[0]) - math.pi / 2
    bmesh.ops.rotate(bms[key], verts=r["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(ang, 3, 'Z'))
    bmesh.ops.translate(bms[key], verts=r["verts"], vec=Vector(centre))
def disc(key, centre, rad, dirv, depth=0.02):
    r = bmesh.ops.create_cone(bms[key], cap_ends=True, segments=16, radius1=rad, radius2=rad, depth=depth)
    rot = Vector((0, 0, 1)).rotation_difference(Vector((dirv[0], dirv[1], 0)).normalized()).to_matrix()
    bmesh.ops.rotate(bms[key], verts=r["verts"], cent=(0, 0, 0), matrix=rot)
    bmesh.ops.translate(bms[key], verts=r["verts"], vec=Vector(centre))
def pole(x, y, h, rad=0.08):
    r = bmesh.ops.create_cone(bms["pole"], cap_ends=True, segments=10, radius1=rad, radius2=rad * 0.8, depth=h)
    bmesh.ops.translate(bms["pole"], verts=r["verts"], vec=(x, y, h / 2))
def plate(kind, c, f, size=None):
    """sign plate: grey back, coloured front offset toward f (unit 2D vector, metres)"""
    fv = np.array([f[0], f[1], 0.0])
    if kind == "guide_blue":
        w, h = size or (2.0, 1.4)
        box("back", c, (w, 0.05, h), f); box("blue", c + fv * 0.035, (w * 0.97, 0.02, h * 0.95), f)
    elif kind == "triangle":
        sz = size or 0.8; box("back", c, (sz, 0.04, sz * 0.85), f); box("yellowsign", c + fv * 0.03, (sz * 0.9, 0.02, sz * 0.75), f)
    else:
        rad = (size or 0.6) / 2; colr = {"round_blue": "blue", "round_red": "redsign", "round_white": "white"}.get(kind, "white")
        disc("back", c, rad, f, 0.03); disc(colr, c + fv * 0.025, rad * 0.95, f, 0.01)
# ---- keep pole bases off the carriageway: snap into the nearest kerbed element (sidewalk / median / planting)
# using the same road spec as build_road.py ($BLENDER_SHARED/params_road.json). A post found on asphalt (road
# element, or a junction paved by an "opening") moves to just inside the nearest kerb (KERB_IN metres), either
# sideways to a kerbed strip of the same section or along s past the end of the opening (street corner).
ROAD = json.load(open(SH + r"\params_road.json")) if os.path.exists(SH + r"\params_road.json") else None
KERB_IN = FPARAMS.get("kerb_in", 0.4) / S
def kerbed_at(s, lat):
    """True if (s, lat) is on a kerbed strip, False if on asphalt, None if outside the modelled road"""
    if not ROAD: return None
    for o in ROAD.get("openings", []):
        if o["s0"] <= s <= o["s1"] and o.get("fill") and o["fill"][0] <= lat <= o["fill"][1]: return False
    for sec in ROAD["sections"]:
        if not (sec["s0"] <= s < sec["s1"]): continue
        for e in sec["elems"]:
            if e["l0"] <= lat <= e["l1"]: return e["type"] != "road"
    return None
def snap(s, lat):
    if kerbed_at(s, lat) is not False: return s, lat, False
    cands = []
    for sec in ROAD["sections"]:
        if not (sec["s0"] <= s < sec["s1"]): continue
        for e in sec["elems"]:
            if e["type"] == "road": continue
            for l2 in (e["l0"] + KERB_IN, e["l1"] - KERB_IN):
                if e["l0"] < l2 < e["l1"] and kerbed_at(s, l2): cands.append((abs(l2 - lat), s, l2))
    for o in ROAD.get("openings", []):                     # street corner: just outside the paved opening along s
        if o["s0"] <= s <= o["s1"] and o.get("fill") and o["fill"][0] <= lat <= o["fill"][1]:
            for s2 in (o["s0"] - KERB_IN, o["s1"] + KERB_IN):
                if kerbed_at(s2, lat): cands.append((abs(s2 - s), s2, lat))
    if not cands: return s, lat, False
    _, s2, l2 = min(cands); return s2, l2, True
def at_route(s, lat):
    uu = (s - 266.0) / 180.0
    p = np.array([np.polyval(cx, uu), np.polyval(cy, uu)]); d = np.array([np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)])
    t = d / np.linalg.norm(d); return p + np.array([t[1], -t[0]]) * lat
moved = []
counts = {"light": 0, "signal": 0, "sign": 0}
for it in spec["items"]:
    typ = it.get("type", "light")
    if typ == "drop": continue
    t, n, s, lat, rp = route_dirs(it["x"], it["y"])
    if FPARAMS.get("snap_to_kerb", True) and not it.get("fixed"):
        s2, l2, mv = snap(s, lat)
        if mv:
            q = at_route(s2, l2); moved.append((it.get("id"), round(s, 1), round(lat, 2), round(s2, 1), round(l2, 2)))
            it = dict(it, x=float(q[0]), y=float(q[1])); t, n, s, lat, rp = route_dirs(it["x"], it["y"])
    X, Y = it["x"] * S, it["y"] * S
    face = bearing_vec(it.get("face", 0), t, n)
    if typ == "light":
        H = it.get("h", 3.8) * S; pole(X, Y, H)
        arm = face * 1.2
        box("pole", (X + arm[0] / 2, Y + arm[1] / 2, H - 0.1), (0.08, 1.2, 0.08), face)
        box("lamp", (X + arm[0], Y + arm[1], H - 0.18), (0.3, 0.6, 0.12), face)
    elif typ == "signal":
        H = it.get("h", 3.6) * S; pole(X, Y, H + 0.4, 0.1)
        if "arm_dir" in it: ad = bearing_vec(it["arm_dir"], t, n)
        else:
            centre = rp + n * (3.8 if lat < 7 else 11.8); ad = centre - np.array([it["x"], it["y"]]); ad /= np.linalg.norm(ad)
        L = it.get("arm", 3.0) * S
        box("pole", (X + ad[0] * L / 2, Y + ad[1] * L / 2, H), (0.12, L, 0.12), ad)
        hc = np.array([X + ad[0] * L, Y + ad[1] * L, H - 0.35])
        side = np.array([-face[1], face[0], 0.0]); fv = np.array([face[0], face[1], 0.0])
        box("housing", hc, (1.25, 0.32, 0.42), face)
        for k_, lc in enumerate(("green", "yellow", "red")):       # Japanese order seen from the front: left green, right red
            disc(lc, hc + side * (-0.4 + 0.4 * k_) * -1 + fv * 0.17, 0.14, face, 0.02)
        if it.get("ped", False):
            pf = bearing_vec(it.get("ped_face", it.get("face", 0)), t, n); pfv = np.array([pf[0], pf[1], 0.0])
            pc = np.array([X, Y, 2.6]) + pfv * 0.25
            box("housing", pc, (0.35, 0.25, 0.75), pf)
            disc("red", pc + pfv * 0.13 + np.array([0, 0, 0.17]), 0.12, pf, 0.02); disc("green", pc + pfv * 0.13 - np.array([0, 0, 0.17]), 0.12, pf, 0.02)
        for ex in it.get("extra", []):
            ef = bearing_vec(ex.get("face", it.get("face", 0)), t, n)
            plate(ex["kind"], np.array([X + ef[0] * 0.12, Y + ef[1] * 0.12, ex.get("h", 2.2) * S]), ef, ex.get("size"))
    elif typ == "sign":
        hc = it.get("h", 1.6) * S
        top = hc + (0.7 if it.get("kind") == "guide_blue" else 0.35)
        pole(X, Y, top, 0.05 if it.get("kind") != "guide_blue" else 0.12)
        plate(it.get("kind", "round_blue"), np.array([X + face[0] * 0.08, Y + face[1] * 0.08, hc]), face, it.get("size"))
        for ex in it.get("extra", []):
            ef = bearing_vec(ex.get("face", it.get("face", 0)), t, n)
            plate(ex["kind"], np.array([X + ef[0] * 0.08, Y + ef[1] * 0.08, ex.get("h", 1.2) * S]), ef, ex.get("size"))
    counts[typ] = counts.get(typ, 0) + 1
for k, bm in bms.items():
    if not bm.faces: bm.free(); continue
    me = bpy.data.meshes.new("Furn_" + k); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Furn_" + k, me); o.data.materials.append(M[k]); col.objects.link(o)
result = dict(counts, moved_to_kerb=len(moved), moved=moved)

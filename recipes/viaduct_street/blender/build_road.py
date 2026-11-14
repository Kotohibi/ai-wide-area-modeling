"""Procedural road (no photo textures): carriageways, kerbed sidewalks / medians, lane markings, side streets.

Inputs (namespace before exec): RPARAMS = {
  "S": 1.6,
  "sections": [ {"s0":88, "s1":245, "elems":[
       {"type":"sidewalk", "l0":-4.0, "l1":0.3},
       {"type":"road", "l0":0.3, "l1":7.3, "lines":[[0.8,"solid"],[2.95,"dashed"],[5.1,"solid"]]},
       {"type":"median", "l0":7.3, "l1":9.7}, ...]}, ...],
  "openings": [ {"s0":131, "s1":162, "types":["median"], "fill":[0.3, 14.0]} ],   # intersections: drop elems, pave across
  "side_streets": [ {"s0":141.7, "s1":151.5, "l0":0.3, "l1":-30, "lines":[["center","double"]]} ],
  "skip_lines": [[134.0,137.0],[158.5,161.2]],      # no lane lines through crosswalks / junctions
}
Lateral values are on the same smoothed route as build_v3 (right of travel = +). Heights: road 0, kerbed elems +0.15 m.
Everything goes into the `Road` collection (re-runnable). Japanese standard markings: 0.15 m lines, 5 m dashes / 5 m gaps,
double centre line 0.15 + 0.15 + 0.15 m.
"""
import bpy, bmesh, json, math, os
import numpy as np
SH = os.environ.get("BLENDER_SHARED", "")
S = RPARAMS.get("S", 1.6)
P = np.array(json.load(open(SH + r"\path_level.json"))["path"])
u = (P[:, 0] - 266.0) / 180.0
cx = np.polyfit(u, P[:, 1], 4); cy = np.polyfit(u, P[:, 2], 4); cz = np.polyfit(u, P[:, 3], 2)
def frame(s):
    uu = (s - 266.0) / 180.0
    p = np.array([np.polyval(cx, uu), np.polyval(cy, uu)]); d = np.array([np.polyval(np.polyder(cx), uu), np.polyval(np.polyder(cy), uu)])
    t = d / np.linalg.norm(d); return p, t, np.array([t[1], -t[0]]), float(np.polyval(cz, uu))
col = bpy.data.collections.get("Road")
if col:
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
col = bpy.data.collections.new("Road"); bpy.context.scene.collection.children.link(col)
def mat(name, rgb, rough=0.9):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough; m.diffuse_color = (*rgb, 1); return m
MAT = {"road": mat("RoadAsphalt", (0.09, 0.09, 0.10)), "sidewalk": mat("SidewalkPaving", (0.55, 0.53, 0.50)),
       "median": mat("MedianConcrete", (0.50, 0.50, 0.48)), "planting": mat("PlantingStrip", (0.20, 0.33, 0.14)),
       "paint": mat("RoadPaint", (0.93, 0.93, 0.90), 0.6)}
KERB = 0.15 / S                                     # kerb height in units
bms = {k: bmesh.new() for k in MAT}
def strip(bm, s0, s1, l0, l1, h0, h1, closed=True):
    """box-like strip following the route between s0..s1, lateral l0..l1, heights h0..h1 (units)"""
    if s1 - s0 < 0.05: return
    n = max(1, int((s1 - s0) / 1.5))
    rings = []
    for k in range(n + 1):
        s = s0 + (s1 - s0) * k / n; p, t, nr, g = frame(s)
        a = (p + nr * l0) * S; b = (p + nr * l1) * S
        rings.append([bm.verts.new((a[0], a[1], (g + h0) * S)), bm.verts.new((b[0], b[1], (g + h0) * S)),
                      bm.verts.new((b[0], b[1], (g + h1) * S)), bm.verts.new((a[0], a[1], (g + h1) * S))])
    for k in range(n):
        A, B = rings[k], rings[k + 1]
        for j in range(4):
            j2 = (j + 1) % 4
            bm.faces.new((A[j], A[j2], B[j2], B[j]))
    if closed:
        bm.faces.new(tuple(reversed(rings[0]))); bm.faces.new(tuple(rings[-1]))
def intervals(s0, s1, cuts):
    """[s0,s1] minus the cut intervals"""
    out = [(s0, s1)]
    for a, b in cuts:
        nxt = []
        for x, y in out:
            if b <= x or a >= y: nxt.append((x, y)); continue
            if a > x: nxt.append((x, a))
            if b < y: nxt.append((b, y))
        out = nxt
    return out
openings = RPARAMS.get("openings", []); skip_lines = RPARAMS.get("skip_lines", [])
W = 0.15 / S; DASH = 5.0 / S
def line(s0, s1, lat, kind):
    for a, b in intervals(s0, s1, skip_lines):
        if kind == "solid": strip(bms["paint"], a, b, lat - W / 2, lat + W / 2, 0.0, 0.012 / S, closed=False)
        elif kind == "double":
            for off in (-W, W): strip(bms["paint"], a, b, lat + off - W / 2, lat + off + W / 2, 0.0, 0.012 / S, closed=False)
        else:
            s = a
            while s < b:
                strip(bms["paint"], s, min(s + DASH, b), lat - W / 2, lat + W / 2, 0.0, 0.012 / S, closed=False); s += 2 * DASH
n_el = 0
for sec in RPARAMS["sections"]:
    for e in sec["elems"]:
        cuts = [(o["s0"], o["s1"]) for o in openings if e["type"] in o.get("types", []) and (o.get("side") is None or (o["side"] == "left") == (e["l1"] <= 0.5))]
        for a, b in intervals(sec["s0"], sec["s1"], cuts):
            if e["type"] == "road":
                strip(bms["road"], a, b, e["l0"], e["l1"], -0.05 / S, 0.0)
                for lat, kind in e.get("lines", []):
                    line(a, b, lat, kind)
            else:
                kind = "planting" if e["type"] == "planting" else ("median" if e["type"] == "median" else "sidewalk")
                strip(bms[kind], a, b, e["l0"], e["l1"], -0.05 / S, KERB)
            n_el += 1
for o in openings:                                   # pave the junction where medians / sidewalks were removed
    if o.get("fill"): strip(bms["road"], o["s0"], o["s1"], o["fill"][0], o["fill"][1], -0.05 / S, 0.0)
for st in RPARAMS.get("side_streets", []):           # side street: straight carriageway perpendicular to the route
    sm = (st["s0"] + st["s1"]) / 2; p, t, nr, g = frame(sm); half = (st["s1"] - st["s0"]) / 2
    a0, a1 = st["l0"], st["l1"]; sgn = 1 if a1 > a0 else -1
    bm = bms["road"]
    def quad(bm, c0, c1, w0, w1, h):
        V = [bm.verts.new(((p + nr * c + t * w)[0] * S, (p + nr * c + t * w)[1] * S, (g + h) * S)) for c, w in ((c0, w0), (c1, w0), (c1, w1), (c0, w1))]
        bm.faces.new(V if sgn > 0 else list(reversed(V)))
    quad(bm, a0, a1, -half, half, 0.0)
    for side in (-1, 1):                             # kerbed sidewalks along the side street
        w0, w1 = (side * half, side * (half + 2.2)) if side > 0 else (side * (half + 2.2), side * half)
        V0 = [((p + nr * c + t * w)) for c, w in ((a0, w0), (a1, w0), (a1, w1), (a0, w1))]
        for k_ in range(1):
            vs = [bms["sidewalk"].verts.new((v[0] * S, v[1] * S, (g + KERB) * S)) for v in V0]
            bms["sidewalk"].faces.new(vs if sgn > 0 else list(reversed(vs)))
    for c_lat, kind in st.get("lines", []):
        if c_lat == "center":
            for off in (-W, W):
                ww = [off - W / 2, off + W / 2]
                V = [bms["paint"].verts.new(((p + nr * c + t * w)[0] * S, (p + nr * c + t * w)[1] * S, (g + 0.012 / S) * S)) for c, w in ((a0 + sgn * 3.0, ww[0]), (a1, ww[0]), (a1, ww[1]), (a0 + sgn * 3.0, ww[1]))]
                bms["paint"].faces.new(V if sgn > 0 else list(reversed(V)))
names = {"road": "RoadSurface", "sidewalk": "Sidewalks", "median": "Medians", "planting": "PlantingStrips", "paint": "LaneMarkings"}
for k, bm in bms.items():
    if not bm.faces: bm.free(); continue
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(names[k]); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(names[k], me); o.data.materials.append(MAT[k]); col.objects.link(o)
result = {"elements": n_el, "objects": len(col.objects)}

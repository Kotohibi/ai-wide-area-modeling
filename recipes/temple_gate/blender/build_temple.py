"""Build the the temple two-storey gate (rōmon) and its surroundings in Blender from temple_params.json.
Run inside Blender:  exec(compile(open(p, encoding="utf-8").read(), p, "exec"), globals())
Deletes and rebuilds its own collections (Temple_*), so edit the JSON and re-run."""
import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix

PARAMS = globals().get("TEMPLE_PARAMS", __import__("os").path.join(__import__("os").environ.get("PROJECT_DIR", "."), r"tools\temple_params.json"))
P = json.load(open(PARAMS, encoding="utf-8"))
G = P["gate"]; CX, CY = G["center"]

# ---------------------------------------------------------------- materials
MATS = {
    "wood":    (0.10, 0.060, 0.035, 0.8),
    "wood_lt": (0.20, 0.120, 0.070, 0.8),
    "plaster": (0.85, 0.84, 0.80, 0.9),
    "tile":    (0.22, 0.32, 0.29, 0.5),
    "tile_dk": (0.15, 0.22, 0.20, 0.5),
    "copper":  (0.28, 0.40, 0.33, 0.4),
    "stone":   (0.62, 0.60, 0.56, 0.9),
    "granite": (0.55, 0.55, 0.53, 0.8),
    "asphalt": (0.20, 0.20, 0.20, 0.95),
    "water":   (0.03, 0.05, 0.06, 0.1),
    "wall":    (0.72, 0.62, 0.47, 0.9),
    "hedge":   (0.10, 0.22, 0.07, 0.9),
    "gold":    (0.75, 0.55, 0.20, 0.3),
    "back":    (0.80, 0.10, 0.10, 0.8),   # back face of oriented things (plaque) - shows orientation errors
}
def mat(name):
    m = bpy.data.materials.get("T_" + name)
    if m is None:
        m = bpy.data.materials.new("T_" + name); m.use_nodes = True
    c = MATS[name]; bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*c[:3], 1); bsdf.inputs["Roughness"].default_value = c[3]
    m.diffuse_color = (*c[:3], 1)
    return m

# ---------------------------------------------------------------- collections
ROOT = "Temple"
def reset_collections(names):
    root = bpy.data.collections.get(ROOT)
    if root is None:
        root = bpy.data.collections.new(ROOT); bpy.context.scene.collection.children.link(root)
    out = {}
    for n in names:
        c = bpy.data.collections.get(n)
        if c is not None:
            for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
        else:
            c = bpy.data.collections.new(n); root.children.link(c)
        out[n] = c
    return out

# ---------------------------------------------------------------- mesh builder (one object, several materials)
class MB:
    def __init__(self): self.v = []; self.f = []; self.m = []; self.mats = []
    def mi(self, name):
        if name not in self.mats: self.mats.append(name)
        return self.mats.index(name)
    def add(self, verts, faces, m):
        o = len(self.v); k = self.mi(m); self.v += [tuple(p) for p in verts]
        for f in faces: self.f.append([o + i for i in f]); self.m.append(k)
    def box(self, c, s, m, rz=0.0):
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2; cr, sr = math.cos(rz), math.sin(rz)
        vs = []
        for z in (-hz, hz):
            for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
                vs.append((c[0] + x * cr - y * sr, c[1] + x * sr + y * cr, c[2] + z))
        self.add(vs, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], m)
    def aabb(self, x0, y0, z0, x1, y1, z1, m):
        self.box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), m)
    def beam(self, p0, p1, w, h, m):
        """Box from p0 to p1 (3D), width w (horizontal), height h (perpendicular)."""
        a, b = Vector(p0), Vector(p1); d = b - a; L = d.length
        if L < 1e-6: return
        t = d / L; side = t.cross(Vector((0, 0, 1)))
        if side.length < 1e-6: side = Vector((1, 0, 0))
        side.normalize(); up = side.cross(t).normalized()
        vs = []
        for e in (a, b):
            for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                vs.append(tuple(e + side * (sx * w / 2) + up * (sz * h / 2)))
        self.add(vs, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], m)
    def cyl(self, x, y, z0, z1, r, m, n=16):
        vs = [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n), z) for z in (z0, z1) for i in range(n)]
        fs = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        self.add(vs, fs, m)
    def build(self, name, coll, smooth=False):
        me = bpy.data.meshes.new(name); me.from_pydata(self.v, [], self.f); me.update()
        for n in self.mats: me.materials.append(mat(n))
        for p, k in zip(me.polygons, self.m): p.material_index = k; p.use_smooth = smooth
        ob = bpy.data.objects.new(name, me); coll.objects.link(ob); return ob

def W(u, v, z=0.0):            # gate local -> model frame
    return (CX + u, CY + v, z)

# ---------------------------------------------------------------- roof surfaces
def g(s, p): return max(0.0, min(1.0, s)) ** p

def hip_gable_z(u, v, R):
    """Irimoya roof height at (u,v): hips below the gable, gable roof above it, concave slopes, corner upturn."""
    hu, hv, ze, zr, gu, p = R["hu"], R["hv"], R["z_eave"], R["z_ridge"], R["gable_u"], R["p"]
    D = zr - ze
    zf = ze + D * g((hv - abs(v)) / hv, p)
    zs = ze + D * g((hu - abs(u)) / hv, p)
    z = zf if abs(u) <= gu else min(zf, zs)
    front = abs(u) <= gu or zf <= zs
    z += R["rise"] * (abs(u) / hu) ** 3 * (abs(v) / hv) ** 3
    return z, front

def pent_z(u, v, R):
    hu, hv, ze, zt, p = R["hu"], R["hv"], R["z_eave"], R["z_top"], R["p"]
    du, dv = hu - abs(u), hv - abs(v); Dw = hu - R["inner_hu"]
    d = min(du, dv); z = ze + (zt - ze) * g(d / Dw, p)
    z += R["rise"] * (abs(u) / hu) ** 3 * (abs(v) / hv) ** 3
    return z, dv <= du, d <= Dw + 1e-6

def ribs(u, v, front, amp=0.035, pitch=0.30):
    t = (u if front else v) / pitch
    return amp * abs(math.sin(math.pi * t)) ** 0.6

def axis_samples(h, step, extra=()):
    n = int(round(2 * h / step)); xs = sorted(set([round(-h + 2 * h * i / n, 4) for i in range(n + 1)] + [round(e, 4) for e in extra]))
    return xs

def roof_object(name, coll, R, kind):
    step = 0.05
    if kind == "hip":
        gu = R["gable_u"]; us = axis_samples(R["hu"], step, (gu, -gu, gu + 0.01, -gu - 0.01))
    else:
        us = axis_samples(R["hu"], step)
    vs = axis_samples(R["hv"], step)
    bm = bmesh.new(); grid = {}
    for j, v in enumerate(vs):
        for i, u in enumerate(us):
            if kind == "hip":
                z, front = hip_gable_z(u, v, R); keep = True
            else:
                z, front, keep = pent_z(u, v, R)
            grid[i, j] = (bm.verts.new(W(u, v, z + ribs(u, v, front))), keep)
    for j in range(len(vs) - 1):
        for i in range(len(us) - 1):
            q = [grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]]
            if kind == "pent" and not all(k for _, k in q):
                continue
            bm.faces.new([a for a, _ in q])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    loose = [vv for vv in bm.verts if not vv.link_faces]; bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat("tile")); me.materials.append(mat("wood"))
    for pg in me.polygons: pg.use_smooth = True
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    sd = ob.modifiers.new("thick", "SOLIDIFY"); sd.thickness = R["thick"]; sd.offset = -1.0
    sd.material_offset = 1; sd.material_offset_rim = 1; sd.use_even_offset = True
    return ob

def rafters(mb, R, zfun, inner_u, inner_v, pitch=0.24):
    """Rafters under the eave all round: from the eave edge inward to the purlin line, just under the roof."""
    hu, hv, t = R["hu"], R["hv"], R["thick"]
    def under(u, v): return zfun(u, v) - t - 0.06
    # front/back edges
    n = int(2 * (inner_u + 0.3) / pitch)
    for sgn in (-1, 1):
        for i in range(n + 1):
            u = -(inner_u + 0.3) + i * pitch
            mb.beam(W(u, sgn * (hv - 0.02), under(u, sgn * (hv - 0.02))), W(u, sgn * inner_v, under(u, sgn * inner_v)), 0.09, 0.11, "wood_lt")
    m = int(2 * (inner_v + 0.3) / pitch)
    for sgn in (-1, 1):
        for i in range(m + 1):
            v = -(inner_v + 0.3) + i * pitch
            mb.beam(W(sgn * (hu - 0.02), v, under(sgn * (hu - 0.02), v)), W(sgn * inner_u, v, under(sgn * inner_u, v)), 0.09, 0.11, "wood_lt")
    for su in (-1, 1):                      # corner rafters (sumigi)
        for sv in (-1, 1):
            a = (su * hu, sv * hv); b = (su * inner_u, sv * inner_v)
            mb.beam(W(a[0], a[1], under(*a) + 0.05), W(b[0], b[1], under(*b)), 0.2, 0.24, "wood")

def bracket_set(mb, u, v, z0, z1, out_u, out_v, tiers, m="wood"):
    """Stack of bearing blocks and arms on a pillar, stepping outward (out_u/out_v: unit outward direction)."""
    h = (z1 - z0) / (tiers * 2)
    z = z0
    mb.box(W(u, v, z + h / 2), (0.42, 0.42, h), m); z += h
    for k in range(tiers):
        du, dv = out_u * 0.42 * k, out_v * 0.42 * k
        L = 1.1 - 0.1 * k
        mb.box(W(u + du + out_u * 0.21, v + dv + out_v * 0.21, z + h / 2), (L if out_v else 0.9, L if out_u else 0.9, h * 0.8), m)  # cross arms
        z += h
        mb.box(W(u + du + out_u * 0.42, v + dv + out_v * 0.42, z + h / 2), (0.3, 0.3, h), m)
        mb.box(W(u + du + out_u * 0.42 - out_v * 0.4, v + dv + out_v * 0.42 - out_u * 0.4, z + h / 2), (0.26, 0.26, h), m)
        mb.box(W(u + du + out_u * 0.42 + out_v * 0.4, v + dv + out_v * 0.42 + out_u * 0.4, z + h / 2), (0.26, 0.26, h), m)
        z += h

def perimeter_pts(us, vs):
    """Pillar positions on the outer ring with outward directions."""
    out = []
    for u in us:
        for v in (vs[0], vs[-1]): out.append((u, v, 0, 1 if v > 0 else -1))
    for v in vs[1:-1]:
        for u in (us[0], us[-1]): out.append((u, v, 1 if u > 0 else -1, 0))
    return out

# ================================================================= build
cols = reset_collections(["Temple_Gate_Base", "Temple_Gate_Lower", "Temple_Gate_PentRoof",
                          "Temple_Gate_Upper", "Temple_Gate_Roof"])
# ground, walls, hedges and the rest of the precinct: build_site.py

# ---- platform, gutter, bridge, bollards
pf = G["platform"]; gt = G["gutter"]; br = G["bridge"]; mb = MB()
mb.aabb(CX - pf["hu"], CY - pf["hv"], -0.02, CX + pf["hu"], CY + pf["hv"], pf["h"], "stone")
mb.aabb(CX - pf["hu"] - 0.12, CY - pf["hv"] - 0.12, -0.02, CX + pf["hu"] + 0.12, CY + pf["hv"] + 0.12, pf["h"] - 0.06, "granite")
mb.aabb(CX - pf["hu"], CY + gt["v0"], gt["z"] - 0.02, CX + pf["hu"], CY + gt["v1"] - 0.12, gt["z"], "water")
mb.aabb(CX - pf["hu"], CY + gt["v0"] - 0.15, -0.3, CX + pf["hu"], CY + gt["v0"], 0.06, "granite")      # gutter outer kerb
mb.aabb(CX - br["hu"], CY + gt["v0"] - 0.15, -0.02, CX + br["hu"], CY + gt["v1"], br["z"], "granite")   # bridge slab / step
for bu in G["bollards_u"]:
    mb.aabb(CX + bu - 0.17, CY + G["bollard_v"] - 0.17, 0, CX + bu + 0.17, CY + G["bollard_v"] + 0.17, 0.15, "granite")
    mb.cyl(CX + bu, CY + G["bollard_v"], 0.15, G["bollard_h"], G["bollard_r"], "granite", 12)
    mb.cyl(CX + bu, CY + G["bollard_v"], G["bollard_h"], G["bollard_h"] + 0.12, G["bollard_r"] * 0.7, "granite", 12)
mb.build("Gate_Platform", cols["Temple_Gate_Base"])

# ---- lower storey
z_pf = pf["h"]; L = G["lower"]; PU, PV = G["pillars_u"], G["pillars_v"]; r = G["pillar_r"]
mb = MB()
for u in PU:
    for v in PV:
        mb.cyl(*W(u, v)[:2], z_pf, G["pillar_top"], r, "wood")
        mb.cyl(*W(u, v)[:2], z_pf, z_pf + G["nemaki_h"], r + 0.025, "copper")
        mb.box(W(u, v, z_pf + 0.06), (0.62, 0.62, 0.12), "granite")
# tie beams on all pillar lines
for v in PV:
    mb.aabb(CX + PU[0] - 0.35, CY + v - 0.1, L["kashira_z"][0], CX + PU[-1] + 0.35, CY + v + 0.1, L["kashira_z"][1], "wood")
for u in PU:
    mb.aabb(CX + u - 0.1, CY + PV[0] - 0.35, L["kashira_z"][0], CX + u + 0.1, CY + PV[-1] + 0.35, L["kashira_z"][1], "wood")
for v in (PV[0], PV[-1]):
    mb.aabb(CX + PU[0], CY + v - 0.08, L["tobinuki_z"][0], CX + PU[-1], CY + v + 0.08, L["tobinuki_z"][1], "wood")
# side bays: plaster walls on the outer sides and passage sides, slat fences front and back
for u in PU:
    t = 0.12
    mb.aabb(CX + u - t / 2, CY + PV[0], z_pf, CX + u + t / 2, CY + PV[-1], L["kashira_z"][0], "plaster")
    mb.aabb(CX + u - t / 2 - 0.02, CY + PV[0], L["hiraki_z"][0], CX + u + t / 2 + 0.02, CY + PV[-1], L["hiraki_z"][1], "wood")
    mb.aabb(CX + u - t / 2 - 0.02, CY + PV[0], L["tobinuki_z"][0], CX + u + t / 2 + 0.02, CY + PV[-1], L["tobinuki_z"][1], "wood")
    mb.aabb(CX + u - t / 2 - 0.02, CY + PV[0], z_pf, CX + u + t / 2 + 0.02, CY + PV[-1], z_pf + 0.2, "wood")
for (ua, ub) in ((PU[0], PU[1]), (PU[2], PU[3])):
    for v in (PV[0], PV[-1]):
        f0, f1 = L["fence_z"]
        mb.aabb(CX + ua, CY + v - 0.06, f0 - 0.1, CX + ub, CY + v + 0.06, f0, "wood")
        mb.aabb(CX + ua, CY + v - 0.06, f1, CX + ub, CY + v + 0.06, f1 + 0.1, "wood")
        mb.aabb(CX + ua, CY + v - 0.05, (f0 + f1) / 2 - 0.04, CX + ub, CY + v + 0.05, (f0 + f1) / 2 + 0.04, "wood")
        n = int((ub - ua - 2 * r) / L["fence_pitch"])
        for i in range(1, n):
            uu = ua + r + i * (ub - ua - 2 * r) / n
            mb.aabb(CX + uu - 0.03, CY + v - 0.03, f0, CX + uu + 0.03, CY + v + 0.03, f1, "wood")
# passage ceiling + lower brackets
mb.aabb(CX + PU[0], CY + PV[0], L["ceiling_z"] - 0.05, CX + PU[-1], CY + PV[-1], L["ceiling_z"], "wood")
for (u, v, ou, ov) in perimeter_pts(PU, PV):
    bracket_set(mb, u, v, L["bracket_z"][0], L["bracket_z"][1], ou, ov, 2)
for u in [(PU[i] + PU[i + 1]) / 2 for i in range(3)]:          # intermediate supports (nakazonae)
    for v in (PV[0], PV[-1]):
        mb.box(W(u, v, L["bracket_z"][0] + 0.15), (0.5, 0.25, 0.3), "wood")
pr = G["pent_roof"]; kz = L["bracket_z"][1]
for v in (PV[0] - 0.84, PV[-1] + 0.84):                          # outer purlins on the brackets
    mb.aabb(CX + PU[0] - 0.84, CY + v - 0.1, kz, CX + PU[-1] + 0.84, CY + v + 0.1, kz + 0.18, "wood")
for u in (PU[0] - 0.84, PU[-1] + 0.84):
    mb.aabb(CX + u - 0.1, CY + PV[0] - 0.84, kz, CX + u + 0.1, CY + PV[-1] + 0.84, kz + 0.18, "wood")
mb.build("Gate_Lower", cols["Temple_Gate_Lower"])

# ---- pent roof (lower roof)
roof_object("Gate_PentRoof", cols["Temple_Gate_PentRoof"], pr, "pent")
mb = MB()
rafters(mb, pr, lambda u, v: pent_z(u, v, pr)[0], -PU[0] + 0.84, PV[-1] + 0.84)
for su in (-1, 1):                                               # hip ridges of the pent roof
    for sv in (-1, 1):
        a = (su * pr["inner_hu"], sv * pr["inner_hv"]); b = (su * (pr["hu"] - 0.1), sv * (pr["hv"] - 0.1))
        mb.beam(W(a[0], a[1], pent_z(*a, pr)[0] + 0.1), W(b[0], b[1], pent_z(*b, pr)[0] + 0.12), 0.22, 0.2, "tile_dk")
mb.build("Gate_PentRoof_Rafters", cols["Temple_Gate_PentRoof"])

# ---- balcony + upper storey
bc = G["balcony"]; U = G["upper"]; mb = MB()
mb.aabb(CX - bc["hu"], CY - bc["hv"], bc["z"], CX + bc["hu"], CY + bc["hv"], bc["z"] + bc["t"], "wood")
zb = bc["z"] + bc["t"]; ru, rv, rh = bc["rail_hu"], bc["rail_hv"], bc["rail_h"]
ring = [(-ru, -rv), (ru, -rv), (ru, rv), (-ru, rv), (-ru, -rv)]
for (a, b) in zip(ring[:-1], ring[1:]):
    for zz, hh in ((zb + 0.08, 0.08), (zb + 0.45, 0.07), (zb + rh, 0.09)):
        mb.beam(W(a[0], a[1], zz), W(b[0], b[1], zz), 0.09, hh, "wood")
    L_ = math.dist(a, b); n = max(1, int(L_ / 0.9))
    for i in range(n):
        q = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
        mb.aabb(CX + q[0] - 0.06, CY + q[1] - 0.06, zb, CX + q[0] + 0.06, CY + q[1] + 0.06, zb + rh + 0.12, "wood")
UU, UV = U["pillars_u"], U["pillars_v"]
for u in UU:
    for v in UV:
        if v != 0 or u in (UU[0], UU[-1]):
            mb.cyl(*W(u, v)[:2], U["z0"], U["z1"], U["pillar_r"], "wood")
hu_, hv_ = UU[-1], UV[-1]
# walls: plaster with wooden rails; front/back centre bay = dark doors, side bays = slat windows
for sv in (-1, 1):
    v = sv * hv_
    mb.aabb(CX - hu_, CY + v - 0.06, U["z0"], CX + hu_, CY + v + 0.06, U["z1"], "plaster")
    mb.aabb(CX + UU[1] + 0.12, CY + v + sv * 0.04, U["z0"] + 0.05, CX + UU[2] - 0.12, CY + v + sv * 0.08, U["z1"] - 0.35, "wood")
    for (ua, ub) in ((UU[0], UU[1]), (UU[2], UU[3])):
        mb.aabb(CX + ua + 0.25, CY + v + sv * 0.04, U["z0"] + 0.55, CX + ub - 0.25, CY + v + sv * 0.08, U["z1"] - 0.4, "wood")
    for zz in (U["z0"] + 0.45, U["z1"] - 0.38):
        mb.aabb(CX - hu_ - 0.05, CY + v - 0.1, zz, CX + hu_ + 0.05, CY + v + 0.1, zz + 0.1, "wood")
for su in (-1, 1):
    u = su * hu_
    mb.aabb(CX + u - 0.06, CY - hv_, U["z0"], CX + u + 0.06, CY + hv_, U["z1"], "plaster")
    for zz in (U["z0"] + 0.45, U["z1"] - 0.38):
        mb.aabb(CX + u - 0.1, CY - hv_ - 0.05, zz, CX + u + 0.1, CY + hv_ + 0.05, zz + 0.1, "wood")
for v in (-hv_, hv_):
    mb.aabb(CX - hu_ - 0.3, CY + v - 0.1, U["kashira_z"][0], CX + hu_ + 0.3, CY + v + 0.1, U["kashira_z"][1], "wood")
for u in (-hu_, hu_):
    mb.aabb(CX + u - 0.1, CY - hv_ - 0.3, U["kashira_z"][0], CX + u + 0.1, CY + hv_ + 0.3, U["kashira_z"][1], "wood")
# balcony support brackets under the floor, on the lower pillar line
for (u, v, ou, ov) in perimeter_pts(PU, PV):
    mb.box(W(u + ou * 0.2, v + ov * 0.2, bc["z"] - 0.12), (0.5 if ov else 0.7, 0.7 if ov else 0.5, 0.24), "wood")
# upper brackets: 3 steps out to the purlin
for (u, v, ou, ov) in perimeter_pts(UU, UV):
    bracket_set(mb, u, v, U["bracket_z"][0], U["bracket_z"][1], ou, ov, 3)
for u in [(UU[i] + UU[i + 1]) / 2 for i in range(3)]:
    for v in (-hv_, hv_):
        if abs(u) < 0.01 and v < 0: continue                    # the plaque hangs here on the front
        bracket_set(mb, u, v, U["bracket_z"][0], U["bracket_z"][1], 0, 1 if v > 0 else -1, 3)
kz = U["bracket_z"][1]; ku, kv = U["keta_u"], U["keta_v"]
mb.aabb(CX - hu_, CY - hv_, kz - 0.02, CX + hu_, CY + hv_, kz + 0.04, "wood")                  # ceiling over the upper room
for (x0, y0, x1, y1) in ((-ku, -kv, ku, -hv_), (-ku, hv_, ku, kv), (-ku, -hv_, -hu_, hv_), (hu_, -hv_, ku, hv_)):
    mb.aabb(CX + x0, CY + y0, kz, CX + x1, CY + y1, kz + 0.05, "wood")                         # soffit boards between brackets
for v in (-kv, kv):
    mb.aabb(CX - ku - 0.3, CY + v - 0.12, kz, CX + ku + 0.3, CY + v + 0.12, kz + 0.22, "wood")
for u in (-ku, ku):
    mb.aabb(CX + u - 0.12, CY - kv - 0.3, kz, CX + u + 0.12, CY + kv + 0.3, kz + 0.22, "wood")
# plaque (front = south face, gold letters; back face red to show orientation)
pq = G["plaque"]; vq = -hv_ - pq.get("out", 0.85)
mb.aabb(CX - pq["w"] / 2, CY + vq, pq["z"] - pq["h"] / 2, CX + pq["w"] / 2, CY + vq + 0.08, pq["z"] + pq["h"] / 2, "wood")
mb.aabb(CX - pq["w"] / 2 + 0.12, CY + vq - 0.01, pq["z"] - pq["h"] / 2 + 0.1, CX + pq["w"] / 2 - 0.12, CY + vq, pq["z"] + pq["h"] / 2 - 0.1, "gold")
mb.aabb(CX - pq["w"] / 2 + 0.12, CY + vq + 0.08, pq["z"] - pq["h"] / 2 + 0.1, CX + pq["w"] / 2 - 0.12, CY + vq + 0.09, pq["z"] + pq["h"] / 2 - 0.1, "back")
mb.build("Gate_Upper", cols["Temple_Gate_Upper"])

# ---- upper roof (irimoya)
R = G["roof"]
roof_object("Gate_Roof", cols["Temple_Gate_Roof"], R, "hip")
mb = MB()
rafters(mb, R, lambda u, v: hip_gable_z(u, v, R)[0], ku, kv)
gu, hv, hu = R["gable_u"], R["hv"], R["hu"]
zg = hip_gable_z(gu + 0.011, 0, R)[0]                     # height where the hips meet the gable
def zf(v): return hip_gable_z(0, v, R)[0]
vg = 0.0
while zf(vg) > zg and vg < hv: vg += 0.01                 # half-width of the gable at its base
for su in (-1, 1):
    u = su * gu
    vs_ = [-vg + 2 * vg * i / 40 for i in range(41)]
    for a, b in zip(vs_[:-1], vs_[1:]):                   # gable wall (tsuma): wood frame, plaster infill
        mb.add([W(u, a, zg), W(u, b, zg), W(u, b, zf(b) - 0.05), W(u, a, zf(a) - 0.05)], [(0, 1, 2, 3) if su > 0 else (3, 2, 1, 0)], "plaster")
        mb.beam(W(u + su * 0.06, a, zf(a) + 0.02), W(u + su * 0.06, b, zf(b) + 0.02), 0.08, 0.32, "wood")     # bargeboards
        mb.beam(W(u, a, zf(a) + 0.2), W(u, b, zf(b) + 0.2), 0.3, 0.22, "tile_dk")                              # descending ridge
    for zz in (zg + 0.05, zg + 0.6 * (R["z_ridge"] - zg)):
        w = vg * (1 - (zz - zg) / (R["z_ridge"] - zg)) ** (1 / R["p"]) if zz > zg + 0.1 else vg
        mb.aabb(CX + u - 0.04 * su - 0.04, CY - w, zz, CX + u + 0.04 * su + 0.04, CY + w, zz + 0.12, "wood")
    mb.box(W(u + su * 0.1, 0, R["z_ridge"] - 0.55), (0.06, 0.55, 0.6), "wood")                               # gegyo (hanging fish)
    for sv in (-1, 1):                                                                                          # hip ridges
        a = (su * gu, sv * vg); b = (su * (hu - 0.15), sv * (hv - 0.15))
        mb.beam(W(a[0], a[1], hip_gable_z(su * (gu + 0.02), sv * vg, R)[0] + 0.12), W(b[0], b[1], hip_gable_z(*b, R)[0] + 0.15), 0.28, 0.24, "tile_dk")
zr = R["z_ridge"]
mb.aabb(CX - R["ridge_u"], CY - 0.22, zr - 0.05, CX + R["ridge_u"], CY + 0.22, zr + R["ridge_h"], "tile_dk")
for su in (-1, 1):
    mb.aabb(CX + su * R["ridge_u"] - 0.25, CY - 0.3, zr, CX + su * R["ridge_u"] + 0.15, CY + 0.3, zr + R["oni_h"], "tile_dk")    # onigawara
    mb.beam(W(su * (R["ridge_u"] - 0.05), 0, zr + R["oni_h"] - 0.1), W(su * (R["ridge_u"] + 0.3), 0, zr + R["oni_h"] + 0.05), 0.5, 0.14, "tile_dk")  # flared top (toribusuma)
mb.build("Gate_Roof_Parts", cols["Temple_Gate_Roof"])

result = {"objects": {c: [o.name for o in col.objects] for c, col in cols.items()},
          "gable_base_z": round(zg, 3), "gable_half_width": round(vg, 2)}
